"""Tests for spec 018 indicators: momentum and bollinger_band_pct_b."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.indicators import (
    IndicatorError,
    bollinger_band_pct_b,
    momentum,
)


def _bars(closes: list[float], start: datetime | None = None) -> list[PriceBar]:
    start = start or datetime(2026, 5, 1, tzinfo=UTC)
    return [
        PriceBar(
            symbol="TEST",
            timeframe="1d",
            bar_open_utc=(start + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            open_usd=Decimal(str(c)),
            high_usd=Decimal(str(c)),
            low_usd=Decimal(str(c)),
            close_usd=Decimal(str(c)),
            volume=Decimal("1000"),
        )
        for i, c in enumerate(closes)
    ]


class TestMomentum:
    def test_positive_momentum(self):
        bars = _bars([100.0, 110.0, 120.0])
        # period=1: (120/110 - 1)*100 ≈ 9.09%
        val = momentum(bars, period=1)
        assert val > Decimal("9")
        assert val < Decimal("10")

    def test_negative_momentum(self):
        bars = _bars([120.0, 110.0, 100.0])
        val = momentum(bars, period=1)
        assert val < Decimal("0")

    def test_flat_momentum_zero(self):
        bars = _bars([100.0, 100.0])
        val = momentum(bars, period=1)
        assert val == Decimal("0")

    def test_period_2_lookback(self):
        bars = _bars([100.0, 110.0, 120.0])
        # period=2: (120/100 - 1)*100 = 20%
        val = momentum(bars, period=2)
        assert abs(val - Decimal("20")) < Decimal("0.001")

    def test_insufficient_bars_raises(self):
        with pytest.raises(IndicatorError):
            momentum(_bars([100.0]), period=1)

    def test_period_zero_raises(self):
        with pytest.raises(IndicatorError):
            momentum(_bars([100.0, 110.0]), period=0)


class TestBollingerBandPctB:
    def _flat_bars(self, n: int = 25, price: float = 100.0) -> list[PriceBar]:
        return _bars([price] * n)

    def test_close_at_upper_band(self):
        # Rising prices: last close should be near or above upper band → %B ≈ 1 or >1
        closes = list(range(80, 106))  # 26 bars, rising
        bars = _bars([float(c) for c in closes])
        val = bollinger_band_pct_b(bars, period=20)
        assert val > Decimal("0.8")

    def test_close_at_lower_band(self):
        # Falling prices: %B near or below 0
        closes = list(range(106, 80, -1))  # falling
        bars = _bars([float(c) for c in closes])
        val = bollinger_band_pct_b(bars, period=20)
        assert val < Decimal("0.2")

    def test_close_at_middle_is_near_half(self):
        # Symmetric prices around 100 → last bar near midpoint
        import math
        closes = [100 + 5 * math.sin(i * 0.4) for i in range(30)]
        bars = _bars(closes)
        val = bollinger_band_pct_b(bars, period=20)
        # Should be somewhere between 0 and 1 (not extreme)
        assert Decimal("0") <= val <= Decimal("1.5")

    def test_flat_series_raises(self):
        bars = _bars([100.0] * 25)
        with pytest.raises(IndicatorError, match="zero"):
            bollinger_band_pct_b(bars, period=20)

    def test_insufficient_bars_raises(self):
        with pytest.raises(IndicatorError):
            bollinger_band_pct_b(_bars([100.0] * 10), period=20)

    def test_period_too_small_raises(self):
        with pytest.raises(IndicatorError):
            bollinger_band_pct_b(_bars([100.0] * 5), period=1)
