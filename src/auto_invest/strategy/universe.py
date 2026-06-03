"""Systematic universe construction by liquidity (spec 034).

World-class systematic equity does not hand-pick a handful of tickers; it
*constructs* a tradeable universe from the investable cross-section, filtered by
liquidity (you can only trade what you can get in and out of) and by sufficient
price history (you can only rank what you can measure). This module turns a raw
set of per-symbol bars into a deterministic, liquidity-ranked universe that the
cross-sectional alpha stack (spec 021 ranking, spec 025 composite, spec 032
rebalance) can then express an edge across.

NON-KERNEL. Selection-only: this module only decides *which symbols are even
considered*; it never sizes or places an order. The K1 caps in `risk/gates.py`
and the deny-by-default whitelist (principle II) run unchanged afterwards — a
constructed universe is still intersected with the operator whitelist before any
real order, so universe construction can never widen the live trading set beyond
the whitelist.

Liquidity proxy: the **median** daily dollar volume (close × volume) over the
most recent ``lookback_bars`` sessions. Median (not mean) is used so a single
abnormal print does not promote an otherwise thin name. Deterministic Decimal
(2 dp) so identical bars produce an identical universe and live == backtest
(constitution X.2).
"""

from __future__ import annotations

from decimal import Decimal

from auto_invest.market_data.store import PriceBar

# Sorted last: a symbol with no usable bars must never be chosen over one with
# real liquidity data.
_SENTINEL = Decimal("-1")
_QUANT = Decimal("0.01")


def median_dollar_volume(
    bars: list[PriceBar], *, lookback_bars: int = 60
) -> Decimal | None:
    """Median daily dollar volume (close × volume) over the most recent bars.

    Args:
        bars: ascending bar list for one symbol.
        lookback_bars: how many most-recent sessions to measure. When fewer
            bars exist, every available bar is used.

    Returns:
        Median dollar volume as a Decimal quantized to 2 dp, or ``None`` when
        the symbol has no bars at all.
    """
    if not bars:
        return None
    window = bars[-lookback_bars:] if len(bars) >= lookback_bars else bars
    dollar_volumes = sorted(b.close_usd * Decimal(b.volume) for b in window)
    n = len(dollar_volumes)
    mid = n // 2
    if n % 2 == 1:
        median = dollar_volumes[mid]
    else:
        median = (dollar_volumes[mid - 1] + dollar_volumes[mid]) / Decimal(2)
    return median.quantize(_QUANT)


def liquidity_rank(
    symbol_bars: dict[str, list[PriceBar]], *, lookback_bars: int = 60
) -> list[tuple[str, Decimal]]:
    """Rank a universe by median dollar volume, most liquid first.

    Symbols with no usable bars are included at the bottom with a sentinel so
    the caller still sees the full input set but data-poor names are never
    chosen over data-rich ones.

    Returns:
        List of (symbol, median_dollar_volume) sorted descending by liquidity;
        ties broken by symbol name. Data-poor symbols appear last.
    """
    scored: list[tuple[str, Decimal]] = []
    for symbol, bars in symbol_bars.items():
        mdv = median_dollar_volume(bars, lookback_bars=lookback_bars)
        scored.append((symbol, mdv if mdv is not None else _SENTINEL))
    # Deterministic: descending liquidity, tie-break by symbol name ascending.
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored


def select_universe(
    symbol_bars: dict[str, list[PriceBar]],
    *,
    top_n: int,
    min_dollar_volume: Decimal = Decimal(0),
    min_history_bars: int = 0,
    lookback_bars: int = 60,
) -> list[str]:
    """Construct a tradeable universe: the top-N most liquid eligible symbols.

    Eligibility (both required):
      * **enough history** — at least ``min_history_bars`` bars, so the
        cross-sectional alpha lookbacks (momentum / quality / vol) can be
        computed; and
      * **enough liquidity** — median dollar volume ≥ ``min_dollar_volume``.

    The eligible set is ranked by liquidity and the top ``top_n`` are kept.

    Args:
        symbol_bars: mapping of symbol → ascending bar list.
        top_n: maximum universe size (the N most liquid eligible symbols).
        min_dollar_volume: liquidity floor (median dollar volume).
        min_history_bars: minimum number of bars a symbol must have.
        lookback_bars: window for the liquidity median.

    Returns:
        Alphabetically sorted list of selected symbols (deterministic, stable
        for writing into a config). Empty when nothing is eligible.
    """
    eligible: dict[str, list[PriceBar]] = {
        sym: bars
        for sym, bars in symbol_bars.items()
        if len(bars) >= min_history_bars
    }
    ranked = liquidity_rank(eligible, lookback_bars=lookback_bars)
    selected = [
        sym
        for sym, mdv in ranked
        if mdv >= min_dollar_volume and mdv != _SENTINEL
    ][:top_n]
    return sorted(selected)


__all__ = ["median_dollar_volume", "liquidity_rank", "select_universe"]
