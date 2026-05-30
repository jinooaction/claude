"""Spec 029 슬라이스 1 — 포트폴리오 순자산(NAV) 스냅샷 테스트 (SC-01~SC-08)."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.broker.models import PositionSnapshot
from auto_invest.performance.engine import PositionState
from auto_invest.portfolio.nav import (
    SOURCE_BROKER,
    SOURCE_LEDGER,
    compute_nav,
    effective_capital,
    render_text,
)


def _ledger(symbol: str, qty: int, avg: str) -> PositionState:
    return PositionState(
        symbol=symbol,
        qty=qty,
        avg_cost_usd=Decimal(avg),
        realized_pnl_usd=Decimal("0"),
    )


def _broker(symbol: str, qty: int, avg: str) -> PositionSnapshot:
    return PositionSnapshot(symbol=symbol, qty=qty, avg_cost_usd=Decimal(avg))


# --------------------------------------------------------------- SC-01 NAV 기본


def test_sc01_nav_cash_plus_holdings():
    """현금 $1,000 + AAPL 10주(평단 $100, 현재 $120) → 평가 $1,200, NAV $2,200,
    AAPL 비중 ≈ 54.5%."""
    snap = compute_nav(
        broker_cash_usd=Decimal("1000"),
        broker_positions=[_broker("AAPL", 10, "100")],
        broker_reported_total_value_usd=Decimal("2200"),
        ledger_positions={"AAPL": _ledger("AAPL", 10, "100")},
        marks={"AAPL": Decimal("120")},
    )
    assert snap.source == SOURCE_BROKER
    assert snap.cash_usd == Decimal("1000")
    assert snap.total_market_value_usd == Decimal("1200")
    assert snap.total_nav_usd == Decimal("2200")
    assert snap.total_unrealized_pnl_usd == Decimal("200")  # (120-100)*10
    h = snap.holdings[0]
    assert h.symbol == "AAPL"
    assert h.market_value_usd == Decimal("1200")
    assert h.marked is True
    # 비중 1200/2200*100 = 54.545...
    assert h.weight_pct is not None
    assert Decimal("54.5") < h.weight_pct < Decimal("54.6")
    assert h.unrealized_pnl_usd == Decimal("200")


# --------------------------------------------------------------- SC-02 NAV 0


def test_sc02_zero_nav_weight_none_no_div_zero():
    """총 순자산 0 → 모든 비중 None, 0 나눗셈 예외 없음."""
    snap = compute_nav(
        broker_cash_usd=Decimal("0"),
        broker_positions=[_broker("AAPL", 0, "0")],
        broker_reported_total_value_usd=Decimal("0"),
        ledger_positions={},
        marks={},
    )
    assert snap.total_nav_usd == Decimal("0")
    for h in snap.holdings:
        assert h.weight_pct is None


# --------------------------------------------------------------- SC-03 시세 누락


def test_sc03_missing_mark_falls_back_to_avg_cost():
    """시세 일부 누락 → 해당 종목 미실현 None·unmarked, 나머지 정상. NAV 는 누락
    종목을 평균단가로 보수 평가."""
    snap = compute_nav(
        broker_cash_usd=Decimal("500"),
        broker_positions=[
            _broker("AAPL", 10, "100"),  # mark 있음
            _broker("MSFT", 5, "200"),  # mark 없음 → 평단 폴백
        ],
        broker_reported_total_value_usd=None,
        ledger_positions={},
        marks={"AAPL": Decimal("110")},
    )
    by_sym = {h.symbol: h for h in snap.holdings}
    assert by_sym["AAPL"].marked is True
    assert by_sym["AAPL"].market_value_usd == Decimal("1100")
    assert by_sym["MSFT"].marked is False
    assert by_sym["MSFT"].market_value_usd == Decimal("1000")  # 200*5 평단 폴백
    assert by_sym["MSFT"].unrealized_pnl_usd is None
    assert "MSFT" in snap.unmarked_symbols
    assert "AAPL" not in snap.unmarked_symbols
    # NAV = 500 + 1100 + 1000 = 2600
    assert snap.total_nav_usd == Decimal("2600")
    # 미실현은 측정 가능 종목(AAPL)만: (110-100)*10 = 100
    assert snap.total_unrealized_pnl_usd == Decimal("100")


# --------------------------------------------------------------- SC-04 수량 드리프트


def test_sc04_qty_drift_broker_vs_ledger():
    """브로커 보유 AAPL 10 vs 장부 8 → 종목 드리프트 +2."""
    snap = compute_nav(
        broker_cash_usd=Decimal("0"),
        broker_positions=[_broker("AAPL", 10, "100")],
        broker_reported_total_value_usd=None,
        ledger_positions={"AAPL": _ledger("AAPL", 8, "100")},
        marks={"AAPL": Decimal("100")},
    )
    by_sym = {d.symbol: d for d in snap.drifts}
    assert by_sym["AAPL"].qty_drift == 2
    assert by_sym["AAPL"].status == "qty_mismatch"
    assert by_sym["AAPL"].market_value_drift_usd == Decimal("200")  # (10-8)*100
    assert snap.total_qty_drift == 2


# --------------------------------------------------------------- SC-05 broker_only


def test_sc05_broker_only_symbol():
    """브로커에만 있는 TSLA(장부 0) → 드리프트에 broker_only."""
    snap = compute_nav(
        broker_cash_usd=Decimal("0"),
        broker_positions=[_broker("TSLA", 3, "200")],
        broker_reported_total_value_usd=None,
        ledger_positions={},
        marks={"TSLA": Decimal("210")},
    )
    by_sym = {d.symbol: d for d in snap.drifts}
    assert by_sym["TSLA"].status == "broker_only"
    assert by_sym["TSLA"].ledger_qty == 0
    assert by_sym["TSLA"].broker_qty == 3


def test_sc05b_ledger_only_symbol():
    """장부에만 있는 종목 → ledger_only."""
    snap = compute_nav(
        broker_cash_usd=Decimal("0"),
        broker_positions=[],
        broker_reported_total_value_usd=None,
        ledger_positions={"NVDA": _ledger("NVDA", 4, "300")},
        marks={"NVDA": Decimal("300")},
    )
    by_sym = {d.symbol: d for d in snap.drifts}
    assert by_sym["NVDA"].status == "ledger_only"
    assert by_sym["NVDA"].qty_drift == -4


# --------------------------------------------------------------- SC-07 결정론


def test_sc07_deterministic():
    """같은 입력 → 같은 출력(결정론). Decimal 경로."""
    kwargs = dict(
        broker_cash_usd=Decimal("1234.56"),
        broker_positions=[_broker("AAPL", 7, "111.11")],
        broker_reported_total_value_usd=None,
        ledger_positions={"AAPL": _ledger("AAPL", 7, "111.11")},
        marks={"AAPL": Decimal("123.45")},
    )
    a = compute_nav(**kwargs)
    b = compute_nav(**kwargs)
    assert a.to_json_dict() == b.to_json_dict()


# --------------------------------------------------------------- SC-08 폴백 출처


def test_sc08_ledger_fallback_when_no_broker():
    """브로커 정보 없음 → 장부 + 마크로 폴백, source='ledger', 드리프트 없음."""
    snap = compute_nav(
        broker_cash_usd=None,
        broker_positions=None,
        broker_reported_total_value_usd=None,
        ledger_positions={"AAPL": _ledger("AAPL", 10, "100")},
        marks={"AAPL": Decimal("130")},
    )
    assert snap.source == SOURCE_LEDGER
    assert snap.cash_usd == Decimal("0")  # 브로커 현금 모름 → 0
    assert snap.total_market_value_usd == Decimal("1300")
    assert snap.total_nav_usd == Decimal("1300")
    assert snap.drifts == []  # 브로커 없으면 드리프트 계산 불가
    assert snap.total_qty_drift == 0


# --------------------------------------------------------------- 부가: 데이터 품질 경고


def test_broker_reported_nav_gap_warning():
    """브로커 보고 NAV 와 계산 NAV 가 5% 넘게 벌어지면 경고."""
    snap = compute_nav(
        broker_cash_usd=Decimal("1000"),
        broker_positions=[_broker("AAPL", 10, "100")],
        broker_reported_total_value_usd=Decimal("5000"),  # 계산 2200 과 큰 차이
        ledger_positions={"AAPL": _ledger("AAPL", 10, "100")},
        marks={"AAPL": Decimal("120")},
    )
    assert snap.data_quality_warnings
    assert any("순자산" in w for w in snap.data_quality_warnings)


def test_no_warning_when_within_tolerance():
    snap = compute_nav(
        broker_cash_usd=Decimal("1000"),
        broker_positions=[_broker("AAPL", 10, "100")],
        broker_reported_total_value_usd=Decimal("2200"),
        ledger_positions={"AAPL": _ledger("AAPL", 10, "100")},
        marks={"AAPL": Decimal("120")},
    )
    assert snap.data_quality_warnings == []


# --------------------------------------------------------------- 렌더링 smoke


def test_render_text_smoke():
    snap = compute_nav(
        broker_cash_usd=Decimal("1000"),
        broker_positions=[_broker("AAPL", 10, "100")],
        broker_reported_total_value_usd=Decimal("2200"),
        ledger_positions={"AAPL": _ledger("AAPL", 8, "100")},
        marks={"AAPL": Decimal("120")},
    )
    text = render_text(snap)
    assert "포트폴리오 순자산" in text
    assert "AAPL" in text
    assert "드리프트" in text  # 8 vs 10 불일치가 표시됨


# --------------------------------------------------------------- SC-06 감사 왕복


def test_sc06_audit_snapshot_roundtrip():
    """PORTFOLIO_NAV_SNAPSHOT 이벤트가 audit_log 에 정확히 1건 append/read 된다.
    기존 이벤트 타입을 건드리지 않는 K4 추가-전용."""
    import sqlite3

    from auto_invest.persistence import audit, db
    from auto_invest.persistence.audit import PortfolioNavSnapshotPayload

    conn: sqlite3.Connection = db.get_connection(":memory:")
    db.migrate(conn)

    before = len(audit.read_all(conn))
    audit.append(
        conn,
        PortfolioNavSnapshotPayload(
            mode="live",
            schema_version="1.0",
            source="broker",
            computed_at_utc="2026-05-30T00:00:00.000Z",
            cash_usd="1000",
            total_market_value_usd="1200",
            total_nav_usd="2200",
            total_unrealized_pnl_usd="200",
            broker_reported_nav_usd="2200",
            holdings_count=1,
            total_qty_drift=2,
            total_value_drift_usd="200",
        ),
    )
    rows = audit.read_all(conn)
    assert len(rows) == before + 1
    snap_rows = [r for r in rows if r["event_type"] == "PORTFOLIO_NAV_SNAPSHOT"]
    assert len(snap_rows) == 1
    payload = audit.parse_payload(snap_rows[0])
    assert payload["total_nav_usd"] == "2200"
    assert payload["source"] == "broker"
    assert payload["total_qty_drift"] == 2


def test_portfolio_nav_payload_in_any_union():
    """새 페이로드가 AnyPayload 유니온에 포함되어 역직렬화 가능."""
    from auto_invest.persistence.audit import AnyPayload, PortfolioNavSnapshotPayload

    assert PortfolioNavSnapshotPayload in AnyPayload.__args__


# =================================================== 슬라이스 2 — 유효 자본


def test_sc09_defense_drawdown_always():
    """시작 $10,000, NAV $8,000 → 유효 자본 $8,000 (방어, 옵트인 무관)."""
    # growth 꺼도 켜도 하락은 항상 반영.
    assert effective_capital(
        Decimal("10000"), Decimal("8000"), growth_enabled=False
    ) == Decimal("8000")
    assert effective_capital(
        Decimal("10000"), Decimal("8000"), growth_enabled=True
    ) == Decimal("8000")


def test_sc10_growth_off_starting_is_ceiling():
    """시작 $10,000, NAV $15,000, growth 끔 → 유효 자본 $10,000 (시작이 천장)."""
    assert effective_capital(
        Decimal("10000"), Decimal("15000"), growth_enabled=False
    ) == Decimal("10000")


def test_sc11_growth_on_within_ceiling():
    """시작 $10,000, NAV $15,000, growth 켬, 상한 2배 → 유효 자본 $15,000."""
    assert effective_capital(
        Decimal("10000"),
        Decimal("15000"),
        growth_enabled=True,
        max_growth_factor=Decimal("2"),
    ) == Decimal("15000")


def test_sc12_growth_clamped_at_ceiling():
    """시작 $10,000, NAV $25,000, growth 켬, 상한 2배 → 유효 자본 $20,000 (클램프)."""
    assert effective_capital(
        Decimal("10000"),
        Decimal("25000"),
        growth_enabled=True,
        max_growth_factor=Decimal("2"),
    ) == Decimal("20000")


def test_sc13_nav_none_falls_back_to_start():
    """NAV None → 유효 자본 = 시작 자본 (폴백)."""
    assert effective_capital(
        Decimal("10000"), None, growth_enabled=True
    ) == Decimal("10000")
    # 0 이하도 폴백.
    assert effective_capital(
        Decimal("10000"), Decimal("0"), growth_enabled=True
    ) == Decimal("10000")
    assert effective_capital(
        Decimal("10000"), Decimal("-5"), growth_enabled=True
    ) == Decimal("10000")


def test_effective_capital_equal_nav_is_noop():
    """NAV == 시작 → 유효 자본 = 시작 (변화 없음)."""
    assert effective_capital(
        Decimal("10000"), Decimal("10000"), growth_enabled=True
    ) == Decimal("10000")


def test_effective_capital_audit_payload_in_union():
    from auto_invest.persistence.audit import (
        AnyPayload,
        EffectiveCapitalUpdatedPayload,
    )

    assert EffectiveCapitalUpdatedPayload in AnyPayload.__args__
