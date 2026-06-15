"""스펙 029 슬라이스 3 — 미실현 포함 시가평가 순자산 성장 추적 테스트 (SC-17~SC-21)."""

from __future__ import annotations

import sqlite3
from decimal import Decimal

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import PortfolioNavSnapshotPayload
from auto_invest.portfolio.growth import (
    NavPoint,
    compute_growth,
    consistent_basis_suffix,
    read_nav_points,
    render_text,
    stitch_basis_segments,
)


def _pt(at: str, nav: str, basis: str | None = None) -> NavPoint:
    return NavPoint(at_utc=at, nav_usd=Decimal(nav), capital_basis_usd=basis)


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


def _seed_snapshot(
    conn: sqlite3.Connection,
    *,
    mode: str,
    nav: str,
    at: str,
    basis: str | None = None,
) -> None:
    audit.append(
        conn,
        PortfolioNavSnapshotPayload(
            mode=mode, schema_version="1.0", source="broker", computed_at_utc=at,
            cash_usd="0", total_market_value_usd=nav, total_nav_usd=nav,
            total_unrealized_pnl_usd="0", holdings_count=1,
            capital_basis_usd=basis,
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


def test_read_nav_points_parses_capital_basis():
    """capital_basis_usd 가 페이로드에 있으면 점에 실리고, 없으면(레거시) None."""
    conn = db.get_connection(":memory:")
    db.migrate(conn)
    _seed_snapshot(conn, mode="paper", nav="2176", at="2026-01-01T00:00:00.000Z")
    _seed_snapshot(
        conn, mode="paper", nav="12000", at="2026-01-02T00:00:00.000Z", basis="12000"
    )
    pts = read_nav_points(conn, mode="paper")
    assert pts[0].capital_basis_usd is None
    assert pts[1].capital_basis_usd == "12000"


# --------------------------------------------------- consistent_basis_suffix


def test_basis_suffix_empty_and_legacy_unchanged():
    """빈 목록·마지막 점이 레거시(베이시스 없음)면 그대로 — 과거 동작 보존."""
    assert consistent_basis_suffix([]) == []
    legacy = [_pt("2026-01-01T00:00:00.000Z", "100"), _pt("2026-01-02T00:00:00.000Z", "110")]
    assert consistent_basis_suffix(legacy) == legacy


def test_basis_suffix_excludes_legacy_prefix():
    """레거시(현금 미포함) 구간 뒤에 자본 베이시스 구간이 시작되면 꼬리만 남는다.

    실제 사고 사례: GLOBAL-TREND 트랙 — NAV 0(halt 시절) → $2,176(포지션만) →
    $12,000(자본 포함). 앞 두 점을 섞으면 +451% 가짜 수익이 샤프를 오염시킨다.
    """
    pts = [
        _pt("2026-01-01T00:00:00.000Z", "0"),
        _pt("2026-01-02T00:00:00.000Z", "2176"),
        _pt("2026-01-03T00:00:00.000Z", "12000", basis="12000"),
        _pt("2026-01-04T00:00:00.000Z", "12100", basis="12000"),
    ]
    out = consistent_basis_suffix(pts)
    assert [p.nav_usd for p in out] == [Decimal("12000"), Decimal("12100")]


def test_basis_suffix_restarts_on_capital_change():
    """운영자가 트랙 자본을 바꾸면(베이시스 변경) 그 시점부터만 — 자금 흐름 점프 배제."""
    pts = [
        _pt("2026-01-01T00:00:00.000Z", "12000", basis="12000"),
        _pt("2026-01-02T00:00:00.000Z", "24100", basis="24000"),
        _pt("2026-01-03T00:00:00.000Z", "24200", basis="24000"),
    ]
    out = consistent_basis_suffix(pts)
    assert [p.nav_usd for p in out] == [Decimal("24100"), Decimal("24200")]


def test_basis_suffix_all_same_basis_keeps_all():
    pts = [
        _pt("2026-01-01T00:00:00.000Z", "12000", basis="12000"),
        _pt("2026-01-02T00:00:00.000Z", "12050", basis="12000"),
    ]
    assert consistent_basis_suffix(pts) == pts


# --------------------------------------------- stitch_basis_segments (TWR)


def test_stitch_empty_and_legacy_unchanged():
    """빈 목록·마지막 점 레거시(베이시스 None)면 그대로 — 라이브/과거 동작 보존."""
    assert stitch_basis_segments([]) == []
    legacy = [_pt("2026-01-01T00:00:00.000Z", "100"), _pt("2026-01-02T00:00:00.000Z", "110")]
    assert stitch_basis_segments(legacy) == legacy


def test_stitch_all_same_basis_preserves_count():
    pts = [
        _pt("2026-01-01T00:00:00.000Z", "100", basis="A"),
        _pt("2026-01-02T00:00:00.000Z", "110", basis="A"),
        _pt("2026-01-03T00:00:00.000Z", "121", basis="A"),
    ]
    out = stitch_basis_segments(pts)
    assert [p.nav_usd for p in out] == [Decimal("100"), Decimal("110"), Decimal("121")]


def test_stitch_recovers_history_across_capital_change():
    """핵심: 같은 전략의 자본 변경(베이시스 경계)이 forward 시계를 리셋하지 않는다.

    suffix 는 최신 구간만(관측 1개) → stitch 는 구간 내부 수익률을 사슬로 이어 전체
    track record 보존(관측 3개). 운영자 지적("같은 전략인데 왜 4주 또 기다려")의 핵심 수정.
    """
    pts = [
        _pt("2026-01-01T00:00:00.000Z", "100", basis="A"),
        _pt("2026-01-02T00:00:00.000Z", "110", basis="A"),  # +10%
        _pt("2026-01-03T00:00:00.000Z", "121", basis="A"),  # +10%
        _pt("2026-01-04T00:00:00.000Z", "200", basis="B"),  # 자본 입금(경계) — 폐기
        _pt("2026-01-05T00:00:00.000Z", "220", basis="B"),  # +10%
    ]
    # 옛 방식: 최신 베이시스 구간만 → 관측 1개(판정 불가).
    assert len(consistent_basis_suffix(pts)) == 2
    # TWR: 경계만 건너뛰고 내부 수익률 사슬 → 관측 3개(A 의 2 + B 의 1).
    out = stitch_basis_segments(pts)
    assert [p.nav_usd for p in out] == [
        Decimal("100"),
        Decimal("110"),
        Decimal("121"),
        Decimal("133.1"),  # 121 × (220/200) = 121 × 1.1 — 자본 점프 제거, 수익률만 이음
    ]


def test_stitch_excludes_legacy_zero_prefix():
    """레거시(0·포지션만) 프리픽스는 깨끗한 수익률이 아니라 제외 — suffix 와 동일 결과."""
    pts = [
        _pt("2026-01-01T00:00:00.000Z", "0"),
        _pt("2026-01-02T00:00:00.000Z", "2176"),
        _pt("2026-01-03T00:00:00.000Z", "12000", basis="12000"),
        _pt("2026-01-04T00:00:00.000Z", "12100", basis="12000"),
    ]
    out = stitch_basis_segments(pts)
    assert [p.nav_usd for p in out] == [Decimal("12000"), Decimal("12100")]


def test_stitch_single_clean_run_no_basis_change():
    pts = [
        _pt("2026-01-01T00:00:00.000Z", "500", basis="500"),
        _pt("2026-01-02T00:00:00.000Z", "505", basis="500"),
        _pt("2026-01-03T00:00:00.000Z", "510", basis="500"),
    ]
    out = stitch_basis_segments(pts)
    assert len(out) == 3  # 경계 없음 → 전부 보존


def test_stitch_no_clean_returns_returns_last_point():
    """깨끗한 수익률이 하나도 없으면(매 점 베이시스 다름) 마지막 점 1개 — 관측 부족."""
    pts = [
        _pt("2026-01-01T00:00:00.000Z", "100", basis="A"),
        _pt("2026-01-02T00:00:00.000Z", "200", basis="B"),
        _pt("2026-01-03T00:00:00.000Z", "300", basis="C"),
    ]
    out = stitch_basis_segments(pts)
    assert [p.nav_usd for p in out] == [Decimal("300")]


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
