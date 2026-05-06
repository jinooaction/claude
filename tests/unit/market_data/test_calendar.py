"""T013 — MarketCalendar abstraction covers discrete + always-open venues."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from auto_invest.market_data.calendar import (
    AlwaysOpenCalendar,
    DiscreteSessionCalendar,
    get_calendar,
    register_calendar,
)


def test_get_calendar_nyse_is_discrete() -> None:
    cal = get_calendar("nyse")
    assert isinstance(cal, DiscreteSessionCalendar)
    # 2025-01-01 was a US holiday (New Year's Day)
    assert cal.is_holiday(date(2025, 1, 1))
    # 2025-01-02 was a regular session day
    assert cal.is_session(date(2025, 1, 2))
    # Saturday is not a holiday, just a weekend
    assert not cal.is_holiday(date(2025, 1, 4))


def test_get_calendar_binance_is_always_open() -> None:
    cal = get_calendar("binance")
    assert isinstance(cal, AlwaysOpenCalendar)
    # Always open, every weekday and weekend
    for d in (date(2025, 1, 1), date(2025, 1, 4), date(2025, 12, 25)):
        assert cal.is_session(d)
        assert not cal.is_holiday(d)
    # Always open at any moment
    assert cal.is_open_at(datetime(2025, 1, 1, 3, 14, tzinfo=UTC))


def test_unknown_venue_raises() -> None:
    with pytest.raises(KeyError):
        get_calendar("london-stock-exchange-typo")


def test_register_calendar_overrides() -> None:
    cal = AlwaysOpenCalendar(venue="custom-venue-001")
    register_calendar(cal)
    assert get_calendar("CUSTOM-VENUE-001") is cal


def test_always_open_next_open_is_now_utc() -> None:
    cal = AlwaysOpenCalendar(venue="binance")
    naive = datetime(2025, 6, 1, 12, 0)
    aware = cal.next_open(naive)
    assert aware.tzinfo is not None
    aware_in = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    assert cal.next_open(aware_in) == aware_in
