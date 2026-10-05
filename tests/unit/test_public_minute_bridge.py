from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from auto_invest.market_data.intraday import SYMBOLS
from auto_invest.market_data.public_minute import PilotError
from auto_invest.market_data.public_minute_bridge import aggregate, bridge_rows

START = datetime(2014, 1, 2, 14, 30, tzinfo=UTC)


def minute(offset=0, symbol='SPY', start=START, **changes):
    result = dict(timestamp=start + timedelta(minutes=offset), ticker=symbol,
                  open=10. + offset, high=20. + offset, low=9., close=11. + offset,
                  volume=100.)
    result.update(changes)
    return result


def test_aggregate_uses_time_order_and_end_plus_lag():
    rows = [minute(i) for i in reversed(range(5))]
    bar, ready = aggregate(rows, START)
    assert ready == START + timedelta(minutes=6)
    assert bar['open'] == 10. and bar['close'] == 15.
    assert bar['high'] == 24. and bar['low'] == 9. and bar['volume'] == 500


@pytest.mark.parametrize('minutes', [0, 1, 4, 5])
def test_complete_bar_is_not_observable_before_modeled_availability(minutes):
    with pytest.raises(PilotError, match='NOT_YET_AVAILABLE'):
        aggregate([minute(i) for i in range(5)], START,
                  observed=START + timedelta(minutes=minutes))


@pytest.mark.parametrize('offsets', [[0, 1, 3, 4], [0, 1, 2, 2, 4], [0, 1, 2, 3, 5]])
def test_missing_duplicate_or_cross_bin_is_rejected(offsets):
    with pytest.raises(PilotError, match='BIN_INCOMPLETE'):
        aggregate([minute(i) for i in offsets], START)


def test_missing_minutes_are_not_imputed_and_absent_sessions_are_reported():
    report = bridge_rows([minute(i) for i in (0, 1, 3, 4)], '2014-01')
    day = report['sessions'][0]
    assert len(report['sessions']) == 21 and len(day['symbols']) == 5
    assert day['symbols']['SPY']['observed_minutes'] == 4
    assert day['symbols']['SPY']['usable_bins'] == 0
    assert day['symbols']['SPY']['missing_bins'] == 78
    assert report['common_complete_sessions'] == []
    assert report['missing_minutes_by_symbol']['SPY'] == 8186


def test_common_complete_sessions_use_actual_date_intersection():
    rows = [minute(i, symbol=s) for s in SYMBOLS for i in range(390)]
    report = bridge_rows(rows, '2014-01')
    assert report['common_complete_sessions'] == ['2014-01-02']
    rows = [r for r in rows if not (r['ticker'] == 'GLD' and r['timestamp'] == START)]
    report = bridge_rows(rows, '2014-01')
    assert report['complete_sessions_by_symbol']['SPY'] == ['2014-01-02']
    assert report['complete_sessions_by_symbol']['GLD'] == []
    assert report['common_complete_sessions'] == []


def test_zero_volume_is_structurally_valid_but_not_runtime_usable():
    report = bridge_rows([minute(i, volume=0.) for i in range(5)], '2014-01')
    state = report['sessions'][0]['symbols']['SPY']
    assert state['complete_bins'] == 1 and state['zero_volume_bins'] == 1
    assert state['missing_bins'] == 77 and state['usable_bins'] == 0


@pytest.mark.parametrize('change', [
    {'timestamp': START.replace(tzinfo=None)}, {'timestamp': START + timedelta(seconds=1)},
    {'timestamp': datetime(2021, 1, 1, tzinfo=UTC)}, {'ticker': 'AAPL'},
    {'open': float('nan')}, {'close': 100.}, {'volume': -1.},
    {'volume': 1.5}, {'volume': True}, {'volume': float(2**53)},
])
def test_invalid_rows_never_grant_parity(change):
    with pytest.raises(PilotError):
        bridge_rows([minute(**change)], '2014-01')


def test_duplicate_selected_minutes_fail_closed():
    with pytest.raises(PilotError, match='DUPLICATE_MINUTE'):
        bridge_rows([minute(), minute()], '2014-01')


def test_extended_and_holiday_rows_never_fill_regular_gaps():
    rows = [minute(start=datetime(2014, 1, 1, 14, 30, tzinfo=UTC)),
            minute(start=datetime(2014, 2, 1, 0, 59, tzinfo=UTC))]
    report = bridge_rows(rows, '2014-01')
    assert report['excluded_rows'] == 2
    assert report['regular_minutes_by_symbol']['SPY'] == 0


def test_early_close_requires_only_actual_session_bins():
    start = datetime(2019, 12, 24, 14, 30, tzinfo=UTC)
    report = bridge_rows([minute(i, start=start) for i in range(210)], '2019-12')
    state = next(s for s in report['sessions'] if s['day'] == '2019-12-24')['symbols']['SPY']
    assert state['expected_minutes'] == 210 and state['expected_bins'] == 42
    assert state['complete_session'] is True


def test_report_is_price_free_model_and_never_strategy_evidence():
    import json
    report = bridge_rows([minute(i) for i in range(5)], '2014-01')
    assert report['timestamp_semantics_verified'] is False
    assert report['publish_delay_measured'] is False
    assert report['runtime_normalization_checked'] is True
    assert report['provider_eligible'] is False and report['strategy_eligible'] is False
    assert report['orders_submitted'] == 0 and report['returns_examined'] is False
    assert '"open"' not in json.dumps(report) and '"close"' not in json.dumps(report)


def test_holdout_month_is_rejected_even_without_rows():
    with pytest.raises(PilotError, match='DEVELOPMENT_MONTH_REQUIRED'):
        bridge_rows([], '2021-01')
