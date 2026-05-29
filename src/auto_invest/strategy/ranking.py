"""Cross-sectional momentum ranking (spec 021).

Ranks a universe of symbols by their N-period % return and exposes
helpers to test whether a given symbol sits in the top-N or top-pct
of that ranked universe.

NON-KERNEL. This module only ever *filters* (skips) a candidate order;
it never enlarges position size. K1 gates in `risk/gates.py` run
unchanged after any ranking check.

Deterministic: given identical bar data the ranking is identical across
machines and between live and backtest (constitution X.2).
"""

from __future__ import annotations

import math
from decimal import Decimal

from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.indicators import IndicatorError, momentum


def cross_sectional_momentum(
    symbol_bars: dict[str, list[PriceBar]],
    period: int,
) -> list[tuple[str, Decimal]]:
    """Rank symbols by N-period % return, best first.

    Symbols with insufficient bars (< period + 1) are included at the
    bottom of the list with a sentinel value so the caller still sees
    the full universe but data-poor symbols are never chosen over
    data-rich ones.

    Args:
        symbol_bars: mapping of symbol → bar list (ascending order).
        period: momentum lookback in bars.

    Returns:
        List of (symbol, pct_return) tuples sorted descending by return.
        Data-poor symbols appear last with ``Decimal("-Inf")``.
    """
    _SENTINEL = Decimal("-Inf")
    scored: list[tuple[str, Decimal]] = []
    for symbol, bars in symbol_bars.items():
        try:
            pct = momentum(bars, period)
        except IndicatorError:
            pct = _SENTINEL
        scored.append((symbol, pct))

    # Stable sort: deterministic tie-breaking by symbol name.
    scored.sort(key=lambda t: (float(t[1]), t[0]), reverse=True)
    return scored


def is_top_n(
    symbol: str,
    ranked: list[tuple[str, Decimal]],
    n: int,
) -> bool:
    """Return True if *symbol* is within the top-*n* of *ranked*.

    If *n* >= len(*ranked*) every symbol qualifies.
    Symbols absent from *ranked* are treated as bottom-ranked (False).
    """
    if n <= 0:
        return False
    cutoff = min(n, len(ranked))
    top_symbols = {s for s, _ in ranked[:cutoff]}
    return symbol in top_symbols


def is_top_pct(
    symbol: str,
    ranked: list[tuple[str, Decimal]],
    pct: float,
) -> bool:
    """Return True if *symbol* is within the top *pct* percent of *ranked*.

    ``top_n = max(1, ceil(len(ranked) * pct / 100))``

    Args:
        symbol: symbol to test.
        ranked: output of :func:`cross_sectional_momentum`.
        pct: percentage threshold, must be in (0, 100].
    """
    if not ranked:
        return False
    top_n = max(1, math.ceil(len(ranked) * pct / 100))
    return is_top_n(symbol, ranked, top_n)
