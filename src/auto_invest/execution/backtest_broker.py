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
from auto_invest.config.backtest import CostModel
from auto_invest.config.enums import OrderType
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
    """Cost-model-driven simulated broker (Phase 3, T024).

    Phase 4 (T035-T036) layers point-in-time enforcement on the read
    side, square-root market impact, participation cap, and limit-
    order time-in-force handling.
    """

    cost_model: CostModel
    halt_flag: bool = field(default=False)

    def simulate_fill(
        self,
        request: OrderRequest,
        bar: HistoricalBar,
    ) -> SimulatedFill | None:
        """Simulate a fill against `bar` using the cost model.

        Phase 3 simplifications:
          * MARKET orders fill at bar close ± half-spread.
          * LIMIT orders fill iff the limit price is inside the bar's
            high-low range. Buy limits fill at `min(limit, close+spread)`,
            sell limits at `max(limit, close-spread)`. (Phase 4 hardens
            this with proper TIF semantics.)
        """
        if self.halt_flag:
            return None

        from auto_invest.backtest.cost_model import quote_cost

        per_symbol = self.cost_model.for_symbol(request.symbol)
        cost = quote_cost(
            cost_model=per_symbol,
            side=request.side,
            qty=request.qty,
            bar_close_usd=bar.close,
        )

        fill_price = cost.fill_price_usd
        if request.order_type is OrderType.LIMIT:
            if request.limit_price_usd is None:
                return None
            in_range = bar.low <= request.limit_price_usd <= bar.high
            if not in_range:
                return None
            # Use the more conservative of (limit, close±half_spread).
            if request.side.value == "BUY":
                fill_price = min(request.limit_price_usd, cost.fill_price_usd)
            else:
                fill_price = max(request.limit_price_usd, cost.fill_price_usd)

        return SimulatedFill(
            price_usd=fill_price,
            qty=request.qty,
            commission_usd=cost.commission_usd,
            half_spread_usd=cost.half_spread_usd,
            impact_usd=cost.impact_usd,
        )
