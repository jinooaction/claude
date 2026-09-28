"""Fixed official issuer release contracts, distinct from regulatory filings."""

import re
import xml.etree.ElementTree as ET
from datetime import UTC
from email.utils import parsedate_to_datetime

from auto_invest.analytics.earnings_event_inputs import _text
from auto_invest.analytics.filing_observations import MAX_BYTES, issuer_document_id

LISTING_URL = "https://news.microsoft.com/source/tag/press-releases/"


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
