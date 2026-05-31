"""스펙 029 슬라이스 3 — 미실현 포함 시가평가 순자산 성장 추적 테스트 (SC-17~SC-21)."""

from __future__ import annotations

import sqlite3
from decimal import Decimal

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import PortfolioNavSnapshotPayload
from auto_invest.portfolio.growth import (
    NavPoint,
    compute_growth,
    read_nav_points,
    render_text,
)


def _pt(at: str, nav: str) -> NavPoint:
    return NavPoint(at_utc=at, nav_usd=Decimal(nav))


# --------------------------------------------------------------- SC-17 총수익률


def test_sc17_total_return():
    """NAV [$10,000 → $11,000 → $12,100] → 총수익률 +21%, 시작 $10,000, 현재 $12,100."""
    points = [
        _pt("2026-01-01T00:00:00.000Z", "10000"),
        _pt("2026-01-02T00:00:00.000Z", "11000"),
        _pt("2026-01-03T00:00:00.000Z", "12100"),
    ]
    r = compute_growth(points, mode="live")
    assert r.starting_nav_usd == Decimal("10000")
    assert r.current_nav_usd == Decimal("12100")
    assert r.absolute_change_usd == Decimal("2100")
    assert r.total_return_pct is not None
    assert Decimal("20.9") < r.total_return_pct < Decimal("21.1")
    assert r.snapshot_count == 3


# --------------------------------------------------------------- SC-18 최대낙폭


def test_sc18_max_drawdown():
    """[$10,000 → $12,000 → $9,000 → $11,000] → 최대낙폭 25%(=12,000→9,000)."""
    points = [
        _pt("2026-01-01T00:00:00.000Z", "10000"),
        _pt("2026-01-02T00:00:00.000Z", "12000"),
        _pt("2026-01-03T00:00:00.000Z", "9000"),
        _pt("2026-01-04T00:00:00.000Z", "11000"),
    ]
    r = compute_growth(points, mode="live")
    assert r.max_drawdown_pct is not None
    assert Decimal("24.9") < r.max_drawdown_pct < Decimal("25.1")


# --------------------------------------------------------------- SC-19 측정 불가


def test_sc19_single_snapshot_no_trend():
    """스냅샷 1개 → 추세 None(측정 불가), 예외 없음."""
    r = compute_growth([_pt("2026-01-01T00:00:00.000Z", "10000")], mode="live")
    assert r.snapshot_count == 1
    assert r.current_nav_usd == Decimal("10000")
    assert r.total_return_pct is None
    assert r.max_drawdown_pct is None
    assert r.cagr_pct is None


def test_zero_snapshots():
    r = compute_growth([], mode="live")
    assert r.snapshot_count == 0
    assert r.starting_nav_usd is None
    assert r.total_return_pct is None


# --------------------------------------------------------------- SC-20 결정론


def test_sc20_deterministic():
    """같은 입력 → 같은 출력(결정론)."""
    points = [
        _pt("2026-01-01T00:00:00.000Z", "10000.55"),
        _pt("2026-02-01T00:00:00.000Z", "11234.99"),
    ]
    a = compute_growth(points, mode="live")
    b = compute_growth(points, mode="live")
    assert a.to_json_dict() == b.to_json_dict()


# --------------------------------------------------------------- SC-21 CAGR


def test_sc21_cagr_one_year():
    """기간 365일·총수익률 +21% → CAGR ≈ +21%(1년)."""
    points = [
        _pt("2026-01-01T00:00:00.000Z", "10000"),
        _pt("2027-01-01T00:00:00.000Z", "12100"),
    ]
    r = compute_growth(points, mode="live")
    assert r.period_days is not None
    assert Decimal("364") < r.period_days < Decimal("366")
    assert r.cagr_pct is not None
    assert Decimal("20") < r.cagr_pct < Decimal("22")


def test_cagr_zero_period_none():
    """같은 시각 두 스냅샷(기간 0일) → CAGR None."""
    points = [
        _pt("2026-01-01T00:00:00.000Z", "10000"),
        _pt("2026-01-01T00:00:00.000Z", "11000"),
    ]
    r = compute_growth(points, mode="live")
    assert r.period_days == Decimal("0")
    assert r.cagr_pct is None
    # 총수익률은 여전히 계산됨(시각 무관).
    assert r.total_return_pct is not None


def test_nonpositive_nav_degrades_drawdown():
    """곡선에 0 이하가 섞이면 낙폭/CAGR None(metrics 양수 계약)."""
    points = [
        _pt("2026-01-01T00:00:00.000Z", "10000"),
        _pt("2026-01-02T00:00:00.000Z", "0"),
        _pt("2026-01-03T00:00:00.000Z", "5000"),
    ]
    r = compute_growth(points, mode="live")
    assert r.max_drawdown_pct is None
    assert r.cagr_pct is None


# --------------------------------------------------------------- read_nav_points


def _seed_snapshot(conn: sqlite3.Connection, *, mode: str, nav: str, at: str) -> None:
    audit.append(
        conn,
        PortfolioNavSnapshotPayload(
            mode=mode, schema_version="1.0", source="broker", computed_at_utc=at,
            cash_usd="0", total_market_value_usd=nav, total_nav_usd=nav,
            total_unrealized_pnl_usd="0", holdings_count=1,
        ),
    )


def test_read_nav_points_filters_mode_and_orders():
    """audit_log 에서 모드별 NAV 스냅샷을 시간순으로 읽는다."""
    conn = db.get_connection(":memory:")
    db.migrate(conn)
    _seed_snapshot(conn, mode="live", nav="10000", at="2026-01-01T00:00:00.000Z")
    _seed_snapshot(conn, mode="paper", nav="999", at="2026-01-01T12:00:00.000Z")
    _seed_snapshot(conn, mode="live", nav="11000", at="2026-01-02T00:00:00.000Z")

    live = read_nav_points(conn, mode="live")
    assert [p.nav_usd for p in live] == [Decimal("10000"), Decimal("11000")]
    paper = read_nav_points(conn, mode="paper")
    assert [p.nav_usd for p in paper] == [Decimal("999")]


def test_read_nav_points_end_to_end_growth():
    """기록 → 읽기 → 성장 계산 왕복."""
    conn = db.get_connection(":memory:")
    db.migrate(conn)
    _seed_snapshot(conn, mode="live", nav="10000", at="2026-01-01T00:00:00.000Z")
    _seed_snapshot(conn, mode="live", nav="12000", at="2026-01-02T00:00:00.000Z")
    points = read_nav_points(conn, mode="live")
    r = compute_growth(points, mode="live")
    assert r.starting_nav_usd == Decimal("10000")
    assert r.current_nav_usd == Decimal("12000")
    assert r.total_return_pct is not None
    assert Decimal("19.9") < r.total_return_pct < Decimal("20.1")


def test_render_text_smoke():
    points = [
        _pt("2026-01-01T00:00:00.000Z", "10000"),
        _pt("2026-01-02T00:00:00.000Z", "12100"),
    ]
    text = render_text(compute_growth(points, mode="live"))
    assert "성장 추세" in text
    assert "총수익률" in text


def test_render_text_empty():
    text = render_text(compute_growth([], mode="live"))
    assert "스냅샷 없음" in text
