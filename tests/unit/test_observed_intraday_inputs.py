from datetime import UTC, date, datetime, timedelta

import pytest

from auto_invest.analytics.observed_intraday_inputs import Minute, ObservedSeries, Source


def ts(value):
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


SOURCE = Source('TEST', '0' * 64, 'synthetic', 'none', 'unverified')
START = ts('2024-03-08T14:30:00')


def minutes(start, count):
    return [Minute(start + timedelta(minutes=i), 100, 102, 99, 101, 10)
            for i in range(count)]


def series(rows=(), start=date(2024, 3, 8), end=date(2024, 3, 11)):
    return ObservedSeries(SOURCE, start, end, rows)


def test_missing_day_and_dst_are_preserved():
    data = series(minutes(START, 5))
    assert len(data.sessions) == 2
    assert data.bounds(date(2024, 3, 11))[0] == ts('2024-03-11T13:30:00')
    empty = data.window(date(2024, 3, 11), 0, 5, ts('2024-03-11T14:00:00'))
    assert len(empty.missing) == 5 and empty.ohlcv is None


def test_incomplete_window_does_not_create_prices():
    data = series(minutes(START, 4))
    window = data.window(date(2024, 3, 8), 0, 5, START + timedelta(minutes=5))
    assert window.missing == (START + timedelta(minutes=4),)
    assert not window.complete and window.ohlcv is None


def test_future_rows_do_not_change_past_window():
    full = series(minutes(START, 390))
    prefix = series(minutes(START, 30))
    at = START + timedelta(minutes=30)
    assert full.window(date(2024, 3, 8), 0, 30, at) == prefix.window(date(2024, 3, 8), 0, 30, at)
    assert full.window(date(2024, 3, 8), 0, 30, at - timedelta(seconds=1)).ohlcv is None
    pending = full.window(date(2024, 3, 8), 0, 30, START)
    assert pending.observed_count == 0 and len(pending.pending) == 30


def test_early_close_does_not_invent_final_window():
    day = date(2024, 11, 29)
    data = series(start=day, end=day)
    lo, hi = data.bounds(day)
    assert (hi-lo).total_seconds() == 210*60
    with pytest.raises(ValueError):
        data.window(day, 210, 5, hi)


def test_prior_days_do_not_skip_missing_or_use_future():
    data = series(start=date(2024, 3, 1), end=date(2024, 3, 25))
    windows = data.prior_windows(date(2024, 3, 25), 14, 30, ts('2024-03-25T14:00:00'))
    assert len(windows) == 14
    assert windows[-1].start.date() == date(2024, 3, 22)
    assert all(not w.complete for w in windows)
    with pytest.raises(ValueError):
        data.prior_windows(date(2024, 3, 8), 14, 30, START)


def test_open_is_only_a_completed_minute_proxy():
    data = series(minutes(START, 1))
    pending = data.exact_price(START, START)
    assert pending.status == 'NOT_YET_OBSERVABLE' and pending.reference_open is None
    result = data.exact_price(START, START + timedelta(minutes=1))
    assert result.status == 'EXACT' and result.reference_open == 100
    assert not result.fill_verified and result.capacity_unknown


def test_later_observation_is_not_backdated_and_missing_stays_missing():
    next_day = ts('2024-03-11T13:30:00')
    data = series(minutes(next_day, 1))
    assert data.exact_price(START, next_day).status == 'MISSING'
    assert data.next_price(START, next_day).status == 'MISSING'
    result = data.next_price(START, next_day + timedelta(minutes=1))
    assert result.status == 'LATER' and result.observed_at == next_day
    assert result.requested_at == START and not result.fill_verified
    assert series().next_price(START, next_day).status == 'MISSING'


def test_zero_volume_not_price_evidence():
    data = series([Minute(START, 100, 100, 100, 100, 0)])
    assert data.exact_price(START, START + timedelta(minutes=1)).status == 'ZERO_VOLUME'


@pytest.mark.parametrize('rows', [
    minutes(START, 1)*2,
    list(reversed(minutes(START, 2))),
    minutes(START + timedelta(seconds=1), 1),
    minutes(ts('2024-03-09T14:30:00'), 1),
    [Minute(START, float('nan'), 102, 99, 101, 10)],
    [Minute(START, 100, 98, 99, 101, 10)],
    [Minute(START, 100, 102, 99, 101, -1)],
])
def test_invalid_input_rejected(rows):
    with pytest.raises(ValueError):
        series(rows)


def test_naive_asof_rejected():
    with pytest.raises(ValueError):
        series().window(date(2024, 3, 8), 0, 5, datetime(2024, 3, 8, 15))
