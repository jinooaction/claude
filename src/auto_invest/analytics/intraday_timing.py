"""Local recorded observation times; never completion, broker time, or authority."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

DETAILS = (
    "bar_start_utc", "model_bar_end_utc", "runtime_observed_at_utc",
    "status_published_at_utc", "runtime_observation_lag_seconds",
    "status_publication_lag_seconds", "runtime_observation_within_90s", "event_hash",
)
BASE = dict(schema=1, scope="DIAGNOSTIC_TIMING",
            source_integrity_scope="LATEST_RECORD_LOCAL_LINK", authority_assessed=False,
            collection_times_assessed=False, completion_time_assessed=False,
            provider_publication_assessed=False)
REASONS = {"RECORD_UNAVAILABLE", "READER_BUSY", "NO_RECORDED_BAR"}


def require(value):
    if not value:
        raise ValueError("TIMING_RECORD_INVALID")


def _utc(value):
    require(isinstance(value, str) and len(value) <= 40)
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.utcoffset() == timedelta(0))
    return result


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _hash(value):
    return "sha256:" + hashlib.sha256(_encoded(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def _json(value):
    def invalid(_):
        raise ValueError("TIMING_RECORD_INVALID")
    return json.loads(value, object_pairs_hook=_pairs, parse_constant=invalid)


def unavailable(reason="RECORD_UNAVAILABLE"):
    require(reason in REASONS)
    return dict(BASE, status="UNAVAILABLE", reason=reason,
                **{key: None for key in DETAILS})


def project_timing(event, status, event_hash):
    start_text, observed_text = event["timestamp"], event["observed"]
    published_text = status["observed_at_utc"]
    start, observed, published = map(_utc, (start_text, observed_text, published_text))
    end = start + timedelta(minutes=5)
    require(start.second == start.microsecond == 0 and start.minute % 5 == 0
            and end <= observed <= published and start_text == status["last_bar"]
            and event["state"]["last_bar"] == start_text)
    require(isinstance(event_hash, str) and re.fullmatch("sha256:[0-9a-f]{64}", event_hash))
    lag = (observed - end).total_seconds()
    return dict(BASE, status="RECORDED", reason="RECORDED_OBSERVATION_ONLY",
                bar_start_utc=start_text,
                model_bar_end_utc=end.isoformat().replace("+00:00", "Z"),
                runtime_observed_at_utc=observed_text,
                status_published_at_utc=published_text,
                runtime_observation_lag_seconds=lag,
                status_publication_lag_seconds=(published - end).total_seconds(),
                runtime_observation_within_90s=lag <= 90, event_hash=event_hash)


def validate_timing(value, status):
    require(isinstance(value, dict) and set(value) == set(BASE) | set(DETAILS) | {
        "status", "reason"})
    require(type(value["schema"]) is int and value["schema"] == 1)
    for key, expected in BASE.items():
        require(type(value[key]) is type(expected) and value[key] == expected)
    if value["status"] == "UNAVAILABLE":
        require(value["reason"] in REASONS and all(value[k] is None for k in DETAILS))
    else:
        require(value["status"] == "RECORDED")
        expected = project_timing(dict(timestamp=value["bar_start_utc"],
                                       observed=value["runtime_observed_at_utc"],
                                       state=dict(last_bar=value["bar_start_utc"])),
                                  status, value["event_hash"])
        require(value == expected and type(value["runtime_observation_within_90s"]) is bool)
        for key in ("runtime_observation_lag_seconds", "status_publication_lag_seconds"):
            require(type(value[key]) in {int, float} and math.isfinite(value[key]))
    require(len(_encoded(value)) <= 4096)
    return dict(value)


@contextmanager
def timing_lock(root):
    descriptor = None
    acquired = False
    try:
        root = Path(root)
        require(root.is_dir() and not root.is_symlink())
        descriptor = os.open(root / "service.lock", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        require(stat.S_ISREG(os.fstat(descriptor).st_mode))
        fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        acquired = True
    except (OSError, ValueError):
        pass
    try:
        yield acquired
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_timing(root, status):
    """Caller holds the existing diagnostic writer's shared lock."""
    try:
        identity = status["identity"]
        require(isinstance(identity, str) and re.fullmatch("[0-9a-f]{64}", identity))
        if status.get("last_bar") is None:
            return unavailable("NO_RECORDED_BAR")
        epoch = Path(root) / identity
        path = epoch / "paper.db"
        require(epoch.is_dir() and not epoch.is_symlink()
                and path.is_file() and not path.is_symlink()
                and not path.with_name("paper.db-wal").exists()
                and not path.with_name("paper.db-shm").exists())
        before = path.stat()
        require(stat.S_ISREG(before.st_mode))
        deadline = time.monotonic() + 2
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1",
                               uri=True, timeout=2)
        try:
            conn.row_factory = sqlite3.Row
            conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            conn.execute("PRAGMA query_only=ON")
            require(conn.execute("PRAGMA user_version").fetchone()[0] == 181)
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            require(tables == {"intraday_meta", "intraday_events"})
            meta_rows = conn.execute(
                "SELECT length(CAST(identity AS BLOB)) FROM intraday_meta LIMIT 2").fetchall()
            require(len(meta_rows) == 1 and 0 < meta_rows[0][0] <= 16384)
            meta = _json(conn.execute("SELECT identity FROM intraday_meta LIMIT 1").fetchone()[0])
            require(meta["mode"] == "forward" and meta["synthetic"] is False
                    and meta["provider"] == "kis-nasdaq-partial-unadjusted")
            rows = conn.execute("SELECT id,timestamp,previous_hash,hash,"
                                "length(CAST(payload AS BLOB)) AS size "
                                "FROM intraday_events ORDER BY id DESC LIMIT 2").fetchall()
            require(rows and type(status["processed_bars"]) is int
                    and status["processed_bars"] == conn.execute(
                        "SELECT COUNT(*) FROM intraday_events").fetchone()[0])
            row = rows[0]
            require(0 < row["size"] <= 1024 * 1024)
            if len(rows) == 1:
                require(row["id"] == 1 and row["previous_hash"] == "genesis")
            else:
                require(row["id"] == rows[1]["id"] + 1
                        and row["previous_hash"] == rows[1]["hash"]
                        and _utc(rows[1]["timestamp"]) < _utc(row["timestamp"]))
            event = _json(conn.execute("SELECT payload FROM intraday_events WHERE id=?",
                                       (row["id"],)).fetchone()[0])
            require(row["timestamp"] == event["timestamp"]
                    and row["hash"] == _hash([row["previous_hash"], event]))
            report = project_timing(event, status, row["hash"])
        finally:
            conn.close()
        after = path.stat()
        require(all(getattr(before, key) == getattr(after, key) for key in (
            "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")) and time.monotonic() <= deadline)
        return report
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, OverflowError, RecursionError):
        return unavailable()


def read_timing(root, status):
    with timing_lock(root) as acquired:
        return _read_timing(root, status) if acquired else unavailable("READER_BUSY")


def read_timed_status(root, now, reader):
    """Same status reader, plus a coherent price-free local timing projection."""
    with timing_lock(root) as acquired:
        status = reader(root, now)
        timing = _read_timing(root, status) if acquired else unavailable("READER_BUSY")
        return dict(status, timing=timing)
