"""Tests for `auto_invest.worker.schedule` (T024).

Reference NYSE sessions used here:
    * Regular EDT session (summer):   13:30 - 20:00 UTC
    * Regular EST session (winter):   14:30 - 21:00 UTC
    * 2024-03-10 is the US DST start
      (Friday 2024-03-08 still EST; Monday 2024-03-11 first EDT day).
    * 2024-11-29 (Black Friday) is an early-close session;
      close = 18:00 UTC.
    * 2024-12-25 (Christmas) is a market holiday.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from auto_invest.worker.schedule import (
    is_session_open,
    is_us_holiday,
    next_session_close,
    next_session_open,
)

# ----------------------------------------------------------------- is_session_open


def test_session_open_during_regular_hours():
    # Monday 2024-06-03 (EDT), 15:00 UTC = 11:00 EDT — clearly open.
    assert is_session_open(datetime(2024, 6, 3, 15, 0, tzinfo=UTC)) is True


def test_session_closed_before_open():
    # Monday 2024-06-03, 13:00 UTC = 09:00 EDT — half hour before open.
    assert is_session_open(datetime(2024, 6, 3, 13, 0, tzinfo=UTC)) is False


def test_session_closed_after_close():
    # Monday 2024-06-03, 22:00 UTC = 18:00 EDT — two hours after close.
    assert is_session_open(datetime(2024, 6, 3, 22, 0, tzinfo=UTC)) is False


def test_session_closed_on_saturday():
    assert is_session_open(datetime(2024, 6, 8, 15, 0, tzinfo=UTC)) is False


def test_session_closed_on_christmas():
    assert is_session_open(datetime(2024, 12, 25, 16, 0, tzinfo=UTC)) is False


def test_naive_datetime_treated_as_utc():
    naive = datetime(2024, 6, 3, 15, 0)
    aware = datetime(2024, 6, 3, 15, 0, tzinfo=UTC)
    assert is_session_open(naive) == is_session_open(aware) is True


# ----------------------------------------------------------------- next_session_open


def test_next_open_when_idle_over_weekend():
    # Sunday afternoon 2024-06-09 → Monday 2024-06-10 13:30 UTC (EDT).
    moment = datetime(2024, 6, 9, 15, 0, tzinfo=UTC)
    assert next_session_open(moment) == datetime(2024, 6, 10, 13, 30, tzinfo=UTC)


def test_next_open_skips_christmas():
    # Tuesday 2024-12-24 22:00 UTC (after close) → Christmas closed →
    # next session is Thursday 2024-12-26.
    moment = datetime(2024, 12, 24, 22, 0, tzinfo=UTC)
    assert next_session_open(moment).date() == date(2024, 12, 26)


# ----------------------------------------------------------------- next_session_close


def test_next_close_during_regular_session():
    # Monday 2024-06-03 15:00 UTC → close 20:00 UTC same day.
    moment = datetime(2024, 6, 3, 15, 0, tzinfo=UTC)
    assert next_session_close(moment) == datetime(2024, 6, 3, 20, 0, tzinfo=UTC)


def test_next_close_during_half_day_session():
    # Black Friday 2024-11-29 → early close 18:00 UTC (1 PM EST).
    moment = datetime(2024, 11, 29, 15, 0, tzinfo=UTC)
    assert next_session_close(moment) == datetime(2024, 11, 29, 18, 0, tzinfo=UTC)


# ----------------------------------------------------------------- DST boundaries


def test_dst_spring_forward_friday_still_est():
    # Thursday 2024-03-07 22:00 UTC → next open is Friday 2024-03-08 14:30 UTC (EST).
    moment = datetime(2024, 3, 7, 22, 0, tzinfo=UTC)
    assert next_session_open(moment) == datetime(2024, 3, 8, 14, 30, tzinfo=UTC)


def test_dst_spring_forward_monday_now_edt():
    # Sunday 2024-03-10 22:00 UTC → next open is Monday 2024-03-11 13:30 UTC (EDT).
    moment = datetime(2024, 3, 10, 22, 0, tzinfo=UTC)
    assert next_session_open(moment) == datetime(2024, 3, 11, 13, 30, tzinfo=UTC)


# ----------------------------------------------------------------- is_us_holiday


def test_holiday_christmas():
    assert is_us_holiday(date(2024, 12, 25)) is True


def test_holiday_thanksgiving():
    assert is_us_holiday(date(2024, 11, 28)) is True


def test_not_holiday_regular_weekday():
    assert is_us_holiday(date(2024, 6, 3)) is False


def test_weekend_not_classified_as_holiday():
    # Saturday and Sunday return False so callers can distinguish
    # "skipped because Saturday" from "skipped because Christmas".
    assert is_us_holiday(date(2024, 6, 8)) is False
    assert is_us_holiday(date(2024, 6, 9)) is False
