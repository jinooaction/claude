"""T021 — backtest broker conforms to the same protocol as the live one."""

from __future__ import annotations

from auto_invest.config.backtest import CostModel
from auto_invest.execution.backtest_broker import BacktestBroker


def test_backtest_broker_protocol_surface() -> None:
    broker = BacktestBroker(cost_model=CostModel())
    # The runtime_checkable Protocol only checks attribute presence; the
    # backtest broker's `simulate_fill` is the documented entry point and
    # must exist before Phase 3's engine wires it.
    assert hasattr(broker, "simulate_fill")
    assert hasattr(broker, "cost_model")
    assert hasattr(broker, "halt_flag")
