"""Bounded offline inspection of archived evidence; never grants trading authority."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

MAX_BYTES = 10 * 1024 * 1024
PROFILE = "cc-nutch16-post-response-v1"


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    _require(len(raw) <= MAX_BYTES, "input size limit exceeded")
    return raw


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON field")
        result[key] = value
    return result


def _fields(value: object, expected: set[str]) -> dict:
    _require(isinstance(value, dict), "expected object")
    _require(set(value) == expected, "unexpected or missing fields")
    return value


def load_manifest(path: Path) -> dict:
    """Read bounded JSON, rejecting ambiguous keys and non-standard constants."""
    def invalid_constant(_: str) -> None:
        raise ValueError("non-standard JSON constant")

    try:
        result = json.loads(
            _read_bounded(path).decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=invalid_constant,
        )
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON encoding or nesting") from exc
    result = _fields(result, {"schema_version", "profile", "artifacts", "index", "event"})
    _require(type(result["schema_version"]) is int and result["schema_version"] == 1,
             "unsupported schema version")
    _require(result["profile"] == PROFILE, "unsupported provider profile")
    artifacts = _fields(result["artifacts"], {"response", "metadata", "warcinfo"})
    for artifact in artifacts.values():
        _fields(artifact, {"path", "sha256"})
        _require(isinstance(artifact["path"], str) and bool(artifact["path"]),
                 "invalid artifact path")
        _require(isinstance(artifact["sha256"], str)
                 and re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"]) is not None,
                 "invalid artifact digest")
    _fields(result["index"], {"url", "timestamp", "digest"})
    _fields(result["event"], {
        "issuer_cik", "kind", "event_date", "report_period_end", "evidence_quotes",
    })
    return result


def _headers(raw: bytes, *, http: bool = False) -> dict[str, str]:
    try:
        lines = raw.decode("utf-8").split("\r\n")
    except UnicodeError as exc:
        raise ValueError("invalid header encoding") from exc
    result = {}
    for line in lines:
        name, separator, value = line.partition(":")
        _require(bool(separator) and re.fullmatch(r"[A-Za-z0-9-]+", name) is not None,
                 "invalid header field")
        name = name.lower()
        # Repeated Set-Cookie is legal HTTP and irrelevant to offline evidence.
        # Identity, content framing, and all WARC fields remain single-valued.
        _require(name not in result or (http and name == "set-cookie"),
                 "duplicate header field")
        _require(all(ord(char) >= 32 and ord(char) != 127 for char in value),
                 "invalid header control character")
        if not (http and name == "set-cookie"):
            result[name] = value.strip()
    return result


def _utc(value: str) -> datetime:
    _require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is not None,
             "invalid WARC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _record_id(value: str) -> None:
    _require(value.startswith("<urn:uuid:") and value.endswith(">"), "invalid record ID")
    try:
        canonical = str(UUID(value[10:-1]))
    except ValueError as exc:
        raise ValueError("invalid record UUID") from exc
    _require(value[10:-1] == canonical, "noncanonical record UUID")


def _sha1(value: bytes) -> str:
    return base64.b32encode(hashlib.sha1(value).digest()).decode("ascii")


@dataclass(frozen=True)
class WarcRecord:
    """One verified gzip member containing exactly one framed WARC record."""

    headers: dict[str, str]
    block: bytes
    compressed_sha256: str
    uncompressed_sha256: str


def read_record(path: Path, expected_sha256: str, expected_type: str) -> WarcRecord:
    raw = _read_bounded(path)
    fingerprint = hashlib.sha256(raw).hexdigest()
    _require(fingerprint == expected_sha256, "artifact digest mismatch")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        decoded = decoder.decompress(raw, MAX_BYTES + 1)
    except zlib.error as exc:
        raise ValueError("invalid gzip member") from exc
    _require(len(decoded) <= MAX_BYTES, "expanded size limit exceeded")
    _require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
             "incomplete gzip or extra member/trailing bytes")
    header, separator, remainder = decoded.partition(b"\r\n\r\n")
    _require(bool(separator) and header.startswith(b"WARC/1.0\r\n"),
             "unsupported WARC framing")
    headers = _headers(header[len(b"WARC/1.0\r\n"):])
    required = {"warc-type", "warc-date", "warc-record-id", "content-length", "content-type"}
    _require(required <= headers.keys(), "missing WARC fields")
    _require(headers["warc-type"] == expected_type, "unexpected WARC type")
    _utc(headers["warc-date"])
    _record_id(headers["warc-record-id"])
    length = headers["content-length"]
    _require(re.fullmatch(r"0|[1-9][0-9]{0,8}", length) is not None,
             "invalid WARC content length")
    size = int(length)
    _require(len(remainder) == size + 4 and remainder[size:] == b"\r\n\r\n",
             "WARC length or record terminator mismatch")
    block = remainder[:size]
    if "warc-block-digest" in headers:
        _require(headers["warc-block-digest"] == "sha1:" + _sha1(block),
                 "WARC block digest mismatch")
    return WarcRecord(headers, block, fingerprint, hashlib.sha256(decoded).hexdigest())


def _url(value: object) -> None:
    _require(isinstance(value, str) and not any(char.isspace() for char in value),
             "invalid URL")
    parsed = urlsplit(value)
    _require(parsed.scheme in {"http", "https"} and bool(parsed.hostname)
             and parsed.username is None and parsed.password is None and not parsed.fragment,
             "unsupported URL")
    _ = parsed.port


def _date(value: object) -> None:
    _require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None,
             "invalid event date")
    date.fromisoformat(value)


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden.append(tag)

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _now() -> datetime:
    return datetime.now(UTC)


def _warc_fields(block: bytes) -> dict[str, str]:
    # The final field line has CRLF. Some exporter records additionally include
    # an empty line *inside* Content-Length; framing was checked separately.
    _require(block.endswith(b"\r\n"), "invalid fields terminator")
    return _headers(block.removesuffix(b"\r\n").removesuffix(b"\r\n"))


def inspect_manifest(path: Path) -> dict:
    """Validate linked evidence and report conditional provider timing assumptions."""
    started = _now()
    manifest = load_manifest(path)
    index, event = manifest["index"], manifest["event"]
    _url(index["url"])
    _require(isinstance(index["timestamp"], str)
             and re.fullmatch(r"\d{14}", index["timestamp"]) is not None,
             "invalid index timestamp")
    timestamp = datetime.strptime(index["timestamp"], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    _require(isinstance(index["digest"], str)
             and re.fullmatch(r"[A-Z2-7]{32}", index["digest"]) is not None,
             "invalid index digest")
    _require(isinstance(event["issuer_cik"], str)
             and re.fullmatch(r"[0-9]{10}", event["issuer_cik"]) is not None,
             "invalid issuer CIK")
    _require(event["kind"] in ("reported", "scheduled"), "invalid event kind")
    _date(event["event_date"])
    if event["report_period_end"] is not None:
        _date(event["report_period_end"])
    quotes = event["evidence_quotes"]
    _require(isinstance(quotes, list) and bool(quotes)
             and all(isinstance(quote, str) and bool(quote.strip()) for quote in quotes),
             "invalid evidence quotes")
    records = {
        name: read_record(path.parent / item["path"], item["sha256"], name)
        for name, item in manifest["artifacts"].items()
    }
    response, metadata, warcinfo = (records[key] for key in ("response", "metadata", "warcinfo"))
    response_headers = response.headers
    for record in (response, metadata):
        _require({"warc-target-uri", "warc-warcinfo-id"} <= record.headers.keys(),
                 "missing record links")
        _require(record.headers["warc-target-uri"] == index["url"], "target URL mismatch")
        _require(_utc(record.headers["warc-date"]) == timestamp, "index timestamp mismatch")
        _require(record.headers["warc-warcinfo-id"] == warcinfo.headers["warc-record-id"],
                 "warcinfo link mismatch")
    _require(len({record.headers["warc-record-id"] for record in records.values()}) == 3,
             "duplicate record identities")
    _require(metadata.headers.get("warc-concurrent-to") == response_headers["warc-record-id"],
             "metadata response link mismatch")
    for record in (metadata, warcinfo):
        _require(record.headers["content-type"] == "application/warc-fields",
                 "unsupported fields media type")
    information = _warc_fields(warcinfo.block)
    _require(information.get("software") == "Nutch 1.6 (CC)/CC WarcExport 1.0",
             "provider software profile mismatch")
    meta = _warc_fields(metadata.block)
    duration = meta.get("fetchtimems", "")
    _require(re.fullmatch(r"0|[1-9][0-9]{0,18}", duration) is not None,
             "invalid fetch duration")
    _require(response_headers["content-type"].replace(" ", "").lower()
             == "application/http;msgtype=response", "unsupported response media type")
    _require("warc-block-digest" in response_headers, "missing response block digest")
    http_header, separator, body = response.block.partition(b"\r\n\r\n")
    status, line_separator, header_fields = http_header.partition(b"\r\n")
    _require(bool(separator) and bool(line_separator)
             and re.fullmatch(rb"HTTP/1\.[01] 200(?: [^\r\n]*)?", status) is not None,
             "unsupported HTTP response")
    http = _headers(header_fields, http=True)
    media = http.get("content-type", "").lower().replace(" ", "")
    _require(media in {"text/html", "text/html;charset=utf-8", 'text/html;charset="utf-8"'},
             "unsupported body media type or encoding")
    _require("transfer-encoding" not in http, "unsupported transfer encoding")
    _require(response_headers.get("warc-payload-digest") == "sha1:" + _sha1(body)
             and index["digest"] == _sha1(body), "payload digest mismatch")
    # This producer stores decoded payloads; retained HTTP content-encoding/length
    # fields describe the wire response, not necessarily these archived bytes.
    text = _Text()
    try:
        text.feed(body.decode("utf-8-sig"))
        text.close()
    except UnicodeError as exc:
        raise ValueError("unsupported body encoding") from exc
    normalized = " ".join(" ".join(text.parts).split())
    _require(all(" ".join(quote.split()) in normalized for quote in quotes),
             "evidence quote absent from visible source text")
    finished = _now()
    _require(started.utcoffset() == timedelta(0) and finished.utcoffset() == timedelta(0)
             and finished >= started, "invalid local inspection interval")
    upper = timestamp + timedelta(seconds=1)
    return {
        "schema_version": 1,
        "profile": PROFILE,
        "local_inspection": {
            "started_at": started.isoformat(), "finished_at": finished.isoformat(),
        },
        "artifacts": {
            name: {"compressed_sha256": record.compressed_sha256,
                   "uncompressed_sha256": record.uncompressed_sha256,
                   "record_id": record.headers["warc-record-id"]}
            for name, record in records.items()
        },
        "index": index,
        "event": event,
        "payload_sha256": hashlib.sha256(body).hexdigest(),
        "links_verified": True,
        "quotes_present": True,
        "conditional_provider_interval": {
            "post_response_lower_inclusive": timestamp.isoformat(),
            "post_response_upper_exclusive": upper.isoformat(),
            "conditional_use_not_before": upper.isoformat(),
            "fetch_time_ms": int(duration),
            "duration_added_to_timestamp": False,
        },
        "warc_truncated": response_headers.get("warc-truncated"),
        "unverified": [
            "exact_deployed_crawler_commit", "provider_clock_accuracy",
            "complete_original_document", "event_processing_latency",
            "issuer_event_semantics", "symbol_lineage",
        ],
        "strategy_admitted": False,
        "live_eligible": False,
    }


def write_inspection(input_path: Path, output_path: Path) -> dict:
    result = inspect_manifest(input_path)
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with output_path.open("x", encoding="utf-8") as handle:
        handle.write(serialized)
    return result
