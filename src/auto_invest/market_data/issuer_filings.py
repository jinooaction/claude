"""Fixed official issuer release contracts, distinct from regulatory filings."""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, fields
from datetime import UTC, timedelta
from email.utils import parsedate_to_datetime
from uuid import uuid4

from auto_invest.analytics.earnings_event_inputs import _text
from auto_invest.analytics.filing_observations import (
    ISSUER_CIK,
    ISSUER_FEED,
    MAX_BYTES,
    Observation,
    issuer_document_id,
    utc,
)
from auto_invest.market_data.filing_collector import Collector, Scope

LISTING_URL = "https://news.microsoft.com/source/tag/press-releases/"
USER_AGENT = "AutoInvestResearch/1.0"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _one(parent, name):
    elements = parent.findall(name)
    _require(len(elements) == 1 and len(elements[0]) == 0, "invalid feed field")
    value = elements[0].text
    _require(isinstance(value, str) and 0 < len(value.strip()) <= 256, "invalid feed value")
    return value.strip()


def parse_feed(raw: bytes) -> tuple[list[dict], int]:
    """Select candidates only; no claim of earnings semantics or full coverage."""
    _require(len(raw) <= MAX_BYTES, "feed size limit")
    text = raw.decode("utf-8")
    _require("\x00" not in text and "<!doctype" not in text.lower()
             and "<!entity" not in text.lower(), "unsafe XML declaration")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError("invalid feed XML") from exc
    _require(root.tag == "rss" and root.get("version") == "2.0", "invalid feed root")
    channels = root.findall("channel")
    _require(len(channels) == 1, "invalid feed channel")
    channel = channels[0]
    _require(_one(channel, "link") == LISTING_URL, "wrong issuer channel")
    items = channel.findall("item")
    _require(len(items) <= 100, "feed item limit")
    selected, seen, ignored = [], set(), 0
    for item in items:
        url, title, published = (_one(item, name) for name in ("link", "title", "pubDate"))
        identity = issuer_document_id(url)
        _require(identity not in seen, "duplicate feed item")
        seen.add(identity)
        try:
            stamp = parsedate_to_datetime(published)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("invalid feed date") from exc
        _require(stamp.tzinfo is not None and stamp.utcoffset() is not None,
                 "feed timezone required")
        claim = stamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
        lower = title.lower()
        candidate = "microsoft" in lower and (
            "earnings" in lower or ("quarter" in lower and "results" in lower))
        if candidate:
            selected.append({"url": url, "document_id": identity, "title": title,
                             "published_at": claim})
        else:
            ignored += 1
    return sorted(selected, key=lambda row: (row["published_at"], row["url"]),
                  reverse=True), ignored


def validate_release(raw: bytes, title: str) -> None:
    _require(len(raw) <= MAX_BYTES, "release size limit")
    html = raw.decode("utf-8")
    _require("</html>" in html.lower(), "incomplete issuer document")
    visible = _text(raw)
    normalized_title = " ".join(title.split())
    _require(bool(normalized_title) and normalized_title in visible
             and re.search(r"\bMicrosoft\b", visible) is not None,
             "issuer release title mismatch")


@dataclass(frozen=True)
class IssuerScope:
    max_documents: int = 3
    max_bytes: int = MAX_BYTES
    interval_seconds: float = 1.0
    timeout_seconds: float = 20.0
    budget_seconds: float = 180.0
    retries: int = 2

    def __post_init__(self):
        Scope(**asdict(self))  # Same established timing, retry and byte limits.
        _require(self.max_documents <= 3, "issuer document limit")

    @classmethod
    def from_dict(cls, value):
        _require(isinstance(value, dict) and set(value) == {f.name for f in fields(cls)},
                 "unexpected issuer scope fields")
        return cls(**value)

    @property
    def sha256(self):
        config = {"provider": "microsoft_press_releases", **asdict(self)}
        return hashlib.sha256(json.dumps(config, sort_keys=True,
                                        separators=(",", ":")).encode()).hexdigest()


class IssuerCollector(Collector):
    @staticmethod
    def valid_agent(value):
        return value == USER_AGENT

    @staticmethod
    def source_kind(accession):
        return "issuer_listing" if accession is None else "issuer_primary"

    def _may_reuse_primaries(self, history, listing_sha, selected, verified_at):
        """Only an identical latest listing and recent complete GETs permit skips."""
        if not history or not selected:
            return False
        latest = history[-1]["manifest"]
        if latest["failures"] or latest.get("selection", {}).get("limit_skipped", 0):
            return False
        latest_listings = [item for item in self.store._receipts(latest)
                           if item.source_kind == "issuer_listing"]
        if len(latest_listings) != 1 or latest_listings[0].blob_sha256 != listing_sha:
            return False
        expected = {row["document_id"] for row in selected}
        for run in reversed(history):
            manifest = run["manifest"]
            if manifest["failures"] or manifest.get("selection", {}).get("unchanged", 0):
                continue
            receipts = self.store._receipts(manifest)
            listings = [item for item in receipts if item.source_kind == "issuer_listing"]
            if len(listings) != 1 or listings[0].blob_sha256 != listing_sha:
                continue
            verified = utc(run["finalized_at"])
            if not verified <= utc(verified_at) < verified + timedelta(hours=24):
                return False
            primary_ids = {item.accession for item in receipts
                           if item.source_kind == "issuer_primary"}
            return expected <= primary_ids
        return False

    def collect(self, *, run_id: str, source_commit: str,
                reuse_unchanged: bool = False) -> dict:
        _require(isinstance(self.scope, IssuerScope), "issuer scope required")
        _require(type(reuse_unchanged) is bool, "invalid issuer reuse option")
        history, started = self.begin(run_id, source_commit)
        observations = []
        selection = {"unselected": 0, "limit_skipped": 0}
        if reuse_unchanged:
            selection["unchanged"] = 0

        def record(url, identity, fetched, claims):
            raw, _, requested, received, verified = fetched
            observations.append(Observation(
                str(uuid4()), ISSUER_CIK, identity, self.source_kind(identity), url,
                self.store.blobs.put(raw), requested, received, verified, claims))

        fetched = self._fetch(ISSUER_CIK, ISSUER_FEED, parse_feed)
        if fetched is not None:
            record(ISSUER_FEED, None, fetched, {})
            candidates, selection["unselected"] = fetched[1]
            selected = candidates[:self.scope.max_documents]
            selection["limit_skipped"] = len(candidates) - len(selected)
            if reuse_unchanged and self._may_reuse_primaries(
                    history, hashlib.sha256(fetched[0]).hexdigest(), selected, fetched[4]):
                selection["unchanged"] = len(selected)
                selected = []
            for row in selected:
                fetched = self._fetch(
                    ISSUER_CIK, row["url"],
                    lambda raw, title=row["title"]: validate_release(raw, title),
                    accession=row["document_id"])
                if fetched is not None:
                    record(row["url"], row["document_id"], fetched,
                           {key: row[key] for key in ("title", "published_at")})
        return self.finish(run_id, source_commit, history, started, observations,
                           sum(selection.values()), selection=selection)
