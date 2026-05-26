"""Spec 013 — 헬스 롤업 단위 테스트.

점검별(워커 생존/stale, 정합성 신선도, 오류 집계, 활동 신선도)과 종합 판정(=최악)
을 결정론적으로 검증. `now` 주입으로 신선도 판정을 고정한다.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import ErrorPayload
from auto_invest.reports import health
from auto_invest.worker.halt import set_halt

NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)


def _conn(tmp_path: Path):
    conn = db.get_connection(tmp_path / "h.db")
    db.migrate(conn)
    return conn


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _seed_recon(conn, result: str, started: datetime):
    conn.execute(
        "INSERT INTO reconciliation_runs (started_at_utc, finished_at_utc, result) VALUES (?,?,?)",
        (_iso(started), _iso(started), result),
    )
    conn.commit()


# --- worker liveness ---


def test_worker_liveness_no_pid_file_degraded(tmp_path: Path):
    c = health.check_worker_liveness(tmp_path / "absent.pid")
    assert c.status == "DEGRADED"
    assert c.data["running"] is False


def test_worker_liveness_alive_ok(tmp_path: Path):
    pid_path = tmp_path / "auto_invest.pid"
    pid_path.write_text(str(os.getpid()))
    c = health.check_worker_liveness(pid_path)
    assert c.status == "OK"
    assert c.data["running"] is True
    assert c.data["pid"] == os.getpid()


def test_worker_liveness_stale_pid_degraded(tmp_path: Path):
    pid_path = tmp_path / "auto_invest.pid"
    # PID 99999999 almost certainly not a live process.
    pid_path.write_text("99999999")
    c = health.check_worker_liveness(pid_path)
    assert c.status == "DEGRADED"
    assert "stale" in c.detail


# --- halt ---


def test_halt_clear_ok(tmp_path: Path):
    c = health.check_halt(tmp_path / "halt.flag")
    assert c.status == "OK"
    assert c.data["halted"] is False


def test_halt_set_degraded(tmp_path: Path):
    halt_path = tmp_path / "halt.flag"
    set_halt(halt_path, "operator paused")
    c = health.check_halt(halt_path)
    assert c.status == "DEGRADED"
    assert c.data["reason"] == "operator paused"


# --- reconciliation ---


def test_reconciliation_none_degraded(tmp_path: Path):
    conn = _conn(tmp_path)
    c = health.check_reconciliation(conn, NOW, 36.0)
    assert c.status == "DEGRADED"


def test_reconciliation_mismatch_critical(tmp_path: Path):
    conn = _conn(tmp_path)
    _seed_recon(conn, "MISMATCH", NOW - timedelta(hours=1))
    c = health.check_reconciliation(conn, NOW, 36.0)
    assert c.status == "CRITICAL"


def test_reconciliation_ok_recent(tmp_path: Path):
    conn = _conn(tmp_path)
    _seed_recon(conn, "OK", NOW - timedelta(hours=1))
    c = health.check_reconciliation(conn, NOW, 36.0)
    assert c.status == "OK"


def test_reconciliation_ok_but_stale_degraded(tmp_path: Path):
    conn = _conn(tmp_path)
    _seed_recon(conn, "OK", NOW - timedelta(hours=48))
    c = health.check_reconciliation(conn, NOW, 36.0)
    assert c.status == "DEGRADED"


# --- recent errors ---


def test_recent_errors_none_ok(tmp_path: Path):
    conn = _conn(tmp_path)
    c = health.check_recent_errors(conn, NOW)
    assert c.status == "OK"
    assert c.data["count"] == 0


def test_recent_errors_present_degraded(tmp_path: Path):
    conn = _conn(tmp_path)
    audit.append(conn, ErrorPayload(where="t", message="boom"))
    c = health.check_recent_errors(conn, NOW)
    assert c.status == "DEGRADED"
    assert c.data["count"] == 1
    assert "boom" in c.data["last_message"]


# --- activity ---


def test_activity_empty_degraded(tmp_path: Path):
    conn = _conn(tmp_path)
    c = health.check_activity(conn, NOW, 36.0)
    assert c.status == "DEGRADED"


def test_activity_fresh_ok(tmp_path: Path):
    conn = _conn(tmp_path)
    audit.append(conn, ErrorPayload(where="t", message="x"))
    # audit.append stamps ts_utc = real now; NOW is in the past relative to it,
    # so use a now slightly after insertion by reading back the row.
    row = conn.execute("SELECT ts_utc FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    inserted = datetime.fromisoformat(row["ts_utc"].replace("Z", "+00:00"))
    c = health.check_activity(conn, inserted + timedelta(minutes=1), 36.0)
    assert c.status == "OK"


# --- overall = worst ---


def test_overall_is_worst(tmp_path: Path):
    conn = _conn(tmp_path)
    _seed_recon(conn, "MISMATCH", NOW - timedelta(hours=1))  # CRITICAL
    pid_path = tmp_path / "auto_invest.pid"
    pid_path.write_text(str(os.getpid()))  # worker OK
    report = health.build_health_report(
        conn, pid_path=pid_path, halt_path=tmp_path / "halt.flag", now=NOW, stale_hours=36.0
    )
    assert report.overall == "CRITICAL"


def test_report_json_deterministic(tmp_path: Path):
    conn = _conn(tmp_path)
    _seed_recon(conn, "OK", NOW - timedelta(hours=1))
    pid_path = tmp_path / "auto_invest.pid"
    pid_path.write_text(str(os.getpid()))
    kwargs = dict(
        pid_path=pid_path, halt_path=tmp_path / "halt.flag", now=NOW, stale_hours=36.0
    )
    a = health.build_health_report(conn, **kwargs).to_json()
    b = health.build_health_report(conn, **kwargs).to_json()
    assert a == b


def test_db_missing_report_critical():
    report = health.db_missing_report(NOW)
    assert report.overall == "CRITICAL"
    assert report.checks[0].name == "database"
