"""Operational health roll-up (spec 013).

A single read-only aggregator that answers "is the system healthy right
now?" by combining the reliability signals scattered across the codebase:
worker liveness (PID file), the halt flag, the last reconciliation
outcome, recent errors, and activity freshness — plus a context block
(today's order funnel, positions, last performance snapshot, last tuner
run) that informs but does not grade.

Safety invariant: this module is **read-only**. It only runs SELECTs and
filesystem existence/`os.kill(pid, 0)` probes. It never writes to the
audit log, never mutates a state file, and never calls `db.migrate`
(which would be unsafe to run against a DB an active worker holds open).
Every query targets tables present since migration 0001.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.worker.halt import read_halt

SCHEMA_VERSION = "1.0"

# Severity ordering — overall verdict is the worst individual check.
_OK = "OK"
_DEGRADED = "DEGRADED"
_CRITICAL = "CRITICAL"
_SEVERITY = {_OK: 0, _DEGRADED: 1, _CRITICAL: 2}


@dataclass(frozen=True)
class HealthCheck:
    """One graded reliability signal."""

    name: str
    status: str  # OK | DEGRADED | CRITICAL
    detail: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "data": self.data,
        }


@dataclass(frozen=True)
class HealthReport:
    """Aggregated verdict + per-check breakdown + informational context."""

    generated_at_utc: str
    overall: str
    checks: tuple[HealthCheck, ...]
    context: dict

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": self.generated_at_utc,
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
            "context": self.context,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


def _worst(statuses: list[str]) -> str:
    if not statuses:
        return _OK
    return max(statuses, key=lambda s: _SEVERITY.get(s, 0))


def _age_hours(ts_str: str | None, now: datetime) -> float | None:
    """Hours between an ISO-8601 (…Z) timestamp and `now`. None if unparsable."""
    if not ts_str:
        return None
    try:
        parsed = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (now - parsed).total_seconds() / 3600.0


# --------------------------------------------------------------------------
# Individual checks (all read-only)
# --------------------------------------------------------------------------


def check_worker_liveness(pid_path: Path) -> HealthCheck:
    if not pid_path.exists():
        return HealthCheck(
            "worker_liveness", _DEGRADED, "워커 PID 파일 없음 — 워커 미실행",
            {"running": False, "pid": None},
        )
    try:
        pid = int(pid_path.read_text().strip())
    except (OSError, ValueError):
        return HealthCheck(
            "worker_liveness", _DEGRADED, "PID 파일을 읽을 수 없음(손상)",
            {"running": False, "pid": None},
        )
    try:
        os.kill(pid, 0)
    except OSError:
        return HealthCheck(
            "worker_liveness", _DEGRADED, f"PID 파일은 있으나 프로세스 {pid} 없음(stale)",
            {"running": False, "pid": pid},
        )
    return HealthCheck(
        "worker_liveness", _OK, f"워커 실행 중 (pid {pid})",
        {"running": True, "pid": pid},
    )


def check_halt(halt_path: Path) -> HealthCheck:
    state = read_halt(halt_path)
    if state is None:
        return HealthCheck("halt", _OK, "거래 중지 아님", {"halted": False})
    return HealthCheck(
        "halt", _DEGRADED, f"거래 중지됨: {state.reason}",
        {"halted": True, "reason": state.reason, "ts_utc": state.ts_utc},
    )


def check_reconciliation(
    conn: sqlite3.Connection, now: datetime, stale_hours: float
) -> HealthCheck:
    row = conn.execute(
        "SELECT result, started_at_utc FROM reconciliation_runs ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return HealthCheck("reconciliation", _DEGRADED, "정합성 검사 기록 없음", {"result": None})
    result = row["result"]
    started = row["started_at_utc"]
    age = _age_hours(started, now)
    data = {"result": result, "started_at_utc": started, "age_hours": age}
    if result == "MISMATCH":
        return HealthCheck("reconciliation", _CRITICAL, "마지막 정합성 검사 불일치(MISMATCH)", data)
    if result == "INCONCLUSIVE":
        return HealthCheck("reconciliation", _DEGRADED, "마지막 정합성 검사 결론 불가", data)
    if age is not None and age > stale_hours:
        return HealthCheck(
            "reconciliation", _DEGRADED,
            f"마지막 정합성 OK이나 {age:.1f}시간 경과(오래됨)", data,
        )
    return HealthCheck("reconciliation", _OK, "마지막 정합성 검사 OK", data)


def check_recent_errors(conn: sqlite3.Connection, now: datetime) -> HealthCheck:
    rows = conn.execute(
        "SELECT ts_utc, payload_json FROM audit_log WHERE event_type = 'ERROR' ORDER BY seq DESC"
    ).fetchall()
    recent = [r for r in rows if (_age_hours(r["ts_utc"], now) or 1e9) <= 24.0]
    if not recent:
        return HealthCheck("recent_errors", _OK, "최근 24시간 오류 없음", {"count": 0})
    last = recent[0]
    detail_msg = ""
    try:
        payload = json.loads(last["payload_json"])
        detail_msg = str(payload.get("message") or payload.get("detail") or "")[:200]
    except (ValueError, TypeError):
        detail_msg = ""
    return HealthCheck(
        "recent_errors", _DEGRADED,
        f"최근 24시간 오류 {len(recent)}건 (마지막: {detail_msg or 'n/a'})",
        {"count": len(recent), "last_ts_utc": last["ts_utc"], "last_message": detail_msg},
    )


def check_activity(conn: sqlite3.Connection, now: datetime, stale_hours: float) -> HealthCheck:
    row = conn.execute("SELECT ts_utc FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    if row is None:
        return HealthCheck("activity", _DEGRADED, "감사 로그 비어있음", {"last_ts_utc": None})
    last_ts = row["ts_utc"]
    age = _age_hours(last_ts, now)
    data = {"last_ts_utc": last_ts, "age_hours": age}
    if age is not None and age > stale_hours:
        return HealthCheck("activity", _DEGRADED, f"최근 활동 {age:.1f}시간 전(정체 가능)", data)
    return HealthCheck("activity", _OK, "최근 활동 신선", data)


# --------------------------------------------------------------------------
# Context (informational; not graded)
# --------------------------------------------------------------------------


def _build_context(conn: sqlite3.Connection, now: datetime) -> dict:
    today = now.strftime("%Y-%m-%d")
    order_counts = dict(
        conn.execute(
            """
            SELECT event_type, COUNT(*) FROM audit_log
            WHERE substr(ts_utc, 1, 10) = ?
              AND event_type IN ('ORDER_INTENT','ORDER_SUBMITTED',
                                 'ORDER_REJECTED_BY_GATE','FILL')
            GROUP BY event_type
            """,
            (today,),
        ).fetchall()
    )

    try:
        from auto_invest.persistence import positions as _positions

        position_count = len(_positions.get_all_positions(conn))
    except sqlite3.Error:
        position_count = None

    last_perf = _latest_payload(conn, "LIVE_PERFORMANCE_SNAPSHOT")
    perf_ctx = None
    if last_perf is not None:
        perf_ctx = {
            "return_pct": last_perf.get("return_pct"),
            "max_drawdown_pct": (last_perf.get("risk") or {}).get("max_drawdown_pct")
            if isinstance(last_perf.get("risk"), dict)
            else last_perf.get("max_drawdown_pct"),
        }

    last_tuner_row = conn.execute(
        "SELECT ts_utc FROM audit_log WHERE event_type = 'AUTO_TUNER_RUN' ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    last_canary = _latest_payload(conn, "AUTO_TUNED_CANARY_VALIDATED")

    return {
        "today_order_counts": order_counts,
        "position_count": position_count,
        "last_performance": perf_ctx,
        "last_tuner_run_utc": last_tuner_row["ts_utc"] if last_tuner_row else None,
        "last_canary_validation_outcome": (
            last_canary.get("outcome") if isinstance(last_canary, dict) else None
        ),
    }


def _latest_payload(conn: sqlite3.Connection, event_type: str) -> dict | None:
    row = conn.execute(
        "SELECT payload_json FROM audit_log WHERE event_type = ? ORDER BY seq DESC LIMIT 1",
        (event_type,),
    ).fetchone()
    if row is None:
        return None
    try:
        parsed = json.loads(row["payload_json"])
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


# --------------------------------------------------------------------------
# Top-level builder
# --------------------------------------------------------------------------


def build_health_report(
    conn: sqlite3.Connection,
    *,
    pid_path: Path,
    halt_path: Path,
    now: datetime,
    stale_hours: float = 36.0,
) -> HealthReport:
    """Aggregate all reliability checks + context into one verdict.

    `now` is injected so the staleness checks are deterministic in tests.
    """
    checks = (
        check_worker_liveness(pid_path),
        check_halt(halt_path),
        check_reconciliation(conn, now, stale_hours),
        check_recent_errors(conn, now),
        check_activity(conn, now, stale_hours),
    )
    overall = _worst([c.status for c in checks])
    context = _build_context(conn, now)
    return HealthReport(
        generated_at_utc=now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        overall=overall,
        checks=checks,
        context=context,
    )


def db_missing_report(now: datetime) -> HealthReport:
    """CRITICAL verdict when the DB file does not exist (no connection made)."""
    check = HealthCheck("database", _CRITICAL, "DB 파일 없음", {"exists": False})
    return HealthReport(
        generated_at_utc=now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        overall=_CRITICAL,
        checks=(check,),
        context={},
    )
