"""T018 — adapter_id boundary + leak detection for the backtest broker.

FR-B06: every artefact produced via BacktestBroker carries
`adapter_id == "backtest-mock-v1"`. A non-mock adapter reaching the
router during a backtest raises `BacktestLiveBrokerLeakError`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from auto_invest.backtest.broker_mock import (
    ADAPTER_ID,
    BacktestBroker,
    BacktestLiveBrokerLeakError,
    assert_backtest_adapter,
)
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.broker.models import OrderRequest
from auto_invest.config.enums import OrderType, Side


def _bar() -> OHLCVBar:
    return OHLCVBar(
        symbol="AAPL",
        session_date=date(2024, 1, 2),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=10_000,
        session_schedule_tag="regular",
    )


def _req() -> OrderRequest:
    return OrderRequest(
        account="ACC",
        symbol="AAPL",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        qty=100,
        limit_price_usd=Decimal("99.50"),
    )


_NOW = datetime(2024, 1, 2, 21, 0, tzinfo=UTC)


def test_adapter_id_constant() -> None:
    assert ADAPTER_ID == "backtest-mock-v1"
    broker = BacktestBroker()
    assert broker.adapter_id == "backtest-mock-v1"


def test_assert_backtest_adapter_accepts_mock() -> None:
    assert_backtest_adapter("backtest-mock-v1")  # no raise


@pytest.mark.parametrize(
    "leaked_id",
    ["kis-prod-v1", "kis-paper-v1", "alpaca", "", "BACKTEST-MOCK-V1"],
)
def test_assert_backtest_adapter_rejects_non_mock(leaked_id: str) -> None:
    with pytest.raises(BacktestLiveBrokerLeakError) as exc:
        assert_backtest_adapter(leaked_id)
    assert leaked_id in str(exc.value)
    assert "backtest-mock-v1" in str(exc.value)


def test_submit_order_returns_unique_kis_order_id() -> None:
    broker = BacktestBroker()
    bar = _bar()
    out1 = broker.submit_order(_req(), now=_NOW, bar=bar)
    out2 = broker.submit_order(_req(), now=_NOW, bar=bar)
    assert out1.result.kis_order_id != out2.result.kis_order_id
    assert out1.result.kis_order_id.startswith("BT-ORD-")


def test_fills_carry_unique_kis_fill_id() -> None:
    broker = BacktestBroker()
    bar = _bar()
    out1 = broker.submit_order(_req(), now=_NOW, bar=bar)
    out2 = broker.submit_order(_req(), now=_NOW, bar=bar)
    assert out1.fill is not None
    assert out2.fill is not None
    assert out1.fill.kis_fill_id != out2.fill.kis_fill_id
    assert out1.fill.kis_fill_id.startswith("BT-FILL-")


def test_cancel_order_removes_from_open_list() -> None:
    broker = BacktestBroker()
    # Untouched limit → stays open.
    bar = OHLCVBar(
        symbol="AAPL",
        session_date=date(2024, 1, 2),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("100.00"),
        close=Decimal("100.50"),
        volume=10_000,
        session_schedule_tag="regular",
    )
    out = broker.submit_order(_req(), now=_NOW, bar=bar)
    assert out.open_order is not None
    cancelled = broker.cancel_order(out.result.kis_order_id)
    assert cancelled is not None
    assert broker.list_open_orders() == []


def test_cancel_unknown_order_returns_none() -> None:
    broker = BacktestBroker()
    assert broker.cancel_order("BT-ORD-doesnotexist") is None


def test_fills_history_accumulates() -> None:
    broker = BacktestBroker()
    bar = _bar()
    broker.submit_order(_req(), now=_NOW, bar=bar)
    broker.submit_order(_req(), now=_NOW, bar=bar)
    assert len(broker.fills()) == 2
