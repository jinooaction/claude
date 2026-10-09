"""Price-free receipt of the existing restricted diagnostic read, never authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from auto_invest.analytics.intraday_collection_record import validate_collection
from auto_invest.analytics.intraday_timing import validate_timing

SOURCES = (
    "scripts/intraday_runtime.py",
    "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json",
    "src/auto_invest/analytics/intraday_runtime.py",
    "src/auto_invest/analytics/intraday_service.py",
    "src/auto_invest/analytics/intraday_paper_challenger.py",
    "src/auto_invest/market_data/intraday.py",
)
CORE = (
    "schema_version", "scope", "program_readiness", "status", "identity",
    "observed_at_utc", "age_seconds",
    "orders_submitted", "qualified_forward_sessions", "live_eligible",
    "forward_promotion_eligible", "blockers",
)
COUNTERS = ("processed_bars", "simulated_fills", "open_quantity")


class ReceiptError(ValueError):
    pass


def require(value):
    if not value:
        raise ReceiptError("DIAGNOSTIC_RECEIPT_INVALID")


def _utc(value):
    require(isinstance(value, str) and len(value) <= 40)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(result.utcoffset() == timedelta(0))
        return result
    except (ValueError, TypeError):
        raise ReceiptError("DIAGNOSTIC_RECEIPT_INVALID") from None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def build_receipt(raw, *, source_sha, run_id, identity, captured):
    try:
        require(isinstance(raw, str) and len(raw.encode()) <= 65536)
        require(re.fullmatch("[0-9a-f]{40}", source_sha)
                and re.fullmatch("[0-9]{1,20}", run_id)
                and re.fullmatch("[0-9a-f]{64}", identity))
        require(isinstance(captured, datetime) and captured.utcoffset() == timedelta(0))
        lines = [line for line in raw.splitlines() if line]
        require(len(lines) == 4)
        headers = {}
        for line in lines[:3]:
            key, value = line.split("=", 1)
            require(key not in headers)
            headers[key] = value
        require(set(headers) == {"INTRADAY_TIMER", "INTRADAY_SERVICE_RESULT",
                                 "INTRADAY_PRODUCTION_COMMIT"})
        require(headers["INTRADAY_TIMER"] == "active"
                and re.fullmatch("[a-z-]{1,32}", headers["INTRADAY_SERVICE_RESULT"])
                and re.fullmatch("[0-9a-f]{40}", headers["INTRADAY_PRODUCTION_COMMIT"]))
        def nonfinite(_):
            raise ReceiptError("DIAGNOSTIC_RECEIPT_INVALID")
        status = json.loads(lines[-1], object_pairs_hook=_pairs, parse_constant=nonfinite)
        require(isinstance(status, dict) and all(key in status for key in CORE))
        require(status["schema_version"] == "1.1"
                and status.get("source_schema_version", "1.1") == "1.1"
                and status["scope"] == "DIAGNOSTIC_PAPER_SERVICE"
                and status["program_readiness"] == "NOT_ASSESSED"
                and status["status"] in {"WAIT_SESSION", "DIAGNOSTIC_PAPER", "ENTRY_HALTED"}
                and status["identity"] == identity)
        if status["status"] != "WAIT_SESSION":
            require(all(key in status for key in (*COUNTERS, "halt_reasons")))
        for field in (*COUNTERS, "orders_submitted", "qualified_forward_sessions"):
            if field not in status:
                continue
            require(type(status[field]) is int and 0 <= status[field] < 2**63)
        require(status["orders_submitted"] == status["qualified_forward_sessions"] == 0
                and status["live_eligible"] is False
                and status["forward_promotion_eligible"] is False)
        age = status["age_seconds"]
        require(type(age) in (int, float) and math.isfinite(age) and 0 <= age <= 180)
        observed = _utc(status["observed_at_utc"])
        require(0 <= (captured - observed).total_seconds() <= 180)
        for field in ("blockers", "halt_reasons"):
            if field not in status:
                continue
            values = status[field]
            require(isinstance(values, list) and len(values) <= 32
                    and all(isinstance(v, str) and re.fullmatch("[A-Z_0-9]{1,80}", v)
                            for v in values))
        require("DIAGNOSTIC_PAPER_ONLY" in status["blockers"]
                and "LIVE_ADAPTER_NOT_IMPLEMENTED" not in status["blockers"]
                and "HISTORY_756_SESSIONS_REQUIRED" not in status["blockers"])
        selected = {key: status[key] for key in CORE}
        selected.update({key: status[key] for key in (*COUNTERS, "halt_reasons") if key in status})
        if "last_bar" in status:
            last = status["last_bar"]
            if last is not None:
                stamp = _utc(last)
                require(stamp.second == stamp.microsecond == 0 and stamp.minute % 5 == 0
                        and stamp + timedelta(minutes=5) <= observed)
            selected["last_bar"] = last
        if "archived_session" in status:
            day = status["archived_session"]
            require(isinstance(day, str) and re.fullmatch("[0-9]{4}-[0-9]{2}-[0-9]{2}", day))
            require(date.fromisoformat(day) <= observed.date())
            selected["archived_session"] = day
        if "archive_status" in status:
            value = status["archive_status"]
            require(isinstance(value, str) and re.fullmatch("[A-Z_]{1,40}", value))
            selected["archive_status"] = value
        if "timing" in status:
            selected["timing"] = validate_timing(status["timing"], status)
        if "collection_record" in status:
            selected["collection_record"] = validate_collection(status["collection_record"], status)
        return dict(receipt_schema_version="1.0", observer_source_sha=source_sha, run_id=run_id,
                    captured_at_utc=captured.isoformat(),
                    production_commit=headers["INTRADAY_PRODUCTION_COMMIT"],
                    production_matches_observer_source=headers["INTRADAY_PRODUCTION_COMMIT"]
                    == source_sha, timer=headers["INTRADAY_TIMER"],
                    service_result=headers["INTRADAY_SERVICE_RESULT"],
                    positions_scope="SIMULATED_PAPER_ACCOUNTS", diagnostic=selected,
                    authority_assessed=False)
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ReceiptError("DIAGNOSTIC_RECEIPT_INVALID") from None


def write_receipt(path, receipt):
    value = json.dumps(receipt, sort_keys=True, allow_nan=False).encode() + b"\n"
    require(len(value) <= 16384)
    with Path(path).open("xb") as handle:
        handle.write(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        require(args.input.is_file() and not args.input.is_symlink()
                and args.input.stat().st_size <= 65536)
        hashes = ["sha256:" + hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES]
        identity = hashlib.sha256(json.dumps(hashes, separators=(",", ":")).encode()).hexdigest()
        receipt = build_receipt(args.input.read_text(), source_sha=args.source_sha,
                                run_id=args.run_id, identity=identity, captured=datetime.now(UTC))
        write_receipt(args.output, receipt)
        return 0
    except (OSError, ValueError, TypeError):
        print("DIAGNOSTIC_RECEIPT_INVALID")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
