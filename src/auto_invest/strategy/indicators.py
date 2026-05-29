"""Indicator facade over the `ta` library (research R-2).

Each function takes a list of `PriceBar` (ascending order, no NaNs,
strictly monotonic timestamps) and returns the latest indicator value
as a Decimal. Input validation lives here so individual triggers can
trust the data they receive.

Public surface (v1):
  * sma(bars, period)
  * ema(bars, period)
  * rsi(bars, period)
  * ema_cross(bars, fast_period, slow_period, direction)
  * rsi_threshold(bars, period, direction, threshold)

Public surface (v2 — spec 018):
  * momentum(bars, period)          — N-period % return (time-series momentum)
  * bollinger_band_pct_b(bars, period, std_dev)  — BB %B mean-reversion signal
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, SMAIndicator
from ta.volatility import BollingerBands

from auto_invest.market_data.store import PriceBar


class IndicatorError(ValueError):
    """Raised when input data cannot satisfy an indicator's requirements."""


def _validate_bars(bars: list[PriceBar], min_bars: int) -> None:
    if len(bars) < min_bars:
        raise IndicatorError(f"need at least {min_bars} bars, got {len(bars)}")
    seen_ts: set[str] = set()
    prev: str | None = None
    for bar in bars:
        if bar.bar_open_utc in seen_ts:
            raise IndicatorError(f"duplicate bar timestamp: {bar.bar_open_utc}")
        seen_ts.add(bar.bar_open_utc)
        if prev is not None and bar.bar_open_utc <= prev:
            raise IndicatorError(f"non-monotonic timestamps: {prev!r} -> {bar.bar_open_utc!r}")
        prev = bar.bar_open_utc
        for field, value in (
            ("open", bar.open_usd),
            ("high", bar.high_usd),
            ("low", bar.low_usd),
            ("close", bar.close_usd),
        ):
            if value.is_nan():
                raise IndicatorError(f"NaN in {field} at {bar.bar_open_utc}")


def _closes(bars: list[PriceBar]) -> pd.Series:
    return pd.Series([float(b.close_usd) for b in bars])


def _last_finite(series: pd.Series, name: str) -> Decimal:
    last = series.iloc[-1]
    if pd.isna(last):
        raise IndicatorError(f"{name} returned NaN at the last bar — likely insufficient warm-up")
    return Decimal(str(last))


def sma(bars: list[PriceBar], period: int) -> Decimal:
    if period < 1:
        raise IndicatorError(f"period must be >= 1, got {period}")
    _validate_bars(bars, period)
    series = SMAIndicator(close=_closes(bars), window=period).sma_indicator()
    return _last_finite(series, f"SMA({period})")


def ema(bars: list[PriceBar], period: int) -> Decimal:
    if period < 1:
        raise IndicatorError(f"period must be >= 1, got {period}")
    _validate_bars(bars, period)
    series = EMAIndicator(close=_closes(bars), window=period).ema_indicator()
    return _last_finite(series, f"EMA({period})")


def rsi(bars: list[PriceBar], period: int = 14) -> Decimal:
    if period < 2:
        raise IndicatorError(f"RSI period must be >= 2, got {period}")
    # RSI typically needs period+1 bars for the first finite value.
    _validate_bars(bars, period + 1)
    series = RSIIndicator(close=_closes(bars), window=period).rsi()
    return _last_finite(series, f"RSI({period})")


def ema_cross(
    bars: list[PriceBar],
    *,
    fast_period: int,
    slow_period: int,
    direction: str,
) -> bool:
    """Return True when fast EMA stands on the requested side of slow EMA."""
    if fast_period >= slow_period:
        raise IndicatorError(f"fast_period ({fast_period}) must be < slow_period ({slow_period})")
    if direction not in ("fast_above_slow", "fast_below_slow"):
        raise IndicatorError(f"unknown ema_cross direction: {direction!r}")
    fast = ema(bars, fast_period)
    slow = ema(bars, slow_period)
    return fast > slow if direction == "fast_above_slow" else fast < slow


def rsi_threshold(
    bars: list[PriceBar],
    *,
    period: int,
    direction: str,
    threshold: Decimal,
) -> bool:
    """Return True when RSI is on the requested side of the threshold."""
    if direction not in ("above", "below"):
        raise IndicatorError(f"unknown rsi direction: {direction!r}")
    value = rsi(bars, period)
    return value > threshold if direction == "above" else value < threshold


def momentum(bars: list[PriceBar], period: int) -> Decimal:
    """N-period percentage return: ``(close[-1] / close[-1-period] - 1) * 100``.

    Positive when price has risen over the lookback, negative when fallen.
    Needs at least ``period + 1`` bars.
    """
    if period < 1:
        raise IndicatorError(f"period must be >= 1, got {period}")
    _validate_bars(bars, period + 1)
    past = bars[-(period + 1)].close_usd
    now = bars[-1].close_usd
    if past.is_nan() or past <= 0:
        raise IndicatorError("past close is NaN or non-positive")
    return Decimal(str(float((now / past - Decimal(1)) * Decimal(100))))


def bollinger_band_pct_b(
    bars: list[PriceBar],
    period: int = 20,
    std_dev: float = 2.0,
) -> Decimal:
    """Bollinger Band %B: position of the latest close within the band.

    ``%B = (close - lower) / (upper - lower)``. 0 at lower band, 1 at upper,
    >1 above upper (overbought), <0 below lower (oversold). Raises
    ``IndicatorError`` when the band width is zero (flat price series).
    """
    if period < 2:
        raise IndicatorError(f"period must be >= 2, got {period}")
    _validate_bars(bars, period)
    closes = _closes(bars)
    bb = BollingerBands(close=closes, window=period, window_dev=std_dev)
    upper = bb.bollinger_hband().iloc[-1]
    lower = bb.bollinger_lband().iloc[-1]
    close = float(bars[-1].close_usd)
    if pd.isna(upper) or pd.isna(lower):
        raise IndicatorError(
            f"BollingerBands returned NaN — likely insufficient warm-up (need {period} bars)"
        )
    width = upper - lower
    if width == 0.0:
        raise IndicatorError("Bollinger Band width is zero — flat price series")
    return Decimal(str((close - lower) / width))
