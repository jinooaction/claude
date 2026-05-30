"""스펙 026 — 승격 준비 평가(라이브 audit_log → 게이트) 테스트.

SC-R01: 라이브 체결 없음 → 불합격(트랙레코드·기간 미달).
SC-R02: 서킷브레이커 트립 이벤트 → circuit_breaker_clear=False.
SC-R03: 정합성 불일치 이벤트 → reconciliation_clear=False.
SC-R04: read-only — audit_log row 수 불변.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

from auto_invest.config.caps import SizingCaps
from auto_invest.persistence import db as _db_mod
from auto_invest.promotion.readiness import compute_readiness

_CAPS = SizingCaps(
    per_trade_pct=Decimal("5"),
    per_symbol_pct=Decimal("20"),
    global_exposure_pct=Decimal("80"),
    canary_capital_pct=Decimal("5"),
    canary_min_duration_days=10,
    canary_acceptance_drawdown_pct=Decimal("3"),
)


def _open_db(path: Path) -> sqlite3.Connection:
    conn = _db_mod.get_connection(path)
    _db_mod.migrate(conn)
    return conn


def _insert_event(
    conn: sqlite3.Connection,
    event_type: str,
    ts: str = "2026-05-20T00:00:00.000Z",
) -> None:
    conn.execute(
        "INSERT INTO audit_log (ts_utc, event_type, payload_json) VALUES (?, ?, ?)",
        (ts, event_type, "{}"),
    )
    conn.commit()


def test_scr01_no_fills_not_ready(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    r = compute_readiness(conn, caps=_CAPS, starting_capital=Decimal("12000"))
    assert r.ready is False
    assert r.checks["track_record"] is False
    assert r.checks["min_duration"] is False


def test_scr02_breaker_event_flags_not_clear(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    _insert_event(conn, "CIRCUIT_BREAKER_TRIPPED")
    r = compute_readiness(conn, caps=_CAPS, starting_capital=Decimal("12000"))
    assert r.checks["circuit_breaker_clear"] is False
    assert r.ready is False


def test_scr03_reconciliation_mismatch_flags_not_clear(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    _insert_event(conn, "RECONCILIATION_MISMATCH")
    r = compute_readiness(conn, caps=_CAPS, starting_capital=Decimal("12000"))
    assert r.checks["reconciliation_clear"] is False
    assert r.ready is False


def test_scr04_read_only(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    _insert_event(conn, "CIRCUIT_BREAKER_TRIPPED")
    before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    compute_readiness(conn, caps=_CAPS, starting_capital=Decimal("12000"))
    after = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert before == after
