"""Multi-factor composite alpha score (spec 025).

Combines several cross-sectional factors into ONE composite z-score so the
universe is ranked by a *blended* signal rather than by one factor at a time.
World-class systematic equity standardises each factor across the universe
(z-score), weights them, and sums — so a name that is merely good on several
factors is preferred over a name that is extreme on one. This generalises the
single-factor filters of spec 021 (momentum) and spec 023 (quality), which when
combined behave as an AND of independent top-N cutoffs and discard cross-factor
information.

NON-KERNEL. Selection-only: a composite filter can *skip* a candidate order,
never enlarge it. K1 cap gates (`risk/gates.py`) run unchanged afterwards.

Deterministic Decimal (6 dp) so identical bars produce an identical ranking and
live == backtest (constitution X.2).

Supported factors (price-only — no external fundamentals needed):
  * ``"momentum"``       — N-period % return (time-series momentum; higher better)
  * ``"quality"``        — rolling Sharpe / (1 + |maxDD|) (spec 023; higher better)
  * ``"low_volatility"`` — negative realized volatility (low-vol anomaly; a lower
                           vol yields a higher score)
  * ``"mean_reversion"`` — negative Bollinger %B (oversold = high score)
"""

from __future__ import annotations

from decimal import Decimal

from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.indicators import (
    IndicatorError,
    bollinger_band_pct_b,
    momentum,
)
from auto_invest.strategy.quality import price_quality_score
from auto_invest.strategy.sizing import realized_volatility

# Canonical factor names. `config/rules.py` keeps a matching
# `KNOWN_COMPOSITE_FACTORS` literal (it cannot import this module without a
# circular import via strategy.sizing -> config.rules); a unit test asserts the
# two stay in sync (FR-C05 / SC-08).
KNOWN_FACTORS: tuple[str, ...] = (
    "momentum",
    "quality",
    "low_volatility",
    "mean_reversion",
)

_SENTINEL = Decimal("-Inf")
_QUANT = Decimal("0.000001")


# ----------------------------------------------------------- factor raw values
# Each extractor returns a per-symbol raw Decimal, or None when the symbol lacks
# enough data for that factor. None excludes the symbol from that factor's
# z-score AND (because every active factor is required) drops it to the sentinel
# rank — never chosen over a data-complete symbol.


def _raw_momentum(bars: list[PriceBar], *, period: int) -> Decimal | None:
    try:
        return momentum(bars, period)
    except IndicatorError:
        return None


def _raw_quality(bars: list[PriceBar], *, lookback_bars: int) -> Decimal | None:
    score = price_quality_score(bars, lookback_bars=lookback_bars)
    # price_quality_score returns the -Inf sentinel on insufficient data.
    return None if score == _SENTINEL else score


def _raw_low_volatility(bars: list[PriceBar], *, lookback_bars: int) -> Decimal | None:
    window = bars[-lookback_bars:] if len(bars) >= lookback_bars else bars
    vol = realized_volatility([b.close_usd for b in window])
    if vol is None:
        return None
    # Low-volatility anomaly: lower realized vol → higher (better) score.
    return -vol


def _raw_mean_reversion(
    bars: list[PriceBar], *, period: int, std_dev: float
) -> Decimal | None:
    try:
        pct_b = bollinger_band_pct_b(bars, period=period, std_dev=std_dev)
    except IndicatorError:
        return None
    # Oversold (low %B) → higher (better) mean-reversion score.
    return -pct_b


def _factor_raw(
    factor: str,
    bars: list[PriceBar],
    *,
    lookback_bars: int,
    momentum_period: int,
    bb_period: int,
    bb_std: float,
) -> Decimal | None:
    if factor == "momentum":
        return _raw_momentum(bars, period=momentum_period)
    if factor == "quality":
        return _raw_quality(bars, lookback_bars=lookback_bars)
    if factor == "low_volatility":
        return _raw_low_volatility(bars, lookback_bars=lookback_bars)
    if factor == "mean_reversion":
        return _raw_mean_reversion(bars, period=bb_period, std_dev=bb_std)
    raise ValueError(f"unknown composite factor: {factor!r}")


# ----------------------------------------------------------- cross-sectional z


def zscore(values: dict[str, Decimal]) -> dict[str, Decimal]:
    """Cross-sectional z-score over the symbols that have a finite value.

    Uses the population standard deviation (divide by N). When the standard
    deviation is zero (every value equal) every z-score is 0. Deterministic
    Decimal, quantized to 6 dp.
    """
    n = len(values)
    if n == 0:
        return {}
    count = Decimal(n)
    mean = sum(values.values(), Decimal(0)) / count
    var = sum(((v - mean) * (v - mean) for v in values.values()), Decimal(0)) / count
    if var <= 0:
        return {k: Decimal("0") for k in values}
    std = var.sqrt()
    return {k: ((v - mean) / std).quantize(_QUANT) for k, v in values.items()}


# ----------------------------------------------------------- composite


def composite_scores(
    symbol_bars: dict[str, list[PriceBar]],
    *,
    weights: dict[str, Decimal],
    lookback_bars: int = 60,
    momentum_period: int = 20,
    bb_period: int = 20,
    bb_std: float = 2.0,
) -> list[tuple[str, Decimal]]:
    """Rank a universe by a weighted, cross-sectionally z-scored factor blend.

    Only factors with a non-zero weight are computed. Each active factor is
    z-scored across the symbols that produced a finite raw value, multiplied by
    its weight, and summed into the composite. A symbol that lacks a finite raw
    value for ANY active factor is assigned ``Decimal("-Inf")`` and sorted last
    (consistent with spec 021/023 — data-poor symbols are never chosen over
    data-rich ones).

    Args:
        symbol_bars: mapping of symbol → ascending bar list.
        weights: factor name → weight (only KNOWN_FACTORS keys are honoured).
        lookback_bars: window for the quality and low-volatility factors.
        momentum_period: lookback bars for the momentum factor.
        bb_period, bb_std: Bollinger params for the mean-reversion factor.

    Returns:
        List of (symbol, composite_score) sorted descending; ties broken by
        symbol name. Data-poor symbols appear last with ``Decimal("-Inf")``.
    """
    active = [f for f in KNOWN_FACTORS if weights.get(f, Decimal(0)) != 0]
    symbols = list(symbol_bars.keys())

    # raw[factor][symbol] — only symbols with a finite value are present.
    raw: dict[str, dict[str, Decimal]] = {f: {} for f in active}
    for sym in symbols:
        bars = symbol_bars[sym]
        for f in active:
            value = _factor_raw(
                f,
                bars,
                lookback_bars=lookback_bars,
                momentum_period=momentum_period,
                bb_period=bb_period,
                bb_std=bb_std,
            )
            if value is not None:
                raw[f][sym] = value

    z: dict[str, dict[str, Decimal]] = {f: zscore(raw[f]) for f in active}

    scored: list[tuple[str, Decimal]] = []
    for sym in symbols:
        if any(sym not in raw[f] for f in active):
            scored.append((sym, _SENTINEL))
            continue
        composite = Decimal(0)
        for f in active:
            composite += weights[f] * z[f][sym]
        scored.append((sym, composite.quantize(_QUANT)))

    # Deterministic: descending score, tie-break by symbol name.
    scored.sort(key=lambda t: (float(t[1]), t[0]), reverse=True)
    return scored


__all__ = ["KNOWN_FACTORS", "composite_scores", "zscore"]
