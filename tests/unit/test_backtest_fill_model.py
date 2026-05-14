"""T017 — exhaustive coverage of R-B3 pessimistic zero-slippage fill model.

Matrix:

    side x order_type x (price-touched / price-untouched) x (volume-ok / short)

Plus:
    - fill price is min(limit, bar.open) for BUY  / max(limit, bar.open) for SELL
    - tie-break when limit exactly equals bar.open
    - GTC re-attempt on the next bar
    - DAY expiry at session close
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from auto_invest.backtest.broker_mock import BacktestBroker
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.broker.models import OrderRequest
from auto_invest.config.enums import OrderType, Side


def _bar(
    *,
    open_: str = "100.00",
    high: str = "101.00",
    low: str = "99.00",
    close: str = "100.50",
    volume: int = 10_000,
    symbol: str = "AAPL",
) -> OHLCVBar:
    return OHLCVBar(
        symbol=symbol,
        session_date=date(2024, 1, 2),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        session_schedule_tag="regular",
    )


def _req(
    *,
    side: Side = Side.BUY,
    order_type: OrderType = OrderType.LIMIT,
    qty: int = 100,
    limit: str | None = "100.00",
    symbol: str = "AAPL",
) -> OrderRequest:
    return OrderRequest(
        account="ACC",
        symbol=symbol,
        side=side,
        order_type=order_type,
        qty=qty,
        limit_price_usd=Decimal(limit) if limit is not None else None,
    )


_NOW = datetime(2024, 1, 2, 21, 0, tzinfo=UTC)


# ---------- BUY LIMIT ----------------------------------------------------


def test_buy_limit_touched_volume_ok_fills_at_min_limit_open() -> None:
    bar = _bar(open_="100.00", low="98.00", high="101.00", volume=10_000)
    req = _req(side=Side.BUY, limit="99.50", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    # bar.low (98) <= limit (99.50) → touched. min(99.50, 100.00) = 99.50.
    assert outcome.fill.fill_price_usd == Decimal("99.50")
    assert outcome.open_order is None
    assert broker.list_open_orders() == []


def test_buy_limit_open_below_limit_fills_at_open() -> None:
    """When the open is favourable (below the BUY limit) the fill is at open."""
    bar = _bar(open_="98.00", low="97.00", high="101.00", volume=10_000)
    req = _req(side=Side.BUY, limit="99.50", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    assert outcome.fill.fill_price_usd == Decimal("98.00")  # min(99.50, 98.00)


def test_buy_limit_untouched_remains_open() -> None:
    bar = _bar(open_="100.00", low="100.00", high="101.00", volume=10_000)
    req = _req(side=Side.BUY, limit="99.50", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is None
    assert outcome.open_order is not None
    assert len(broker.list_open_orders()) == 1


def test_buy_limit_volume_short_remains_open() -> None:
    bar = _bar(open_="100.00", low="98.00", high="101.00", volume=50)
    req = _req(side=Side.BUY, limit="99.50", qty=100)  # volume 50 < qty 100
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is None
    assert outcome.open_order is not None


def test_buy_limit_exactly_at_low_fills() -> None:
    """Boundary: limit == bar.low is 'touched' (use of <=, not <)."""
    bar = _bar(open_="100.00", low="99.50", high="101.00", volume=10_000)
    req = _req(side=Side.BUY, limit="99.50", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    assert outcome.fill.fill_price_usd == Decimal("99.50")


def test_buy_limit_exactly_at_open_fills_at_open() -> None:
    """Tie-break: limit == bar.open. min(limit, open) == both → use that value."""
    bar = _bar(open_="100.00", low="98.00", high="101.00", volume=10_000)
    req = _req(side=Side.BUY, limit="100.00", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    assert outcome.fill.fill_price_usd == Decimal("100.00")


# ---------- SELL LIMIT ---------------------------------------------------


def test_sell_limit_touched_volume_ok_fills_at_max_limit_open() -> None:
    bar = _bar(open_="100.00", low="99.00", high="102.00", volume=10_000)
    req = _req(side=Side.SELL, limit="101.00", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    # bar.high (102) >= limit (101) → touched. max(101, 100) = 101.
    assert outcome.fill.fill_price_usd == Decimal("101.00")


def test_sell_limit_open_above_limit_fills_at_open() -> None:
    """Favourable open (above SELL limit) → fill at open."""
    bar = _bar(open_="103.00", low="99.00", high="105.00", volume=10_000)
    req = _req(side=Side.SELL, limit="101.00", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    assert outcome.fill.fill_price_usd == Decimal("103.00")  # max(101, 103)


def test_sell_limit_untouched_remains_open() -> None:
    bar = _bar(open_="100.00", low="99.00", high="100.50", volume=10_000)
    req = _req(side=Side.SELL, limit="101.00", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is None
    assert outcome.open_order is not None


def test_sell_limit_volume_short_remains_open() -> None:
    bar = _bar(open_="100.00", low="99.00", high="102.00", volume=50)
    req = _req(side=Side.SELL, limit="101.00", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is None


def test_sell_limit_exactly_at_high_fills() -> None:
    bar = _bar(open_="100.00", low="99.00", high="101.00", volume=10_000)
    req = _req(side=Side.SELL, limit="101.00", qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    assert outcome.fill.fill_price_usd == Decimal("101.00")


# ---------- MARKET (defensive worst-case) --------------------------------


def test_market_buy_fills_at_high_when_volume_ok() -> None:
    bar = _bar(open_="100.00", low="99.00", high="101.50", volume=10_000)
    req = _req(side=Side.BUY, order_type=OrderType.MARKET, limit=None, qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    assert outcome.fill.fill_price_usd == Decimal("101.50")


def test_market_sell_fills_at_low_when_volume_ok() -> None:
    bar = _bar(open_="100.00", low="98.50", high="101.00", volume=10_000)
    req = _req(side=Side.SELL, order_type=OrderType.MARKET, limit=None, qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is not None
    assert outcome.fill.fill_price_usd == Decimal("98.50")


def test_market_volume_short_remains_open() -> None:
    bar = _bar(volume=50)
    req = _req(side=Side.BUY, order_type=OrderType.MARKET, limit=None, qty=100)
    broker = BacktestBroker()

    outcome = broker.submit_order(req, now=_NOW, bar=bar)

    assert outcome.fill is None
    assert outcome.open_order is not None


# ---------- TIF: DAY vs GTC ----------------------------------------------


def test_day_order_expires_at_session_close() -> None:
    bar = _bar(open_="100.00", low="100.00", high="101.00", volume=10_000)
    broker = BacktestBroker()
    broker.submit_order(_req(limit="99.00"), now=_NOW, bar=bar, time_in_force="DAY")

    expired = broker.expire_day_orders(now=_NOW)

    assert len(expired) == 1
    assert broker.list_open_orders() == []


def test_gtc_order_carries_to_next_session_and_can_fill_there() -> None:
    bar1 = _bar(open_="100.00", low="100.00", high="101.00", volume=10_000)
    bar2 = OHLCVBar(
        symbol="AAPL",
        session_date=date(2024, 1, 3),
        open=Decimal("99.50"),
        high=Decimal("100.00"),
        low=Decimal("98.00"),
        close=Decimal("99.00"),
        volume=10_000,
        session_schedule_tag="regular",
    )
    broker = BacktestBroker()

    out1 = broker.submit_order(
        _req(limit="99.00"), now=_NOW, bar=bar1, time_in_force="GTC"
    )
    assert out1.fill is None

    # End of day 1 — GTC should NOT be expired.
    expired = broker.expire_day_orders(now=_NOW)
    assert expired == []
    assert len(broker.list_open_orders()) == 1

    # Day 2 fills.
    fills = broker.try_fill_open_orders(
        bar2, now=datetime(2024, 1, 3, 21, 0, tzinfo=UTC)
    )
    assert len(fills) == 1
    assert fills[0].fill_price_usd == Decimal("99.00")
    assert broker.list_open_orders() == []


def test_try_fill_open_orders_only_matches_same_symbol() -> None:
    broker = BacktestBroker()
    bar_aapl = _bar(symbol="AAPL", open_="100.00", low="100.00", volume=10_000)
    bar_msft = _bar(
        symbol="MSFT",
        open_="50.00",
        low="48.00",
        high="51.00",
        close="50.00",
        volume=10_000,
    )

    broker.submit_order(
        _req(symbol="AAPL", limit="99.00"), now=_NOW, bar=bar_aapl, time_in_force="GTC"
    )
    fills = broker.try_fill_open_orders(bar_msft, now=_NOW)

    assert fills == []
    assert len(broker.list_open_orders()) == 1


def test_bar_symbol_mismatch_raises() -> None:
    broker = BacktestBroker()
    bar = _bar(symbol="AAPL")
    req = _req(symbol="MSFT", limit="50.00")

    with pytest.raises(ValueError, match="does not match"):
        broker.submit_order(req, now=_NOW, bar=bar)
