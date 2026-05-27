"""Spec 011 P2 — 위험조정 성과(US2) 단위 테스트.

검증:
  - 청산(매도)당 실현 손익 분해 (realized_trades).
  - 승률·평균이익/손실·손익비 (FR-006).
  - 샤프·최대낙폭·총수익률이 spec 008 backtest/metrics.py 와 수치 일치 (FR-007, SC-002).
  - 거래 0건 → risk None, 0 나눗셈 없음 (US2 AC2).
  - 시작 자본이 손실로 0 이하가 되면 곡선 기반 지표는 N/A, 건당 지표는 정상.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.backtest.metrics import (
    daily_returns_from_equity,
    max_drawdown_pct,
    sharpe_ratio,
    sortino_ratio,
    total_return_pct,
)
from auto_invest.performance.engine import (
    FillRecord,
    compute_performance,
    compute_risk_metrics,
    realized_trades,
    render_text,
)

SINCE = datetime(2000, 1, 1, tzinfo=UTC)
UNTIL = datetime(2099, 1, 1, tzinfo=UTC)


def _fill(symbol, side, qty, price, ts, rule_id="R"):
    return FillRecord(symbol, side, qty, Decimal(price), ts, rule_id)


# --- 기본 3거래 시퀀스 (승 30, 패 -20, 승 10) ----------------------------------

_FILLS = [
    _fill("AAPL", "BUY", 1, "100", "2026-05-20T00:00:00.000Z"),
    _fill("AAPL", "SELL", 1, "130", "2026-05-20T01:00:00.000Z"),  # +30
    _fill("AAPL", "BUY", 1, "100", "2026-05-21T00:00:00.000Z"),
    _fill("AAPL", "SELL", 1, "80", "2026-05-21T01:00:00.000Z"),  # -20
    _fill("MSFT", "BUY", 1, "50", "2026-05-22T00:00:00.000Z"),
    _fill("MSFT", "SELL", 1, "60", "2026-05-22T01:00:00.000Z"),  # +10
]
_EQUITY = [Decimal("250"), Decimal("280"), Decimal("260"), Decimal("270")]


def test_realized_trades_per_sell() -> None:
    trades = realized_trades(_FILLS)
    assert [t.pnl_usd for t in trades] == [Decimal("30"), Decimal("-20"), Decimal("10")]
    assert [t.date for t in trades] == ["2026-05-20", "2026-05-21", "2026-05-22"]
    assert [t.symbol for t in trades] == ["AAPL", "AAPL", "MSFT"]


def test_win_rate_avg_profit_factor() -> None:
    r = compute_risk_metrics(_FILLS, starting_capital=Decimal("250"))
    assert r is not None
    assert r.closed_trades == 3
    assert r.win_rate == Decimal("2") / Decimal("3")
    assert r.avg_win_usd == Decimal("20")  # (30+10)/2
    assert r.avg_loss_usd == Decimal("-20")
    assert r.profit_factor == Decimal("2")  # 40 / 20


def test_risk_metrics_match_backtest_metrics() -> None:
    """SC-002 — 샤프·낙폭·총수익률·Sortino 가 backtest/metrics.py 와 바이트 동일.

    spec 016 슬라이스 2(헌법 X.2 단일 잣대): 라이브 위험조정 지표는 전부
    backtest/metrics.py 공용 정의를 호출해 백테스트와 같은 수치를 낸다.
    """
    r = compute_risk_metrics(_FILLS, starting_capital=Decimal("250"))
    assert r is not None
    assert r.total_return_pct == total_return_pct(_EQUITY)
    assert r.max_drawdown_pct == max_drawdown_pct(_EQUITY)
    assert r.sharpe_ratio == sharpe_ratio(daily_returns_from_equity(_EQUITY))
    assert r.sortino_ratio == sortino_ratio(daily_returns_from_equity(_EQUITY))


def test_starting_capital_default_is_gross_invested() -> None:
    """--capital 미지정이면 총 투입액(gross_invested)을 곡선 기준 자본으로 쓴다."""
    rep = compute_performance(_FILLS, {}, mode="paper", since=SINCE, until=UNTIL)
    assert rep.risk is not None
    assert rep.risk.starting_capital_usd == Decimal("250")  # 100+100+50
    assert rep.risk.total_return_pct == total_return_pct(_EQUITY)


def test_capital_override_changes_return() -> None:
    rep = compute_performance(
        _FILLS, {}, mode="paper", since=SINCE, until=UNTIL,
        starting_capital=Decimal("1000"),
    )
    assert rep.risk is not None
    assert rep.risk.starting_capital_usd == Decimal("1000")
    expected = [Decimal("1000"), Decimal("1030"), Decimal("1010"), Decimal("1020")]
    assert rep.risk.total_return_pct == total_return_pct(expected)


def test_no_closed_trades_risk_is_none() -> None:
    """매수만 있으면 청산 0건 → risk None, render 에 '거래 없음' (US2 AC2)."""
    fills = [_fill("AAPL", "BUY", 1, "100", "2026-05-20T00:00:00.000Z")]
    rep = compute_performance(fills, {}, mode="paper", since=SINCE, until=UNTIL)
    assert rep.risk is None
    assert "거래 없음" in render_text(rep)
    assert rep.to_json_dict()["risk"] is None


def test_loss_below_capital_degrades_curve_metrics() -> None:
    """실현 손실이 시작 자본을 초과해 자산이 0 이하가 되면 곡선 지표는 N/A,
    건당 지표(승률·평균손실)는 계속 정상 계산된다."""
    fills = [
        _fill("X", "BUY", 1, "100", "2026-05-20T00:00:00.000Z"),
        _fill("X", "SELL", 1, "10", "2026-05-20T01:00:00.000Z"),  # -90
    ]
    r = compute_risk_metrics(fills, starting_capital=Decimal("50"))
    assert r is not None
    assert r.closed_trades == 1
    assert r.win_rate == Decimal("0")
    assert r.avg_loss_usd == Decimal("-90")
    assert r.sharpe_ratio is None
    assert r.max_drawdown_pct is None
    assert r.total_return_pct is None


def test_render_includes_risk_section() -> None:
    rep = compute_performance(_FILLS, {}, mode="paper", since=SINCE, until=UNTIL)
    text = render_text(rep)
    assert "Risk-adjusted" in text
    assert "Sharpe" in text
    assert "Sortino" in text
    assert "Win rate" in text
