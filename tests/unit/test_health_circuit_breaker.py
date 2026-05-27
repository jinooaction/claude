"""Spec 014 — health 롤업의 브레이커 점검 (T011). 읽기 전용 확인 포함."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import CircuitBreakerTrippedPayload
from auto_invest.reports import health
from auto_invest.worker.halt import set_halt

NOW = datetime(2026, 5, 26, 15, 0, tzinfo=UTC)


def _conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    return c


def _trip_row(conn) -> None:
    audit.append(
        conn,
        CircuitBreakerTrippedPayload(
            mode="paper", tripped_at_utc="2026-05-26T11:00:00.000Z",
            starting_capital_usd="100", realized_pnl_today_usd="-20",
            current_equity_usd="80", breached=["daily_loss"],
            daily_loss_limit_pct="10", max_total_drawdown_pct="20",
            reason="circuit breaker tripped: daily realized loss",
        ),
    )


def test_no_trip_ok(tmp_path: Path):
    conn = _conn(tmp_path)
    c = health.check_circuit_breaker(conn, tmp_path / "halt.flag", NOW)
    assert c.status == "OK"
    assert c.data["trip_count"] == 0
    assert c.data["halted_by_breaker"] is False


def test_breaker_halt_is_critical(tmp_path: Path):
    conn = _conn(tmp_path)
    _trip_row(conn)
    halt_path = tmp_path / "halt.flag"
    set_halt(halt_path, "circuit_breaker: daily realized loss $-20 <= limit $-10")
    c = health.check_circuit_breaker(conn, halt_path, NOW)
    assert c.status == "CRITICAL"
    assert c.data["halted_by_breaker"] is True
    assert c.data["last_breached"] == ["daily_loss"]


def test_past_trip_but_resumed_is_ok(tmp_path: Path):
    """트립 이력은 있으나 halt 해제(resume)된 경우 OK + 이력 표시."""
    conn = _conn(tmp_path)
    _trip_row(conn)
    c = health.check_circuit_breaker(conn, tmp_path / "halt.flag", NOW)
    assert c.status == "OK"
    assert c.data["trip_count"] == 1


def test_manual_halt_not_attributed_to_breaker(tmp_path: Path):
    conn = _conn(tmp_path)
    halt_path = tmp_path / "halt.flag"
    set_halt(halt_path, "operator paused")
    c = health.check_circuit_breaker(conn, halt_path, NOW)
    assert c.status == "OK"
    assert c.data["halted_by_breaker"] is False


def test_breaker_check_is_read_only(tmp_path: Path):
    """점검은 감사 로그에 한 줄도 쓰지 않는다(읽기 전용)."""
    conn = _conn(tmp_path)
    _trip_row(conn)
    before = len(audit.read_all(conn))
    health.check_circuit_breaker(conn, tmp_path / "halt.flag", NOW)
    health.build_health_report(
        conn, pid_path=tmp_path / "x.pid", halt_path=tmp_path / "halt.flag", now=NOW
    )
    assert len(audit.read_all(conn)) == before


def test_breaker_halt_makes_overall_critical(tmp_path: Path):
    conn = _conn(tmp_path)
    _trip_row(conn)
    halt_path = tmp_path / "halt.flag"
    set_halt(halt_path, "circuit_breaker: equity floor breached")
    report = health.build_health_report(
        conn, pid_path=tmp_path / "x.pid", halt_path=halt_path, now=NOW
    )
    assert report.overall == "CRITICAL"
    names = {c.name for c in report.checks}
    assert "circuit_breaker" in names
