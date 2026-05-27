"""spec 016 슬라이스 2 — 단일 잣대 통일 (헌법 X.2) 교차 검증.

같은 논리적 체결 시퀀스를 (1) 백테스트 경로(replay.FillRecord → report._closed_trade_pnls)
와 (2) 라이브 성과 경로(performance.FillRecord → engine.realized_trades)에 각각 흘려보내
거래 단위 잣대(청산 손익·승률·손익비)가 **바이트 동일**한지 확인한다. 두 경로 모두
backtest/metrics.py 의 공용 정의를 호출하므로 잣대가 갈라질 수 없음을 증명한다.
"""

from __future__ import annotations

from decimal import Decimal

from auto_invest.backtest.metrics import win_loss_stats
from auto_invest.backtest.replay import FillRecord as BacktestFill
from auto_invest.backtest.report import _closed_trade_pnls
from auto_invest.performance.engine import FillRecord as LiveFill
from auto_invest.performance.engine import realized_trades

# (symbol, side, qty, price) — 승 +60, 패 -40, 승 +20 의 세 청산.
_TRADES = [
    ("AAPL", "BUY", 2, "100"),
    ("AAPL", "SELL", 2, "130"),  # +60
    ("AAPL", "BUY", 1, "100"),
    ("AAPL", "SELL", 1, "60"),  # -40
    ("MSFT", "BUY", 1, "50"),
    ("MSFT", "SELL", 1, "70"),  # +20
]


def _backtest_fills() -> list[BacktestFill]:
    return [
        BacktestFill(
            correlation_id=f"c-{i}",
            rule_id="r1",
            symbol=sym,
            side=side,
            qty=qty,
            fill_price_usd=price,
            executed_at_utc=f"2024-01-0{i + 1}T21:00:00.000Z",
            kis_fill_id=f"BT-{i}",
        )
        for i, (sym, side, qty, price) in enumerate(_TRADES)
    ]


def _live_fills() -> list[LiveFill]:
    return [
        LiveFill(
            symbol=sym,
            side=side,
            qty=qty,
            price_usd=Decimal(price),
            ts_utc=f"2024-01-0{i + 1}T21:00:00.000Z",
            rule_id="r1",
        )
        for i, (sym, side, qty, price) in enumerate(_TRADES)
    ]


def test_closed_trade_pnls_identical_across_engines() -> None:
    bt_pnls = _closed_trade_pnls(_backtest_fills())
    live_pnls = [t.pnl_usd for t in realized_trades(_live_fills())]
    assert bt_pnls == [Decimal("60"), Decimal("-40"), Decimal("20")]
    assert bt_pnls == live_pnls


def test_win_loss_stats_identical_across_engines() -> None:
    bt = win_loss_stats(_closed_trade_pnls(_backtest_fills()))
    live = win_loss_stats([t.pnl_usd for t in realized_trades(_live_fills())])
    assert bt == live
    assert bt.closed_trades == 3
    assert bt.win_rate == Decimal("2") / Decimal("3")
    assert bt.profit_factor == Decimal("2")  # gross win 80 / gross loss 40
