"""Market calendar wrapper (FR-003, research R-6).

Thin facade over `exchange_calendars` for the NYSE/NASDAQ session
calendar (XNYS). All public functions take and return timezone-aware
UTC datetimes; naive inputs are interpreted as UTC for convenience.

The worker uses these helpers to (a) gate trigger evaluation to
regular hours, (b) schedule the end-of-session reconciliation and
report jobs, and (c) skip evaluation entirely on US market holidays.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache

import exchange_calendars as ec
import pandas as pd

CALENDAR_CODE = "XNYS"


@lru_cache(maxsize=1)
def _calendar() -> ec.ExchangeCalendar:
    return ec.get_calendar(CALENDAR_CODE)


def _to_aware_utc(dt: datetime) -> pd.Timestamp:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return pd.Timestamp(dt.astimezone(UTC))


def _to_py_utc(ts: pd.Timestamp) -> datetime:
    """Convert a pandas Timestamp (UTC-aware) to a stdlib UTC datetime."""
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.to_pydatetime().astimezone(UTC)


def is_session_open(now: datetime) -> bool:
    """Return True if the US regular session is open at `now`."""
    return bool(_calendar().is_open_at_time(_to_aware_utc(now)))


def next_session_open(now: datetime) -> datetime:
    """Return the next session open at or after `now`, in UTC.

    If `now` is already inside a session, the calendar returns the
    *next* session's open (not the current). Use `is_session_open()`
    first if you need to distinguish.
    """
    return _to_py_utc(_calendar().next_open(_to_aware_utc(now)))


def next_session_close(now: datetime) -> datetime:
    """Return the next session close after `now`, in UTC.

    If `now` is inside a session, this is the current session's close.
    On half-day sessions (e.g., the day after Thanksgiving) this
    correctly reflects the early close.
    """
    return _to_py_utc(_calendar().next_close(_to_aware_utc(now)))


def is_us_holiday(d: date) -> bool:
    """Return True if `d` is a US market holiday.

    A "holiday" here means a non-session weekday. Weekends are not
    holidays — they are weekends — and return False so callers can
    distinguish "skipped because closed" from "skipped because Saturday."
    """
    if d.weekday() >= 5:
        return False
    return not _calendar().is_session(pd.Timestamp(d))
