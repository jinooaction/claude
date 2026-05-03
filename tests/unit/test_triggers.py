"""Tests for `auto_invest.strategy.triggers` (T039)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from auto_invest.config.rules import (
    IndicatorTrigger,
    PriceTrigger,
    TimeTrigger,
)
from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.triggers import (
    TriggerContext,
    evaluate,
    evaluate_indicator_trigger,
    evaluate_price_trigger,
    evaluate_time_trigger,
)


def _bars(closes: list[float]) -> tuple[PriceBar, ...]:
    start = datetime(2026, 5, 1, tzinfo=UTC)
    return tuple(
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
    )


# ----------------------------------------------------------------- time trigger


def test_time_trigger_fires_at_exact_minute():
    trigger = TimeTrigger(at_time="13:30", cooldown_seconds=60)
    ctx = TriggerContext(now=datetime(2026, 5, 4, 13, 30, 0, tzinfo=UTC))
    assert evaluate_time_trigger(trigger, ctx) is True


def test_time_trigger_does_not_fire_one_minute_off():
    trigger = TimeTrigger(at_time="13:30", cooldown_seconds=60)
    ctx = TriggerContext(now=datetime(2026, 5, 4, 13, 31, 0, tzinfo=UTC))
    assert evaluate_time_trigger(trigger, ctx) is False


def test_time_trigger_respects_weekdays():
    # Only Monday (0). 2026-05-04 is a Monday; 2026-05-05 is a Tuesday.
    trigger = TimeTrigger(at_time="13:30", weekdays=(0,), cooldown_seconds=60)
    monday = TriggerContext(now=datetime(2026, 5, 4, 13, 30, tzinfo=UTC))
    tuesday = TriggerContext(now=datetime(2026, 5, 5, 13, 30, tzinfo=UTC))
    assert evaluate_time_trigger(trigger, monday) is True
    assert evaluate_time_trigger(trigger, tuesday) is False


def test_time_trigger_cooldown_suppresses_refire():
    trigger = TimeTrigger(at_time="13:30", cooldown_seconds=86400)
    base = datetime(2026, 5, 4, 13, 30, tzinfo=UTC)
    ctx = TriggerContext(
        now=base + timedelta(seconds=1),
        last_fired_at_utc=base,
    )
    # Time-of-day still matches, but we are in cooldown.
    assert evaluate_time_trigger(trigger, ctx) is False


# ----------------------------------------------------------------- price trigger


def test_price_trigger_below_fires_when_price_under_threshold():
    trigger = PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=0)
    ctx = TriggerContext(
        now=datetime(2026, 5, 4, tzinfo=UTC),
        current_price_usd=Decimal("99.99"),
    )
    assert evaluate_price_trigger(trigger, ctx) is True


def test_price_trigger_below_inclusive_at_threshold():
    trigger = PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=0)
    ctx = TriggerContext(
        now=datetime(2026, 5, 4, tzinfo=UTC),
        current_price_usd=Decimal("100"),
    )
    assert evaluate_price_trigger(trigger, ctx) is True


def test_price_trigger_below_does_not_fire_above():
    trigger = PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=0)
    ctx = TriggerContext(
        now=datetime(2026, 5, 4, tzinfo=UTC),
        current_price_usd=Decimal("100.01"),
    )
    assert evaluate_price_trigger(trigger, ctx) is False


def test_price_trigger_above_direction():
    trigger = PriceTrigger(direction=">=", threshold=Decimal("100"), cooldown_seconds=0)
    ctx_above = TriggerContext(
        now=datetime(2026, 5, 4, tzinfo=UTC),
        current_price_usd=Decimal("101"),
    )
    ctx_below = TriggerContext(
        now=datetime(2026, 5, 4, tzinfo=UTC),
        current_price_usd=Decimal("99"),
    )
    assert evaluate_price_trigger(trigger, ctx_above) is True
    assert evaluate_price_trigger(trigger, ctx_below) is False


def test_price_trigger_no_quote_does_not_fire():
    trigger = PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=0)
    ctx = TriggerContext(now=datetime(2026, 5, 4, tzinfo=UTC), current_price_usd=None)
    assert evaluate_price_trigger(trigger, ctx) is False


def test_price_trigger_cooldown_suppresses_refire():
    trigger = PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=600)
    base = datetime(2026, 5, 4, 13, 30, tzinfo=UTC)
    ctx = TriggerContext(
        now=base + timedelta(seconds=10),
        current_price_usd=Decimal("90"),
        last_fired_at_utc=base,
    )
    assert evaluate_price_trigger(trigger, ctx) is False


# ----------------------------------------------------------------- indicator trigger


def test_indicator_trigger_warmup_returns_false_quietly():
    trigger = IndicatorTrigger(
        indicator="EMA_CROSS",
        timeframe="1d",
        cooldown_seconds=0,
        params={"fast_period": 5, "slow_period": 20, "direction": "fast_above_slow"},
    )
    # Far fewer than slow_period bars: insufficient warm-up.
    ctx = TriggerContext(
        now=datetime(2026, 6, 1, tzinfo=UTC),
        bars=_bars([1.0, 2.0, 3.0]),
    )
    assert evaluate_indicator_trigger(trigger, ctx) is False


def test_indicator_trigger_ema_cross_fires_on_uptrend():
    trigger = IndicatorTrigger(
        indicator="EMA_CROSS",
        timeframe="1d",
        cooldown_seconds=0,
        params={"fast_period": 5, "slow_period": 20, "direction": "fast_above_slow"},
    )
    ctx = TriggerContext(
        now=datetime(2026, 6, 1, tzinfo=UTC),
        bars=_bars([float(i) for i in range(1, 31)]),
    )
    assert evaluate_indicator_trigger(trigger, ctx) is True


def test_indicator_trigger_rsi_below():
    trigger = IndicatorTrigger(
        indicator="RSI_BELOW",
        timeframe="1d",
        cooldown_seconds=0,
        params={"period": 14, "threshold": 30},
    )
    descending = [float(i) for i in range(30, 1, -1)]
    ctx = TriggerContext(
        now=datetime(2026, 6, 1, tzinfo=UTC),
        bars=_bars(descending),
    )
    assert evaluate_indicator_trigger(trigger, ctx) is True


def test_indicator_trigger_unknown_indicator_returns_false():
    trigger = IndicatorTrigger(
        indicator="UNICORN",
        timeframe="1d",
        cooldown_seconds=0,
        params={},
    )
    ctx = TriggerContext(
        now=datetime(2026, 6, 1, tzinfo=UTC),
        bars=_bars([float(i) for i in range(1, 31)]),
    )
    assert evaluate_indicator_trigger(trigger, ctx) is False


# ----------------------------------------------------------------- dispatch


def test_dispatch_routes_by_type():
    time_trigger = TimeTrigger(at_time="13:30", cooldown_seconds=0)
    price_trigger = PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=0)
    moment = datetime(2026, 5, 4, 13, 30, tzinfo=UTC)

    assert evaluate(time_trigger, TriggerContext(now=moment)) is True
    assert (
        evaluate(
            price_trigger,
            TriggerContext(now=moment, current_price_usd=Decimal("90")),
        )
        is True
    )
