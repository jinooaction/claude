"""Tests for `auto_invest.strategy.indicators` (T037)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.indicators import (
    IndicatorError,
    ema,
    ema_cross,
    rsi,
    rsi_threshold,
    sma,
)


def _bars(closes: list[float], start: datetime | None = None) -> list[PriceBar]:
    start = start or datetime(2026, 5, 1, tzinfo=UTC)
    return [
        PriceBar(
            symbol="AAPL",
            timeframe="1d",
            bar_open_utc=(start + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            open_usd=Decimal(str(c)),
            high_usd=Decimal(str(c)),
            low_usd=Decimal(str(c)),
            close_usd=Decimal(str(c)),
            volume=0,
        )
        for i, c in enumerate(closes)
    ]


# --------------------------------------------------------- input validation


def test_insufficient_bars_raises():
    with pytest.raises(IndicatorError, match="need at least 5 bars"):
        sma(_bars([1, 2, 3]), period=5)


def test_non_monotonic_timestamps_raise():
    bars = _bars([1, 2, 3])
    bars[1] = PriceBar(
        symbol="AAPL",
        timeframe="1d",
        bar_open_utc=bars[0].bar_open_utc,  # duplicate
        open_usd=Decimal("2"),
        high_usd=Decimal("2"),
        low_usd=Decimal("2"),
        close_usd=Decimal("2"),
        volume=0,
    )
    with pytest.raises(IndicatorError, match="duplicate bar timestamp"):
        sma(bars, period=2)


def test_period_must_be_positive():
    with pytest.raises(IndicatorError):
        sma(_bars([1, 2, 3]), period=0)


# --------------------------------------------------------- SMA


def test_sma_simple():
    # SMA(5) of [1..10] last value = mean of [6,7,8,9,10] = 8
    assert sma(_bars(list(range(1, 11))), period=5) == Decimal("8")


# --------------------------------------------------------- EMA


def test_ema_constant_series_equals_value():
    # EMA of constant 100 series is 100.
    result = ema(_bars([100.0] * 20), period=10)
    assert result == Decimal("100.0")


def test_ema_ascending_is_above_first_value():
    result = ema(_bars(list(range(1, 21))), period=10)
    # Final value should be near the recent prices (15-20 range), well
    # above the early prices.
    assert result > Decimal("10")


# --------------------------------------------------------- RSI


def test_rsi_all_up_close_to_100():
    closes = [float(i) for i in range(1, 30)]  # strictly ascending
    value = rsi(_bars(closes), period=14)
    assert value > Decimal("99")  # all gains -> RSI saturates near 100


def test_rsi_all_down_close_to_zero():
    closes = [float(i) for i in range(30, 1, -1)]  # strictly descending
    value = rsi(_bars(closes), period=14)
    assert value < Decimal("1")


def test_rsi_too_few_bars_raises():
    with pytest.raises(IndicatorError):
        rsi(_bars([1, 2, 3]), period=14)


# --------------------------------------------------------- EMA cross


def test_ema_cross_fast_above_slow_on_uptrend():
    # On an ascending series, fast EMA tracks recent values closer than slow.
    bars = _bars([float(i) for i in range(1, 31)])
    assert ema_cross(bars, fast_period=5, slow_period=20, direction="fast_above_slow") is True
    assert ema_cross(bars, fast_period=5, slow_period=20, direction="fast_below_slow") is False


def test_ema_cross_fast_below_slow_on_downtrend():
    bars = _bars([float(i) for i in range(30, 0, -1)])
    assert ema_cross(bars, fast_period=5, slow_period=20, direction="fast_below_slow") is True


def test_ema_cross_fast_must_be_less_than_slow():
    bars = _bars([float(i) for i in range(1, 31)])
    with pytest.raises(IndicatorError, match="fast_period"):
        ema_cross(bars, fast_period=20, slow_period=10, direction="fast_above_slow")


def test_ema_cross_unknown_direction():
    bars = _bars([float(i) for i in range(1, 31)])
    with pytest.raises(IndicatorError, match="direction"):
        ema_cross(bars, fast_period=5, slow_period=20, direction="diagonal")


# --------------------------------------------------------- RSI threshold


def test_rsi_threshold_below():
    closes = [float(i) for i in range(30, 1, -1)]  # descending -> low RSI
    bars = _bars(closes)
    assert rsi_threshold(bars, period=14, direction="below", threshold=Decimal("30")) is True


def test_rsi_threshold_above():
    closes = [float(i) for i in range(1, 30)]  # ascending -> high RSI
    bars = _bars(closes)
    assert rsi_threshold(bars, period=14, direction="above", threshold=Decimal("70")) is True
