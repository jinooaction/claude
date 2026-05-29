"""Trigger evaluators for the three v1 trigger families (FR-001).

Each evaluator takes a `Trigger` model from `config/rules.py`, plus a
`TriggerContext` carrying the current moment, last quote, recent
bars, and the last fire time, and returns True iff the trigger should
fire NOW. The order router separately enforces sizing and whitelist
gates after a trigger fires.

A trigger that is "in cooldown" never fires regardless of base
condition; this is the worker's primary mechanism for preventing
re-fire storms when a price hovers around a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal

from auto_invest.config.rules import (
    IndicatorTrigger,
    PriceTrigger,
    TimeTrigger,
)
from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.indicators import (
    IndicatorError,
    bollinger_band_pct_b,
    ema_cross,
    momentum,
    rsi_threshold,
)


@dataclass(frozen=True)
class TriggerContext:
    now: datetime
    current_price_usd: Decimal | None = None
    bars: tuple[PriceBar, ...] = field(default_factory=tuple)
    last_fired_at_utc: datetime | None = None


def _in_cooldown(now: datetime, last_fired: datetime | None, cooldown_seconds: int) -> bool:
    if last_fired is None or cooldown_seconds <= 0:
        return False
    return (now - last_fired) < timedelta(seconds=cooldown_seconds)


def _parse_at_time(at_time: str) -> time:
    hour, minute = at_time.split(":")
    return time(int(hour), int(minute))


def evaluate_time_trigger(trigger: TimeTrigger, ctx: TriggerContext) -> bool:
    if _in_cooldown(ctx.now, ctx.last_fired_at_utc, trigger.cooldown_seconds):
        return False
    target = _parse_at_time(trigger.at_time)
    if (ctx.now.hour, ctx.now.minute) != (target.hour, target.minute):
        return False
    return not (trigger.weekdays is not None and ctx.now.weekday() not in trigger.weekdays)


def evaluate_price_trigger(trigger: PriceTrigger, ctx: TriggerContext) -> bool:
    if _in_cooldown(ctx.now, ctx.last_fired_at_utc, trigger.cooldown_seconds):
        return False
    if ctx.current_price_usd is None:
        return False
    if trigger.direction == "<=":
        return ctx.current_price_usd <= trigger.threshold
    return ctx.current_price_usd >= trigger.threshold


def evaluate_indicator_trigger(trigger: IndicatorTrigger, ctx: TriggerContext) -> bool:
    if _in_cooldown(ctx.now, ctx.last_fired_at_utc, trigger.cooldown_seconds):
        return False
    bars = list(ctx.bars)
    try:
        if trigger.indicator == "EMA_CROSS":
            return ema_cross(
                bars,
                fast_period=int(trigger.params["fast_period"]),
                slow_period=int(trigger.params["slow_period"]),
                direction=str(trigger.params["direction"]),
            )
        if trigger.indicator in ("RSI_BELOW", "RSI_ABOVE"):
            direction = "below" if trigger.indicator == "RSI_BELOW" else "above"
            return rsi_threshold(
                bars,
                period=int(trigger.params["period"]),
                direction=direction,
                threshold=Decimal(str(trigger.params["threshold"])),
            )
        if trigger.indicator in ("MOMENTUM_ABOVE", "MOMENTUM_BELOW"):
            value = momentum(bars, period=int(trigger.params["period"]))
            threshold = Decimal(str(trigger.params["threshold"]))
            return value > threshold if trigger.indicator == "MOMENTUM_ABOVE" else value < threshold
        if trigger.indicator in ("BB_ABOVE", "BB_BELOW"):
            pct_b = bollinger_band_pct_b(
                bars,
                period=int(trigger.params.get("period", 20)),
                std_dev=float(trigger.params.get("std_dev", 2.0)),
            )
            threshold = Decimal(str(trigger.params["threshold"]))
            return pct_b > threshold if trigger.indicator == "BB_ABOVE" else pct_b < threshold
        raise IndicatorError(f"unsupported indicator: {trigger.indicator!r}")
    except IndicatorError:
        # Insufficient bars / NaN / other quality issue: not armed yet.
        # The caller should consult market_data.quality independently
        # for human-readable diagnostics.
        return False


def evaluate(trigger, ctx: TriggerContext) -> bool:
    """Dispatch by trigger type."""
    if isinstance(trigger, TimeTrigger):
        return evaluate_time_trigger(trigger, ctx)
    if isinstance(trigger, PriceTrigger):
        return evaluate_price_trigger(trigger, ctx)
    if isinstance(trigger, IndicatorTrigger):
        return evaluate_indicator_trigger(trigger, ctx)
    raise TypeError(f"unknown trigger type: {type(trigger).__name__}")
