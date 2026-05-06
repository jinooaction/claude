"""Simulated broker for the backtest engine (T021).

Implements the same `place_order` contract surface as the live KIS
adapter, but its fill behaviour is determined by the bar context
(`open/high/low/close/volume`) and the cost model. Phase 3 wires the
cost model in (T024); this module's Phase 2 contribution is the
protocol object so the engine can be wired without circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

from auto_invest.broker.models import OrderRequest, OrderResult
from auto_invest.market_data.revisions import HistoricalBar


@runtime_checkable
class BrokerProtocol(Protocol):
    """Both the live KIS path and the backtest path implement this."""

    async def place_order(self, *args, **kwargs) -> OrderResult: ...  # noqa: D401, E501


@dataclass(frozen=True)
class SimulatedFill:
    """One simulated fill produced by the backtest broker."""

    price_usd: Decimal
    qty: int
    commission_usd: Decimal
    half_spread_usd: Decimal
    impact_usd: Decimal

    @property
    def total_cost_usd(self) -> Decimal:
        return self.commission_usd + self.half_spread_usd + self.impact_usd


@dataclass
class BacktestBroker:
    """Default-allow simulated broker.

    Phase 2 leaves the fill model trivial (fill at bar close, zero
    cost). Phase 3 (T023, T024) replaces `simulate_fill` with the
    cost-model-driven implementation.
    """

    cost_model: object | None = None  # CostModel; typed loosely to avoid circular import
    halt_flag: bool = field(default=False)

    def simulate_fill(self, request: OrderRequest, bar: HistoricalBar) -> SimulatedFill | None:
        """Phase 2 placeholder: fill at bar close, zero cost.

        Phase 3 replaces this with full cost-model-driven simulation.
        Returns None when the bar cannot satisfy the order (e.g.,
        limit price out of range).
        """
        if self.halt_flag:
            return None
        return SimulatedFill(
            price_usd=bar.close,
            qty=request.qty,
            commission_usd=Decimal("0"),
            half_spread_usd=Decimal("0"),
            impact_usd=Decimal("0"),
        )
