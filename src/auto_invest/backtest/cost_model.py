"""Backtest cost model v1 (T023).

Phase 3 implements commission + half-spread; Phase 4 (T035) adds the
square-root market-impact term and the participation cap. Each
component is itemised so the report and `orders.jsonl` show what
share of cost came from which mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from auto_invest.config.backtest import CostModel
from auto_invest.config.enums import Side


@dataclass(frozen=True)
class CostQuote:
    fill_price_usd: Decimal
    commission_usd: Decimal
    half_spread_usd: Decimal
    impact_usd: Decimal

    @property
    def total_cost_usd(self) -> Decimal:
        return self.commission_usd + self.half_spread_usd + self.impact_usd


def quote_cost(
    *,
    cost_model: CostModel,
    side: Side,
    qty: int,
    bar_close_usd: Decimal,
) -> CostQuote:
    """Phase 3 cost: commission + half-spread applied to a market-order fill.

    Phase 4 will overlay sqrt market-impact on top of this and clamp
    the fill quantity to the participation cap.
    """
    notional = bar_close_usd * Decimal(qty)
    commission = max(
        cost_model.commission_min_usd,
        notional * cost_model.commission_bps / Decimal(10000),
    )
    half_spread = notional * cost_model.half_spread_bps / Decimal(10000)
    # Phase 3 stub: zero market impact; Phase 4 adds it.
    impact = Decimal("0")

    # Buy fills land at `close + half_spread`; sell fills at `close - half_spread`.
    # The half_spread cost is the magnitude of that move.
    if side is Side.BUY:
        fill_price = bar_close_usd + (cost_model.half_spread_bps / Decimal(10000)) * bar_close_usd
    else:
        fill_price = bar_close_usd - (cost_model.half_spread_bps / Decimal(10000)) * bar_close_usd

    return CostQuote(
        fill_price_usd=fill_price,
        commission_usd=commission,
        half_spread_usd=half_spread,
        impact_usd=impact,
    )
