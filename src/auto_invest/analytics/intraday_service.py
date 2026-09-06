"""Private diagnostic supervisor state. Never a trading/promotion authority."""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from auto_invest.market_data.intraday import DataError, digest, encode, iso, utc

BLOCKERS = [
    "HISTORY_756_SESSIONS_REQUIRED",
    "HISTORICAL_ACCEPTANCE_REQUIRED",
    "QUALIFIED_FORWARD_60_SESSIONS_REQUIRED",
    "PROVIDER_EXECUTION_PARITY_REQUIRED",
    "LIVE_ADAPTER_NOT_IMPLEMENTED",
    "PRODUCTION_FILLS_NOT_VERIFIED",
]
FIELDS = {
    "status",
    "reason",
    "identity",
    "processed_bars",
    "last_bar",
    "simulated_fills",
    "open_quantity",
    "halt_reasons",
    "archived_session",
    "archive_status",
}
STATES = {"WAIT_SESSION", "DIAGNOSTIC_PAPER", "ENTRY_HALTED", "FAILED"}


def service_identity(sources: list[Path]) -> str:
    return digest(encode([digest(p.read_bytes()) for p in sources])).split(":")[1]


@contextmanager
def busy_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(root / "service.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            yield True
    finally:
        os.close(descriptor)


def publish(root: Path, result: dict, now: datetime) -> dict:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = {k: v for k, v in result.items() if k in FIELDS}
    result.update(
        schema_version="1.0",
        observed_at_utc=iso(now),
        orders_submitted=0,
        live_eligible=False,
        forward_promotion_eligible=False,
        qualified_forward_sessions=0,
        blockers=BLOCKERS,
    )
    temporary = root / ("status-" + uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encode(result))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, root / "status.json")
    return result


def read_service_status(root: Path, now: datetime) -> dict:
    path = root / "status.json"
    unavailable = dict(orders_submitted=0, live_eligible=False, forward_promotion_eligible=False)
    if path.is_symlink():
        return dict(unavailable, status="INVALID_STATUS")
    if not path.exists():
        return dict(unavailable, status="NOT_STARTED")
    try:
        if path.stat().st_size > 16000:
            raise ValueError
        data = json.loads(path.read_text())
        if (
            data["schema_version"] != "1.0"
            or data["status"] not in STATES
            or data["orders_submitted"] != 0
            or data["live_eligible"] is not False
            or data["forward_promotion_eligible"] is not False
            or data["qualified_forward_sessions"] != 0
            or data["blockers"] != BLOCKERS
            or set(data)
            - (
                FIELDS
                | {
                    "schema_version",
                    "observed_at_utc",
                    "orders_submitted",
                    "live_eligible",
                    "forward_promotion_eligible",
                    "qualified_forward_sessions",
                    "blockers",
                }
            )
        ):
            raise ValueError
        age = (now - utc(data["observed_at_utc"])).total_seconds()
        if age < 0:
            raise ValueError
        if age > 180:
            data["last_status"] = data["status"]
            data["status"] = "STALE"
        return dict(data, age_seconds=round(age, 1))
    except (OSError, KeyError, TypeError, ValueError, DataError):
        return dict(unavailable, status="INVALID_STATUS")
