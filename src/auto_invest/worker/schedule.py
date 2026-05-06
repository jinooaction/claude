"""NYSE/NASDAQ session-calendar facade for spec 001 (FR-003, R-6).

Spec 002 introduced `market_data/calendar.py` with a `MarketCalendar`
abstraction so non-equity asset classes (crypto, FX) can plug in.
This module preserves the spec 001 public API (`is_session_open`,
`next_session_open`, `next_session_close`, `is_us_holiday`) by
delegating to the NYSE calendar in the new abstraction; existing
import sites in spec 001 are unchanged.
"""

from __future__ import annotations

from datetime import date, datetime

from auto_invest.market_data.calendar import get_calendar

CALENDAR_CODE = "XNYS"


def _nyse():
    return get_calendar("nyse")


def is_session_open(now: datetime) -> bool:
    return _nyse().is_open_at(now)


def next_session_open(now: datetime) -> datetime:
    return _nyse().next_open(now)


def next_session_close(now: datetime) -> datetime:
    return _nyse().next_close(now)


def is_us_holiday(d: date) -> bool:
    return _nyse().is_holiday(d)
