"""Tests for spec 018 triggers: MOMENTUM_ABOVE/BELOW, BB_ABOVE/BB_BELOW."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from auto_invest.config.rules import IndicatorTrigger
from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.triggers import TriggerContext, evaluate_indicator_trigger


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


def _ctx(bars: list[PriceBar]) -> TriggerContext:
    return TriggerContext(now=datetime(2026, 5, 10, tzinfo=UTC), bars=tuple(bars))


class TestMomentumTrigger:
    def test_momentum_above_fires_when_positive(self):
        bars = _bars([100.0, 110.0, 120.0])
        trigger = IndicatorTrigger(
            indicator="MOMENTUM_ABOVE",
            timeframe="1d",
            params={"period": 1, "threshold": "0"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is True

    def test_momentum_above_does_not_fire_on_decline(self):
        bars = _bars([120.0, 110.0, 100.0])
        trigger = IndicatorTrigger(
            indicator="MOMENTUM_ABOVE",
            timeframe="1d",
            params={"period": 1, "threshold": "0"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is False

    def test_momentum_below_fires_on_decline(self):
        bars = _bars([120.0, 110.0, 100.0])
        trigger = IndicatorTrigger(
            indicator="MOMENTUM_BELOW",
            timeframe="1d",
            params={"period": 1, "threshold": "0"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is True

    def test_momentum_above_with_threshold(self):
        # 20% rise — should exceed 10% threshold
        bars = _bars([100.0, 110.0, 120.0])
        trigger = IndicatorTrigger(
            indicator="MOMENTUM_ABOVE",
            timeframe="1d",
            params={"period": 2, "threshold": "10"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is True

    def test_momentum_insufficient_bars_returns_false(self):
        bars = _bars([100.0])
        trigger = IndicatorTrigger(
            indicator="MOMENTUM_ABOVE",
            timeframe="1d",
            params={"period": 1, "threshold": "0"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is False


class TestBBTrigger:
    def _rising_bars(self) -> list[PriceBar]:
        return _bars([float(c) for c in range(80, 106)])

    def _falling_bars(self) -> list[PriceBar]:
        return _bars([float(c) for c in range(106, 80, -1)])

    def test_bb_above_fires_near_upper_band(self):
        bars = self._rising_bars()
        trigger = IndicatorTrigger(
            indicator="BB_ABOVE",
            timeframe="1d",
            params={"period": 20, "std_dev": 2.0, "threshold": "0.8"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is True

    def test_bb_below_fires_near_lower_band(self):
        bars = self._falling_bars()
        trigger = IndicatorTrigger(
            indicator="BB_BELOW",
            timeframe="1d",
            params={"period": 20, "std_dev": 2.0, "threshold": "0.2"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is True

    def test_bb_above_does_not_fire_near_lower_band(self):
        bars = self._falling_bars()
        trigger = IndicatorTrigger(
            indicator="BB_ABOVE",
            timeframe="1d",
            params={"period": 20, "std_dev": 2.0, "threshold": "0.8"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is False

    def test_bb_flat_series_returns_false(self):
        bars = _bars([100.0] * 25)
        trigger = IndicatorTrigger(
            indicator="BB_ABOVE",
            timeframe="1d",
            params={"period": 20, "threshold": "0.5"},
            cooldown_seconds=0,
        )
        assert evaluate_indicator_trigger(trigger, _ctx(bars)) is False

    def test_bb_default_std_dev(self):
        bars = self._rising_bars()
        trigger = IndicatorTrigger(
            indicator="BB_ABOVE",
            timeframe="1d",
            params={"period": 20, "threshold": "0.5"},
            cooldown_seconds=0,
        )
        # should work without std_dev param (defaults to 2.0)
        result = evaluate_indicator_trigger(trigger, _ctx(bars))
        assert isinstance(result, bool)
