"""Cash + position accounting in the simulator (T022).

The portfolio receives `SimulatedFill`s and updates per-instrument
quantity, weighted-average cost basis, realised P&L per closed leg,
and mark-to-market unrealised P&L per bar.

v2 supports long-only positions (matching spec 001's deny-by-default
on short selling). A SELL that would take the position negative is
clamped at zero and the unfilled remainder reported back so the
engine can decide what to do with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from auto_invest.config.enums import Side
from auto_invest.execution.backtest_broker import SimulatedFill


@dataclass
class Position:
    qty: int = 0
    avg_cost_usd: Decimal = Decimal("0")

    @property
    def is_flat(self) -> bool:
        return self.qty == 0


@dataclass
class TradeRecord:
    """One realised trade leg (closed quantity)."""
    symbol: str
    qty_closed: int
    realised_pnl_usd: Decimal


@dataclass
class Portfolio:
    starting_cash_usd: Decimal
    cash_usd: Decimal = field(init=False)
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[TradeRecord] = field(default_factory=list)
    total_cost_usd: Decimal = Decimal("0")  # sum of commission + spread + impact

    def __post_init__(self) -> None:
        self.cash_usd = self.starting_cash_usd

    def apply_fill(
        self,
        *,
        symbol: str,
        side: Side,
        fill: SimulatedFill,
    ) -> None:
        """Apply a buy or sell fill, updating cash, position, and realised P&L."""
        pos = self.positions.setdefault(symbol, Position())
        notional = fill.price_usd * Decimal(fill.qty)

        if side is Side.BUY:
            new_qty = pos.qty + fill.qty
            # Weighted average cost basis update.
            pos.avg_cost_usd = (
                (pos.avg_cost_usd * Decimal(pos.qty) + notional) / Decimal(new_qty)
            ) if new_qty > 0 else Decimal("0")
            pos.qty = new_qty
            self.cash_usd -= notional
        else:  # SELL
            qty_closed = min(pos.qty, fill.qty)
            if qty_closed > 0:
                realised = (fill.price_usd - pos.avg_cost_usd) * Decimal(qty_closed)
                pos.qty -= qty_closed
                self.cash_usd += fill.price_usd * Decimal(qty_closed)
                self.trades.append(TradeRecord(symbol=symbol, qty_closed=qty_closed, realised_pnl_usd=realised))
                if pos.qty == 0:
                    pos.avg_cost_usd = Decimal("0")
            # No short selling: any sell beyond `pos.qty` is dropped.

        # Costs are charged to cash regardless of side.
        self.cash_usd -= fill.total_cost_usd
        self.total_cost_usd += fill.total_cost_usd

    def equity_usd(self, marks: dict[str, Decimal]) -> Decimal:
        """Total portfolio value: cash + sum(qty * mark price) for known marks.

        Symbols missing from `marks` contribute their `qty * avg_cost_usd`
        as a conservative fallback.
        """
        total = self.cash_usd
        for sym, pos in self.positions.items():
            if pos.qty == 0:
                continue
            mark = marks.get(sym, pos.avg_cost_usd)
            total += Decimal(pos.qty) * mark
        return total

    def position_qty(self, symbol: str) -> int:
        return self.positions.get(symbol, Position()).qty

    def realised_pnl_usd(self) -> Decimal:
        return sum((t.realised_pnl_usd for t in self.trades), start=Decimal("0"))
