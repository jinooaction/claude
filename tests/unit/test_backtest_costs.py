"""Unit tests for the backtest transaction-cost model (spec 016).

Covers SC-C04 (slippage direction), SC-C05 (commission floor), SC-C03
(zero model is an identity), and the 6dp canonicalisation/determinism
that keeps the FR-B15 byte-equality contract intact.
"""

from __future__ import annotations

from decimal import Decimal

from auto_invest.backtest.costs import BacktestCostModel
from auto_invest.config.enums import Side


def test_zero_model_is_identity() -> None:
    m = BacktestCostModel.zero()
    assert m.is_zero
    price = Decimal("100")
    assert m.effective_fill_price(Side.BUY, price) == Decimal("100.000000")
    assert m.effective_fill_price(Side.SELL, price) == Decimal("100.000000")
    assert m.commission_usd(10, price) == Decimal("0.000000")


def test_kis_default_is_non_zero() -> None:
    m = BacktestCostModel.kis_default()
    assert not m.is_zero
    assert m.commission_bps == Decimal("25")
    assert m.slippage_bps == Decimal("5")


def test_slippage_direction_buy_pays_up_sell_receives_less() -> None:
    m = BacktestCostModel(slippage_bps=Decimal("50"))  # 0.50%
    price = Decimal("100")
    buy = m.effective_fill_price(Side.BUY, price)
    sell = m.effective_fill_price(Side.SELL, price)
    assert buy == Decimal("100.500000")  # 100 * 1.005
    assert sell == Decimal("99.500000")  # 100 * 0.995
    assert buy > price > sell


def test_commission_is_proportional_to_notional() -> None:
    m = BacktestCostModel(commission_bps=Decimal("25"))  # 0.25%
    # 10 shares * $100 = $1000 notional; 0.25% = $2.50
    assert m.commission_usd(10, Decimal("100")) == Decimal("2.500000")


def test_commission_floor_replaces_small_proportional() -> None:
    m = BacktestCostModel(commission_bps=Decimal("25"), min_commission_usd=Decimal("5"))
    # 1 share * $100 = $100 notional; 0.25% = $0.25 < $5 floor.
    assert m.commission_usd(1, Decimal("100")) == Decimal("5.000000")
    # Large notional: proportional ($25) exceeds the floor.
    assert m.commission_usd(100, Decimal("100")) == Decimal("25.000000")


def test_outputs_are_canonical_6dp() -> None:
    m = BacktestCostModel.kis_default()
    eff = m.effective_fill_price(Side.BUY, Decimal("123.456789"))
    comm = m.commission_usd(7, Decimal("123.456789"))
    assert len(str(eff).split(".")[1]) == 6
    assert len(str(comm).split(".")[1]) == 6


def test_describe_is_stable() -> None:
    m = BacktestCostModel.kis_default()
    assert m.describe() == (
        "commission=25.000000bps,slippage=5.000000bps,min_commission=0.000000usd"
    )
