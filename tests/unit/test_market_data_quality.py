"""Tests for `auto_invest.market_data.quality` (T034)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from auto_invest.market_data.quality import (
    QualityState,
    assess_quality,
    expected_period,
)
from auto_invest.market_data.store import PriceBar


def _bars(timeframe: str, count: int, start: datetime) -> list[PriceBar]:
    period = expected_period(timeframe)
    return [
        PriceBar(
            symbol="AAPL",
            timeframe=timeframe,
            bar_open_utc=(start + period * i).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            open_usd=Decimal("180"),
            high_usd=Decimal("180"),
            low_usd=Decimal("180"),
            close_usd=Decimal("180"),
            volume=0,
        )
        for i in range(count)
    ]


def test_expected_period_known_timeframes():
    assert expected_period("1m") == timedelta(minutes=1)
    assert expected_period("1h") == timedelta(hours=1)
    assert expected_period("1d") == timedelta(days=1)


def test_expected_period_rejects_unknown():
    with pytest.raises(ValueError, match="unsupported timeframe"):
        expected_period("3w")


def test_insufficient_data_when_below_min_bars():
    bars = _bars("1d", 2, datetime(2026, 5, 1, tzinfo=UTC))
    report = assess_quality(
        bars,
        timeframe="1d",
        now=datetime(2026, 5, 2, tzinfo=UTC),
        min_bars=20,
    )
    assert report.state is QualityState.INSUFFICIENT_DATA
    assert "have 2 bars" in report.detail


def test_armed_when_recent_and_contiguous():
    bars = _bars("1d", 5, datetime(2026, 5, 1, tzinfo=UTC))
    # last bar at 2026-05-05; check at 2026-05-05 14:00 UTC (within tolerance).
    report = assess_quality(
        bars,
        timeframe="1d",
        now=datetime(2026, 5, 5, 14, 0, tzinfo=UTC),
    )
    assert report.state is QualityState.ARMED


def test_stale_when_latest_bar_too_old():
    bars = _bars("1m", 5, datetime(2026, 5, 1, 13, 0, tzinfo=UTC))
    # Latest bar at 13:04, now at 13:30 — far past 2*period default.
    report = assess_quality(
        bars,
        timeframe="1m",
        now=datetime(2026, 5, 1, 13, 30, tzinfo=UTC),
    )
    assert report.state is QualityState.STALE
    assert "older than" in report.detail


def test_gap_detected_between_non_contiguous_bars():
    base = datetime(2026, 5, 1, tzinfo=UTC)
    period = timedelta(days=1)
    bars = [
        PriceBar(
            symbol="AAPL",
            timeframe="1d",
            bar_open_utc=ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            open_usd=Decimal("180"),
            high_usd=Decimal("180"),
            low_usd=Decimal("180"),
            close_usd=Decimal("180"),
            volume=0,
        )
        for ts in [base, base + period, base + period * 4]  # gap of 2 days
    ]
    report = assess_quality(
        bars,
        timeframe="1d",
        now=base + period * 4 + timedelta(hours=1),
    )
    assert report.state is QualityState.GAP
    assert "unexpected gap" in report.detail


def test_jitter_within_tolerance_does_not_trigger_gap():
    # 1m timeframe, bars at 0s/60s/121s/180s — 1s drift on 3rd bar (within 10% tolerance).
    base = datetime(2026, 5, 1, 13, 0, tzinfo=UTC)
    bars = [
        PriceBar(
            symbol="AAPL",
            timeframe="1m",
            bar_open_utc=(base + offset).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            open_usd=Decimal("180"),
            high_usd=Decimal("180"),
            low_usd=Decimal("180"),
            close_usd=Decimal("180"),
            volume=0,
        )
        for offset in [
            timedelta(0),
            timedelta(seconds=60),
            timedelta(seconds=121),
            timedelta(seconds=180),
        ]
    ]
    report = assess_quality(
        bars,
        timeframe="1m",
        now=base + timedelta(seconds=181),
    )
    assert report.state is QualityState.ARMED


def test_custom_max_staleness_overrides_default():
    bars = _bars("1m", 3, datetime(2026, 5, 1, 13, 0, tzinfo=UTC))
    # Latest bar at 13:02, now at 13:10 (8 minutes later).
    # Default staleness 2m would mark STALE; explicit 30m allows ARMED.
    now = datetime(2026, 5, 1, 13, 10, tzinfo=UTC)

    report_default = assess_quality(bars, timeframe="1m", now=now)
    report_custom = assess_quality(
        bars,
        timeframe="1m",
        now=now,
        max_staleness=timedelta(minutes=30),
    )
    assert report_default.state is QualityState.STALE
    assert report_custom.state is QualityState.ARMED
