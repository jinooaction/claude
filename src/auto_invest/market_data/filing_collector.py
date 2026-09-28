"""Bounded, read-only SEC collector. No source claim becomes a trading event."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from uuid import uuid4

import httpx

from auto_invest.analytics.filing_observations import MAX_BYTES, Observation, RunStore, utc


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


@dataclass(frozen=True)
class Scope:
    ciks: tuple[str, ...] = ("0000789019",)
    forms: tuple[str, ...] = ("8-K", "8-K/A")
    max_documents: int = 5
    max_bytes: int = MAX_BYTES
    interval_seconds: float = 1.0
    timeout_seconds: float = 20.0
    budget_seconds: float = 180.0
    retries: int = 2

    def __post_init__(self):
        _require(isinstance(self.ciks, tuple) and 1 <= len(self.ciks) <= 10,
                 "invalid issuer scope")
        _require(all(isinstance(cik, str) and re.fullmatch(r"[0-9]{10}", cik)
                     and int(cik) > 0 for cik in self.ciks), "invalid issuer CIK")
        _require(len(set(self.ciks)) == len(self.ciks), "duplicate issuer")
        _require(isinstance(self.forms, tuple) and bool(self.forms)
                 and set(self.forms) <= {"8-K", "8-K/A"}
                 and len(set(self.forms)) == len(self.forms), "invalid form scope")
        for name, lower, upper in (
            ("max_documents", 1, 5), ("max_bytes", 1, MAX_BYTES), ("retries", 0, 2),
        ):
            value = getattr(self, name)
            _require(type(value) is int and lower <= value <= upper, "invalid collection limit")
        for name, lower, upper in (
            ("interval_seconds", 1, 60), ("timeout_seconds", 0.1, 20),
            ("budget_seconds", 1, 180),
        ):
            value = getattr(self, name)
            _require(type(value) in (int, float) and lower <= value <= upper,
                     "invalid collection timing")

    @classmethod
    def from_dict(cls, value: dict) -> Scope:
        _require(isinstance(value, dict) and set(value) == {f.name for f in fields(cls)},
                 "unexpected or missing scope fields")
        result = dict(value)
        for name in ("ciks", "forms"):
            _require(isinstance(result[name], list), "expected scope array")
            result[name] = tuple(result[name])
        return cls(**result)

    @property
    def sha256(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


def _json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "duplicate source JSON field")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("invalid JSON constant")

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON encoding or nesting") from exc
    _require(isinstance(value, dict), "invalid source JSON object")
    return value


def parse_listing(raw: bytes, cik: str, forms: tuple[str, ...]) -> tuple[str, list[dict]]:
    """Check column alignment/identity; return recent scope, not historical coverage."""
    source = _json(raw)
    identity = source.get("cik")
    _require(type(identity) in (int, str) and str(identity).isdigit()
             and int(identity) == int(cik), "listing issuer mismatch")
    name = source.get("name")
    _require(isinstance(name, str) and 0 < len(name) <= 256, "invalid issuer name")
    filings = source.get("filings")
    _require(isinstance(filings, dict), "missing filing listing")
    rows = filings.get("recent")
    _require(isinstance(rows, dict), "missing recent filings")
    columns = ("accessionNumber", "form", "primaryDocument", "filingDate",
               "reportDate", "acceptanceDateTime")
    _require(all(isinstance(rows.get(key), list) for key in columns), "invalid listing columns")
    count = len(rows["accessionNumber"])
    _require(all(len(rows[key]) == count for key in columns), "misaligned listing columns")
    selected, seen = [], set()
    for index in range(count):
        row = {key: rows[key][index] for key in columns}
        _require(all(isinstance(value, str) and len(value) <= 256
                     and all(ord(char) >= 32 for char in value) for value in row.values()),
                 "invalid filing value")
        accession = row["accessionNumber"]
        _require(re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is not None,
                 "invalid filing accession")
        _require(accession not in seen, "duplicate filing accession")
        seen.add(accession)
        date.fromisoformat(row["filingDate"])
        if row["form"] not in forms:
            continue
        document = row["primaryDocument"]
        _require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:htm|html|txt)", document)
                 is not None, "invalid primary document path")
        selected.append(row)
    return name, sorted(selected, key=lambda row: (row["filingDate"], row["accessionNumber"]),
                        reverse=True)


class _DocumentText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.ciks = []
        self.cik_depth = 0

    def handle_starttag(self, tag, attrs):
        if self.cik_depth:
            self.cik_depth += 1
        elif dict(attrs).get("name", "").lower().endswith(":entitycentralindexkey"):
            self.cik_depth = 1

    def handle_endtag(self, tag):
        if self.cik_depth:
            self.cik_depth -= 1

    def handle_data(self, data):
        self.text.append(data)
        if self.cik_depth and data.strip():
            self.ciks.append(data.strip())


def _company(value: str) -> str:
    normalized = re.sub(r"\bCORP\b\.?", "CORPORATION", value.upper())
    return re.sub(r"[^A-Z0-9]", "", normalized)


def validate_primary(raw: bytes, cik: str, name: str) -> None:
    """Check document framing/issuer cues, without inferring earnings meaning."""
    text = raw.decode("utf-8")
    _require("</html>" in text.lower(), "incomplete HTML document")
    parser = _DocumentText()
    parser.feed(text)
    parser.close()
    visible = re.sub(r"\s+", " ", " ".join(parser.text)).upper()
    _require(re.search(r"FORM\s+8\s*[-–]\s*K", visible) is not None
             and "CURRENT REPORT" in visible
             and "SECURITIES AND EXCHANGE COMMISSION" in visible,
             "unexpected primary document")
    if parser.ciks:
        _require(all(value.isdigit() and int(value) == int(cik) for value in parser.ciks),
                 "primary issuer mismatch")
    else:
        _require(bool(_company(name)) and _company(name) in _company(visible),
                 "primary issuer name mismatch")


class _FetchFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Collector:
    """One serialized run. Callers own the client and may inject clocks for tests."""

    @staticmethod
    def valid_agent(value):
        return (isinstance(value, str) and 5 <= len(value) <= 256 and "@" in value
                and all(32 <= ord(char) < 127 for char in value))

    @staticmethod
    def source_kind(accession):
        return "listing" if accession is None else "primary"

    def __init__(self, store: RunStore, scope: Scope, *, user_agent: str, client: httpx.Client,
                 utc_now: Callable[[], str] | None = None,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        _require(self.valid_agent(user_agent),
                 "SEC_USER_AGENT identification required")
        self.store, self.scope, self.client = store, scope, client
        self._user_agent = user_agent
        self.utc_now = utc_now or (lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        self.monotonic, self.sleep = monotonic, sleep
        self.last_utc = None
        self.last_request = None
        self.failures = []
        self.circuit = {"consecutive_failures": 0, "cooldown_until": None}
        self.used = False

    def _now(self) -> str:
        value = self.utc_now()
        current = utc(value)
        _require(self.last_utc is None or self.last_utc <= current, "collector clock reversal")
        self.last_utc = current
        return value

    def _cooldown(self, seconds: float = 900) -> None:
        now = utc(self._now())
        try:
            until = (now + timedelta(seconds=max(900, seconds))).isoformat()
        except OverflowError:
            until = datetime.max.replace(tzinfo=UTC).isoformat()
        previous = self.circuit["cooldown_until"]
        if previous is None or utc(previous) < datetime.fromisoformat(until):
            self.circuit["cooldown_until"] = until.replace("+00:00", "Z")

    def _failure(self, cik: str, code: str, accession: str | None, *, count: bool = True) -> None:
        self.failures.append({"issuer_cik": cik, "code": code, "accession": accession,
                              "source_kind": self.source_kind(accession)})
        if count:
            self.circuit["consecutive_failures"] += 1
        if code == "http_403" or (count and self.circuit["consecutive_failures"] >= 3):
            self._cooldown()

    def _remaining(self) -> float:
        return self.scope.budget_seconds - (self.monotonic() - self.started_monotonic)

    def _wait(self, seconds: float) -> None:
        if seconds >= self._remaining():
            raise _FetchFailure("run_budget")
        if seconds > 0:
            self.sleep(seconds)

    def _retry_after(self, value: str | None) -> float:
        if not value:
            return 0
        try:
            seconds = int(value)
        except ValueError:
            try:
                timestamp = parsedate_to_datetime(value)
                if timestamp.tzinfo is None:
                    return 0
                seconds = (timestamp - utc(self._now())).total_seconds()
            except (ValueError, TypeError, OverflowError):
                return 0
        return max(0, seconds)

    def _fetch(self, cik: str, url: str, validator: Callable[[bytes], object], *,
               accession: str | None = None):
        for attempt in range(self.scope.retries + 1):
            retry_delay, retryable = 0.0, False
            try:
                if self.circuit["cooldown_until"] is not None:
                    if utc(self._now()) < utc(self.circuit["cooldown_until"]):
                        raise _FetchFailure("cooldown")
                    self.circuit = {"consecutive_failures": 0, "cooldown_until": None}
                delay = 0 if self.last_request is None else max(
                    0, self.scope.interval_seconds - (self.monotonic() - self.last_request))
                self._wait(delay)
                requested = self._now()
                self.last_request = self.monotonic()
                with self.client.stream(
                    "GET", url,
                    headers={"User-Agent": self._user_agent, "Accept-Encoding": "identity"},
                    follow_redirects=False,
                    timeout=min(self.scope.timeout_seconds, self._remaining()),
                ) as response:
                    status = response.status_code
                    retry_delay = self._retry_after(response.headers.get("Retry-After"))
                    if status != 200:
                        code = ("http_403" if status == 403 else "http_429" if status == 429
                                else "http_5xx" if 500 <= status <= 599 else "http_4xx")
                        retryable = status == 429 or 500 <= status <= 599
                        raise _FetchFailure(code)
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise _FetchFailure("invalid_response")
                    chunks, size = [], 0
                    # Do not coalesce tiny chunks: a trickling response must
                    # hit the run deadline even if it never fills a buffer.
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > self.scope.max_bytes:
                            raise _FetchFailure("size_limit")
                        if self._remaining() <= 0:
                            raise _FetchFailure("run_budget")
                        chunks.append(chunk)
                    raw = b"".join(chunks)
                    length = response.headers.get("content-length")
                    if length is not None and (not length.isdigit() or int(length) != len(raw)):
                        raise _FetchFailure("invalid_response")
                received = self._now()
                try:
                    parsed = validator(raw)
                except (ValueError, TypeError, KeyError, RecursionError):
                    raise _FetchFailure("invalid_response") from None
                verified = self._now()
                if self._remaining() <= 0:
                    raise _FetchFailure("run_budget")
                self.circuit = {"consecutive_failures": 0, "cooldown_until": None}
                return raw, parsed, requested, received, verified
            except httpx.DecodingError:
                code = "invalid_response"
            except httpx.TransportError as exc:
                code = "timeout" if isinstance(exc, httpx.TimeoutException) else "network"
                retryable = True
            except _FetchFailure as exc:
                code = exc.code
            self._failure(cik, code, accession, count=code not in {"cooldown", "run_budget"})
            if retry_delay:
                self._cooldown(retry_delay)
            if not retryable or attempt == self.scope.retries or code == "http_403":
                return None
            if self.circuit["consecutive_failures"] >= 3:
                return None
            delay = max(2 ** attempt, retry_delay)
            try:
                self._wait(delay)
            except _FetchFailure:
                return None
            # A short Retry-After may be honored inside this same bounded run.
            if retry_delay and retry_delay < 900:
                self.circuit["cooldown_until"] = None
        return None

    def begin(self, run_id: str, source_commit: str):
        _require(not self.used, "collector instance is single-use")
        self.used = True
        _require(isinstance(run_id, str)
                 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", run_id) is not None,
                 "invalid run ID")
        _require(isinstance(source_commit, str)
                 and re.fullmatch(r"[a-f0-9]{40}", source_commit) is not None,
                 "invalid source commit")
        history = self.store.verify()
        _require(all(run["manifest"]["run_id"] != run_id for run in history), "duplicate run ID")
        self.started_monotonic = self.monotonic()
        started = self._now()
        if history:
            _require(utc(history[-1]["finalized_at"]) <= utc(started), "cross-run clock reversal")
            view = self.store.query(history[-1]["finalized_at"])
            kinds = {self.source_kind(None), self.source_kind("document")}
            _require(all(item["source_kind"] in kinds for item in view["observations"]),
                     "collector source stores must remain separate")
            _require(all(failure.get("source_kind", "listing") in kinds
                         for run in view["runs"] + view["recovered_runs"]
                         for failure in run["manifest"]["failures"]),
                     "collector failure states must remain separate")
            self.circuit = dict(history[-1]["manifest"]["circuit"])
        return history, started

    def finish(self, run_id, source_commit, history, started, observations, skipped,
               selection=None):
        manifest = {
            "schema_version": 1, "run_id": run_id, "source_commit": source_commit,
            "config_sha256": self.scope.sha256, "started_at": started, "ended_at": self._now(),
            "previous_run_sha256": history[-1]["sha256"] if history else None,
            "observations": [], "failures": self.failures,
            "coverage": {"succeeded": len(observations), "failed": len(self.failures),
                         "skipped": skipped},
            "circuit": self.circuit,
        }
        if selection is not None:
            manifest["selection"] = selection
        digest = self.store.publish(manifest, observations)
        uncollected = skipped if selection is None else selection["limit_skipped"]
        return {"run_id": run_id, "run_sha256": digest,
                "complete": not self.failures and uncollected == 0,
                "historical_completeness": "unknown", "coverage": manifest["coverage"]}

    def collect(self, *, run_id: str, source_commit: str) -> dict:
        history, started = self.begin(run_id, source_commit)
        observations, skipped, documents = [], 0, 0

        def record(cik, accession, kind, url, fetched, claims):
            raw, _, requested, received, verified = fetched
            digest = self.store.blobs.put(raw)
            observations.append(Observation(
                str(uuid4()), cik, accession, kind, url, digest,
                requested, received, verified, claims))

        for cik in self.scope.ciks:
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            fetched = self._fetch(
                cik, url, lambda raw, issuer=cik: parse_listing(raw, issuer, self.scope.forms))
            if fetched is None:
                continue
            record(cik, None, "listing", url, fetched, {})
            name, candidates = fetched[1]
            selected = candidates[:max(0, self.scope.max_documents - documents)]
            skipped += len(candidates) - len(selected)
            for row in selected:
                accession = row["accessionNumber"]
                url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                       f"{accession.replace('-', '')}/{row['primaryDocument']}")
                documents += 1
                fetched = self._fetch(
                    cik, url, lambda raw, issuer=cik, company=name:
                    validate_primary(raw, issuer, company), accession=accession)
                if fetched is not None:
                    claims = {"acceptance_datetime": row["acceptanceDateTime"],
                              "filing_date": row["filingDate"], "report_date": row["reportDate"],
                              "form": row["form"], "primary_document": row["primaryDocument"]}
                    record(cik, accession, "primary", url, fetched, claims)
        return self.finish(run_id, source_commit, history, started, observations, skipped)
