"""Fixed, bounded research-only HF raw access. No price or trading evaluation."""

import hashlib
import json
import math
import os
import re
import signal
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

SCOPE = "HF_RAW_PILOT_V1"
BASE = "https://api.hfdatalibrary.com/v1"
SYMBOLS = ("AMZN", "NVDA")
RAW_LIMIT = 128 * 1024 * 1024
CATALOGUE_LIMIT = 4 * 1024 * 1024
SOURCE_BREAK = "PiTrading/IEX March 2022; not execution parity"
RESULT_CODES = {
    "COMPLETE", "HISTORY_COOLDOWN", "HISTORY_UNVERIFIED", "MISSING_KEY", "CIRCUIT_OPEN",
    "INVALID_CONTENT_TYPE", "INVALID_LENGTH", "SOURCE_TOO_LARGE", "PRIVATE_RESPONSE_REJECTED",
    "LENGTH_MISMATCH", "INVALID_CATALOGUE", "PILOT_SYMBOL_MISSING", "INVALID_PARQUET",
    "INVALID_PARQUET_SCHEMA", "EMPTY_PARQUET", "HTTP_TRANSIENT", "HTTP_ACCESS_REFUSED",
    "NETWORK_OR_TIMEOUT", "INVALID_SOURCE_OR_STORAGE", "RETRY_EXHAUSTED", "RATE_LIMIT_DEFERRED",
    "RUN_DEADLINE",
}


def utc(value: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("INVALID_TIME")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("INVALID_TIME")
    return parsed.astimezone(UTC)


def initial_state() -> dict:
    return {"schema_version": 1, "scope": SCOPE, "complete": True,
            "catalogue": {"failures": 0, "blocked_until": None},
            "raw": {"failures": 0, "blocked_until": None}}


def validate_state(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != set(initial_state()):
        raise ValueError("INVALID_STATE")
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["scope"] != SCOPE or value["complete"] is not True):
        raise ValueError("INVALID_STATE")
    for name in ("catalogue", "raw"):
        item = value[name]
        if not isinstance(item, dict) or set(item) != {"failures", "blocked_until"}:
            raise ValueError("INVALID_STATE")
        if type(item["failures"]) is not int or not 0 <= item["failures"] <= 3:
            raise ValueError("INVALID_STATE")
        if item["blocked_until"] is not None:
            utc(item["blocked_until"])
        if item["failures"] == 3 and item["blocked_until"] is None:
            raise ValueError("INVALID_STATE")
    return json.loads(json.dumps(value))


def blocked_state(until: datetime) -> dict:
    value = initial_state()
    for name in ("catalogue", "raw"):
        value[name] = {"failures": 3, "blocked_until": until.isoformat()}
    return value


def restore_state(history: dict, previous: dict | None, now: datetime) -> tuple[dict, str]:
    """Only a successful trusted history query proves an empty first-run history."""
    if (not isinstance(history, dict)
            or set(history) != {"schema_version", "run_attempt", "previous"}
            or type(history["schema_version"]) is not int or history["schema_version"] != 1
            or type(history["run_attempt"]) is not int or history["run_attempt"] < 1):
        raise ValueError("INVALID_HISTORY")
    if history["run_attempt"] != 1:
        return blocked_state(now + timedelta(seconds=900)), "HISTORY_UNVERIFIED"
    prior = history["previous"]
    if prior is None:
        if previous is not None:
            raise ValueError("INVALID_HISTORY")
        return initial_state(), "FIRST_RUN_VERIFIED"
    if (not isinstance(prior, dict) or set(prior) != {"id", "status", "updated_at"}
            or type(prior["id"]) is not int or prior["id"] <= 0):
        raise ValueError("INVALID_HISTORY")
    ended = utc(prior["updated_at"])
    if prior["status"] != "completed" or ended > now:
        return blocked_state(now + timedelta(seconds=900)), "HISTORY_UNVERIFIED"
    if previous is not None:
        try:
            return validate_state(previous), "RESTORED"
        except (ValueError, TypeError, OverflowError):
            pass
    until = ended + timedelta(seconds=900)
    return blocked_state(until), ("HISTORY_COOLDOWN" if until > now
                                  else "RECOVERED_UNKNOWN_HISTORY")


@contextmanager
def wall_timeout(seconds: float):
    """Interrupt even a socket drip; read-timeout alone only bounds idle gaps."""
    if threading.current_thread() is not threading.main_thread() or seconds <= 0:
        raise ValueError("UNSUPPORTED_TIMER")
    old_handler = signal.getsignal(signal.SIGALRM)

    def expired(signum, frame):
        raise TimeoutError("REQUEST_DEADLINE")

    signal.signal(signal.SIGALRM, expired)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    started = time.monotonic()
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0]:
            remaining = old_timer[0] - (time.monotonic() - started)
            signal.setitimer(signal.ITIMER_REAL, max(remaining, 0.000001), old_timer[1])


class Clock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)

    @staticmethod
    def utcnow():
        return datetime.now(UTC)


class Refusal(Exception):
    def __init__(self, code: str, retryable=False, until=None):
        self.code = code
        self.retryable = retryable
        self.until = until


def retry_after(value: str | None, now: datetime) -> datetime:
    conservative = now + timedelta(seconds=900)
    try:
        if value and re.fullmatch(r"[0-9]{1,20}", value):
            requested = now + timedelta(seconds=int(value))
        else:
            requested = parsedate_to_datetime(value or "")
            if requested.tzinfo is None:
                raise ValueError("INVALID_RETRY_AFTER")
            requested = requested.astimezone(UTC)
        return max(conservative, requested)
    except (ValueError, TypeError, OverflowError):
        # Unparseable/overflowing directions cannot justify an early retry.
        return datetime.max.replace(tzinfo=UTC)


def validate_catalogue(data: bytes) -> int:
    value = json.loads(data)
    if (not isinstance(value, dict) or set(value) != {"count", "symbols"}
            or type(value["count"]) is not int or not 1 <= value["count"] <= 10000
            or not isinstance(value["symbols"], list)
            or value["count"] != len(value["symbols"])):
        raise Refusal("INVALID_CATALOGUE")
    tickers = set()
    for row in value["symbols"]:
        if (not isinstance(row, dict) or set(row) != {"ticker", "size_bytes", "last_modified"}
                or not isinstance(row["ticker"], str)
                or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,14}", row["ticker"])
                or row["ticker"] in tickers or type(row["size_bytes"]) is not int
                or not 0 < row["size_bytes"] <= 1024 ** 4):
            raise Refusal("INVALID_CATALOGUE")
        utc(row["last_modified"])
        tickers.add(row["ticker"])
    if not set(SYMBOLS) <= tickers:
        raise Refusal("PILOT_SYMBOL_MISSING")
    return value["count"]


def parquet_rows(path: Path) -> int:
    import duckdb

    with path.open("rb") as source:
        if source.read(4) != b"PAR1":
            raise Refusal("INVALID_PARQUET")
        source.seek(-4, 2)
        if source.read(4) != b"PAR1":
            raise Refusal("INVALID_PARQUET")
    with duckdb.connect(":memory:") as connection:
        connection.execute("SET threads=1")
        schema = connection.execute("DESCRIBE SELECT * FROM read_parquet(?) LIMIT 0",
                                    [str(path)]).fetchall()
        if [row[0] for row in schema] != ["datetime", "Open", "High", "Low", "Close",
                                         "Volume", "source"]:
            raise Refusal("INVALID_PARQUET_SCHEMA")
        if (not schema[0][1].startswith("TIMESTAMP")
                or [row[1] for row in schema[1:]] != ["DOUBLE"] * 4 + ["BIGINT", "VARCHAR"]):
            raise Refusal("INVALID_PARQUET_SCHEMA")
        rows = connection.execute("SELECT num_rows FROM parquet_file_metadata(?)",
                                  [str(path)]).fetchone()[0]
        if type(rows) is not int or rows <= 0:
            raise Refusal("EMPTY_PARQUET")
        return rows


def write_json(path: Path, value: dict):
    if path.exists() or path.is_symlink():
        raise ValueError("NEW_OUTPUT_REQUIRED")
    partial = path.with_suffix(path.suffix + ".partial")
    try:
        with partial.open("x", encoding="utf-8") as target:
            json.dump(value, target, indent=2, sort_keys=True, allow_nan=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        partial.rename(path)
    finally:
        partial.unlink(missing_ok=True)


def stage_output(source: Path, destination: Path):
    """Only manifest-listed, rehashed finalized files enter the recovery artifact."""
    if (source.resolve() != source.absolute() or destination.resolve() != destination.absolute()
            or destination.exists()):
        raise ValueError("NEW_OUTPUT_REQUIRED")
    manifest = source / "manifest.json"
    if manifest.is_symlink() or manifest.stat().st_size > 16384:
        raise ValueError("INVALID_MANIFEST")
    value = json.loads(manifest.read_text())
    expected = {"schema_version", "scope", "result", "source_commit", "restore_reason", "files",
                "returns_evaluated", "historical_universe_verified", "source_parity_verified",
                "live_eligible", "orders_submitted", "source_break", "completed_at"}
    if (set(value) != expected or type(value["schema_version"]) is not int
            or value["schema_version"] != 1 or value["scope"] != SCOPE
            or value["result"] not in RESULT_CODES or value["live_eligible"] is not False
            or any(value[name] is not False for name in (
                "returns_evaluated", "historical_universe_verified", "source_parity_verified"))
            or type(value["orders_submitted"]) is not int or value["orders_submitted"] != 0
            or value["source_break"] != SOURCE_BREAK
            or value["restore_reason"] not in {
                "FIRST_RUN_VERIFIED", "RESTORED", "HISTORY_COOLDOWN", "HISTORY_UNVERIFIED",
                "RECOVERED_UNKNOWN_HISTORY"}
            or (value["source_commit"] is not None and not re.fullmatch(
                r"[0-9a-f]{40}", value["source_commit"]))
            or not set(value["files"]) <= {"catalogue", *SYMBOLS}):
        raise ValueError("INVALID_MANIFEST")
    utc(value["completed_at"])
    if value["result"] == "COMPLETE" and set(value["files"]) != {"catalogue", *SYMBOLS}:
        raise ValueError("INCOMPLETE_SOURCE")
    for name, receipt in value["files"].items():
        raw = name != "catalogue"
        expected_url = f"{BASE}/bars/{name}?version=raw" if raw else f"{BASE}/symbols"
        if (set(receipt) != {"url", "bytes", "sha256", "observed_at", "rows" if raw else "count"}
                or receipt["url"] != expected_url or type(receipt["bytes"]) is not int
                or not 0 < receipt["bytes"] <= (RAW_LIMIT if raw else CATALOGUE_LIMIT)
                or not re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"])
                or type(receipt["rows" if raw else "count"]) is not int
                or receipt["rows" if raw else "count"] <= 0):
            raise ValueError("INVALID_RECEIPT")
        utc(receipt["observed_at"])
    paths = {"catalogue.json", "manifest.json", "circuit-state.json"}
    paths.update(f"{name}.parquet" for name in value["files"] if name != "catalogue")
    if any(p.name not in paths or p.is_symlink() or not p.is_file() for p in source.iterdir()):
        raise ValueError("UNFINISHED_OUTPUT")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for name, receipt in value["files"].items():
            filename = "catalogue.json" if name == "catalogue" else f"{name}.parquet"
            path = source / filename
            if path.stat().st_size != receipt["bytes"]:
                raise ValueError("SOURCE_CHANGED")
            digest = hashlib.sha256()
            with path.open("rb") as incoming, (destination / filename).open("xb") as outgoing:
                while chunk := incoming.read(64 * 1024):
                    digest.update(chunk)
                    outgoing.write(chunk)
            if digest.hexdigest() != receipt["sha256"]:
                raise ValueError("SOURCE_CHANGED")
        write_json(destination / "manifest.json", value)
    except Exception:
        # The stage is new and unpublished. Prior evidence is never touched.
        for path in destination.iterdir():
            path.unlink()
        destination.rmdir()
        raise


class Collector:
    def __init__(self, output: Path, history: dict, previous: dict | None, *,
                 clock=None, transport=None, raw_limit=RAW_LIMIT, source_commit=None):
        self.clock = clock or Clock()
        self.output = output.absolute()
        if self.output.resolve() != self.output or self.output.exists():
            raise ValueError("NEW_OUTPUT_REQUIRED")
        if not 0 < raw_limit <= RAW_LIMIT:
            raise ValueError("INVALID_LIMIT")
        self.state, self.restore_reason = restore_state(history, previous, self.clock.utcnow())
        self.transport = transport
        self.raw_limit = raw_limit
        self.started = self.clock.monotonic()
        self.last_request = self.started
        self.result = {"schema_version": 1, "scope": SCOPE, "result": "NOT_STARTED",
                       "source_commit": source_commit,
                       "restore_reason": self.restore_reason, "files": {},
                       "returns_evaluated": False, "historical_universe_verified": False,
                       "source_parity_verified": False, "live_eligible": False,
                       "orders_submitted": 0,
                       "source_break": SOURCE_BREAK}

    def remaining(self):
        return 180 - (self.clock.monotonic() - self.started)

    def wait(self, seconds):
        if not math.isfinite(seconds) or seconds >= self.remaining():
            raise Refusal("RUN_DEADLINE")
        if seconds > 0:
            self.clock.sleep(seconds)

    def request(self, client, bucket, key, name):
        item = self.state[bucket]
        if item["blocked_until"] and utc(item["blocked_until"]) > self.clock.utcnow():
            raise Refusal("CIRCUIT_OPEN")
        path = self.output / ("catalogue.json" if bucket == "catalogue" else f"{name}.parquet")
        for attempt in range(3):
            try:
                self.wait(max(0, 1 - (self.clock.monotonic() - self.last_request)))
                self.last_request = self.clock.monotonic()
                with wall_timeout(min(20, self.remaining())):
                    receipt = self.fetch(client, bucket, key, name, path)
                item.update(failures=0, blocked_until=None)
                return receipt
            except Refusal as error:
                failure = error
            except (httpx.HTTPError, TimeoutError):
                failure = Refusal("NETWORK_OR_TIMEOUT", retryable=True)
            except Exception:
                failure = Refusal("INVALID_SOURCE_OR_STORAGE")
            partial = path.with_suffix(path.suffix + ".partial")
            partial.unlink(missing_ok=True)
            item["failures"] = min(3, item["failures"] + 1)
            if not failure.retryable or item["failures"] >= 3:
                item["failures"] = 3
                item["blocked_until"] = max(
                    self.clock.utcnow() + timedelta(seconds=900),
                    failure.until or self.clock.utcnow()).isoformat()
                raise failure
            if attempt < 2:
                self.wait(2 ** attempt)
        raise Refusal("RETRY_EXHAUSTED")

    def fetch(self, client, bucket, key, name, path):
        url = f"{BASE}/symbols" if bucket == "catalogue" else f"{BASE}/bars/{name}?version=raw"
        headers = {"Accept-Encoding": "identity", "User-Agent": "AutoInvestResearch/1.0"}
        if bucket == "raw":
            headers["X-API-Key"] = key
        limit = CATALOGUE_LIMIT if bucket == "catalogue" else self.raw_limit
        with client.stream("GET", url, headers=headers) as response:
            if response.status_code == 429:
                raise Refusal("RATE_LIMIT_DEFERRED", until=retry_after(
                    response.headers.get("retry-after"), self.clock.utcnow()))
            if response.status_code != 200:
                transient = response.status_code in {408, 500, 502, 503, 504}
                raise Refusal("HTTP_TRANSIENT" if transient else "HTTP_ACCESS_REFUSED",
                              retryable=transient)
            content_type = response.headers.get("content-type", "").split(";")[0].strip()
            allowed = {"application/json"} if bucket == "catalogue" else {
                "application/octet-stream", "application/vnd.apache.parquet"}
            encoding = response.headers.get("content-encoding", "identity")
            if content_type not in allowed or encoding != "identity":
                raise Refusal("INVALID_CONTENT_TYPE")
            length = response.headers.get("content-length")
            if length is not None and (not length.isdecimal() or not 0 < int(length) <= limit):
                raise Refusal("INVALID_LENGTH")
            partial = path.with_suffix(path.suffix + ".partial")
            total, pending, digest = 0, b"", hashlib.sha256()
            secret = key.encode() if key else b""
            with partial.open("xb") as target:
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    if self.remaining() <= 0:
                        raise Refusal("RUN_DEADLINE")
                    total += len(chunk)
                    if total > limit:
                        raise Refusal("SOURCE_TOO_LARGE")
                    pending += chunk
                    if secret and secret in pending:
                        raise Refusal("PRIVATE_RESPONSE_REJECTED")
                    keep = len(secret) - 1 if secret else 0
                    safe = pending[:-keep] if keep else pending
                    pending = pending[-keep:] if keep else b""
                    target.write(safe)
                    digest.update(safe)
                target.write(pending)
                digest.update(pending)
            if not total or (length is not None and total != int(length)):
                raise Refusal("LENGTH_MISMATCH")
            receipt = {"url": url, "bytes": total, "sha256": digest.hexdigest(),
                       "observed_at": self.clock.utcnow().isoformat()}
            if bucket == "catalogue":
                receipt["count"] = validate_catalogue(partial.read_bytes())
            else:
                receipt["rows"] = parquet_rows(partial)
            if self.remaining() <= 0:
                raise Refusal("RUN_DEADLINE")
            partial.rename(path)
            return receipt

    def run(self, key: str):
        if not isinstance(key, str) or (key and not re.fullmatch(r"[A-Za-z0-9_.\-]{16,256}", key)):
            raise ValueError("INVALID_KEY_INPUT")
        self.output.mkdir(parents=True, exist_ok=False)
        try:
            with wall_timeout(max(0.000001, self.remaining())):
                if self.restore_reason in {"HISTORY_COOLDOWN", "HISTORY_UNVERIFIED"}:
                    raise Refusal(self.restore_reason)
                with httpx.Client(timeout=20, follow_redirects=False, trust_env=False, verify=True,
                                  transport=self.transport) as client:
                    self.result["files"]["catalogue"] = self.request(client, "catalogue", key, "")
                    if not key:
                        raise Refusal("MISSING_KEY")
                    for ticker in SYMBOLS:
                        self.result["files"][ticker] = self.request(client, "raw", key, ticker)
                self.result["result"] = "COMPLETE"
        except Refusal as error:
            self.result["result"] = error.code
        except Exception:
            self.result["result"] = "INVALID_SOURCE_OR_STORAGE"
        for path in self.output.glob("*.partial"):
            path.unlink()
        self.result["completed_at"] = self.clock.utcnow().isoformat()
        write_json(self.output / "manifest.json", self.result)
        write_json(self.output / "circuit-state.json", validate_state(self.state))
        return self.result
