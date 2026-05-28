"""Risk-based position sizing (spec 017) — volatility-aware quantity scaling.

NON-KERNEL. This module only ever *proposes* a quantity; the K1 position caps
(`risk/gates.py`) remain the inviolable ceiling and run unchanged after sizing.
Slice 1 is volatility *throttling*: scale the rule's declared base quantity DOWN
when realized volatility exceeds a target, never up (scale clamped to <= 1). So
this can only reduce exposure relative to v1 fixed-qty — K1 still binds below.

All math is deterministic Decimal (no float, no LLM) so the backtest replay
stays byte-equal across machines (FR-B15) and live trading uses the identical
sizing as the backtest (constitution X.2, single yardstick).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_FLOOR, Decimal

from auto_invest.config.rules import SizingConfig

# Volatility / scale are normalised to 6 decimals to match the rest of the
# backtest's byte-equality contract (see backtest/data_model.canonicalise_decimal).
_QUANT = Decimal("0.000001")


def _canon(value: Decimal) -> Decimal:
    return value.quantize(_QUANT)


def realized_volatility(closes: Sequence[Decimal]) -> Decimal | None:
    """Sample standard deviation of simple per-bar returns, as a fraction.

    Returns None when there are fewer than two returns (need >= 3 closes) or
    any close is non-positive (a return is undefined). The result is a fraction
    (e.g. ``Decimal("0.015")`` for 1.5% per-bar volatility), normalised to 6 dp.
    """
    if len(closes) < 3:
        return None
    returns: list[Decimal] = []
    prev = closes[0]
    if prev <= 0:
        return None
    for close in closes[1:]:
        if close <= 0:
            return None
        returns.append(close / prev - Decimal(1))
        prev = close
    n = Decimal(len(returns))
    mean = sum(returns, Decimal(0)) / n
    # Sample variance (n-1 denominator). len(returns) >= 2 here.
    variance = sum(((r - mean) ** 2 for r in returns), Decimal(0)) / (n - Decimal(1))
    if variance <= 0:
        return Decimal(0)
    return _canon(variance.sqrt())


def volatility_scale(
    realized: Decimal,
    target: Decimal,
    *,
    min_scale: Decimal = Decimal(0),
) -> Decimal:
    """Throttle factor in ``[min_scale, 1]``.

    ``min(1, target / realized)`` clamped so the position is never sized above
    the declared base (slice-1 down-only invariant). A non-positive realized
    volatility means "no measurable risk to throttle", so the factor is 1.
    """
    if realized <= 0:
        return Decimal(1)
    raw = target / realized
    if raw > 1:
        raw = Decimal(1)
    if raw < min_scale:
        raw = min_scale
    return _canon(raw)


def sized_quantity(
    *,
    base_qty: int,
    closes: Sequence[Decimal],
    sizing: SizingConfig | None,
) -> int:
    """Final integer quantity after volatility throttling.

    When ``sizing`` is None or mode="fixed" the declared ``base_qty`` is returned
    unchanged (v1 behaviour, byte-equal). For mode="target_vol" the most recent
    ``lookback_bars`` returns set the realized volatility; if it cannot be
    measured the base qty is returned (fail-safe, FR-S04). The result is floored
    (never rounded up) and may be 0, which callers treat as "skip this fill"
    (FR-S05).
    """
    if sizing is None or sizing.mode == "fixed":
        return base_qty

    # Need lookback returns -> lookback + 1 closes; take the most recent tail.
    window = list(closes)[-(sizing.lookback_bars + 1) :]
    realized = realized_volatility(window)
    if realized is None:
        return base_qty  # fail-safe: not enough data to throttle

    target = sizing.target_volatility_pct / Decimal(100)
    scale = volatility_scale(realized, target, min_scale=sizing.min_scale)
    scaled = (Decimal(base_qty) * scale).to_integral_value(rounding=ROUND_FLOOR)
    result = int(scaled)
    return result if result > 0 else 0


__all__ = ["realized_volatility", "sized_quantity", "volatility_scale"]
