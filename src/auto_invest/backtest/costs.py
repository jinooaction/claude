"""Backtest transaction-cost model (spec 016).

Implements the cost overlay that makes the backtest yardstick honest, per
constitution principle VI ("backtests systematically overstate performance
because they cannot model slippage or partial fills") and principle X.2
(one yardstick across live / paper / canary / backtest).

The broker mock (`broker_mock.py`) keeps its mechanical pessimistic limit
fill; this module layers realistic costs on top inside the replay loop:

  - slippage: the fill executes at a worse price than the broker's nominal
    fill (BUY pays up, SELL receives less), expressed in basis points.
  - commission: a fee proportional to fill notional (basis points) with a
    per-fill floor, deducted from cash separately from the price.

All outputs are canonicalised to 6 dp via `canonicalise_decimal` so the
FR-B15 byte-equality contract for `metrics.csv` survives the cost overlay.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from auto_invest.config.enums import Side

from .data_model import canonicalise_decimal

_BPS_DENOM = Decimal("10000")

# KIS overseas (US) equity online defaults. These are conservative,
# realistic starting points — the operator MUST set their actual KIS fee
# schedule via the CLI flags. ~0.25% per-side commission, 5 bps slippage.
_KIS_COMMISSION_BPS = Decimal("25")
_KIS_SLIPPAGE_BPS = Decimal("5")
_KIS_MIN_COMMISSION_USD = Decimal("0")


@dataclass(frozen=True)
class BacktestCostModel:
    """Deterministic per-fill transaction-cost model.

    commission_bps: per-side commission as basis points of fill notional.
    slippage_bps: adverse price move applied to each fill, in basis points.
    min_commission_usd: per-fill commission floor (KIS charges a minimum).
    """

    commission_bps: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    min_commission_usd: Decimal = Decimal("0")

    @classmethod
    def zero(cls) -> BacktestCostModel:
        """No costs — preserves the legacy cost-free backtest behaviour."""
        return cls()

    @classmethod
    def kis_default(cls) -> BacktestCostModel:
        """Realistic KIS US-equity defaults (the honest production default)."""
        return cls(
            commission_bps=_KIS_COMMISSION_BPS,
            slippage_bps=_KIS_SLIPPAGE_BPS,
            min_commission_usd=_KIS_MIN_COMMISSION_USD,
        )

    @property
    def is_zero(self) -> bool:
        return (
            self.commission_bps == 0
            and self.slippage_bps == 0
            and self.min_commission_usd == 0
        )

    def effective_fill_price(self, side: Side, raw_price: Decimal) -> Decimal:
        """Worsen the broker's nominal fill price by `slippage_bps`.

        BUY fills higher (you pay up), SELL fills lower (you receive less).
        Returns a 6dp-canonical Decimal.
        """
        if self.slippage_bps == 0:
            return Decimal(canonicalise_decimal(raw_price))
        factor = self.slippage_bps / _BPS_DENOM
        if side is Side.BUY:
            adjusted = raw_price * (Decimal("1") + factor)
        else:
            adjusted = raw_price * (Decimal("1") - factor)
        return Decimal(canonicalise_decimal(adjusted))

    def commission_usd(self, qty: int, fill_price: Decimal) -> Decimal:
        """Commission for one fill: max(floor, notional × commission_bps).

        Returns a 6dp-canonical Decimal. Always non-negative.
        """
        notional = Decimal(qty) * fill_price
        proportional = notional * self.commission_bps / _BPS_DENOM
        commission = max(proportional, self.min_commission_usd)
        return Decimal(canonicalise_decimal(commission))

    def describe(self) -> str:
        """Stable one-line descriptor for the run header / audit forensics."""
        return (
            f"commission={canonicalise_decimal(self.commission_bps)}bps,"
            f"slippage={canonicalise_decimal(self.slippage_bps)}bps,"
            f"min_commission={canonicalise_decimal(self.min_commission_usd)}usd"
        )


__all__ = ["BacktestCostModel"]
