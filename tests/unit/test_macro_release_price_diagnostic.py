"""Source, time and observation boundaries for the macro-release diagnostic."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/macro_release_price_diagnostic.py'
SPEC = importlib.util.spec_from_file_location('macro_release_price_diagnostic', SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(family='CPI', day='2014-04-16', status='cancelled', clock='08:30:00'):
    local = datetime.fromisoformat(f'{day}T08:30:00').replace(tzinfo=ZoneInfo('America/New_York'))
    return {
        'release_family': family,
        'scheduled_date_et': day,
        'scheduled_time_et': clock,
        'scheduled_at': local.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'reference_period': '2014-03',
        'source_url': 'https://www.bls.gov/schedule/2014/home.htm',
        'calendar_id': 'US_BLS_CPI_2014-03',
        'status': status,
        'first_announced_at': '2026-10-01T00:00:00Z',
    }


def _contract():
    return {
        'allowed_release_families': ['CPI', 'EMPLOYMENT'],
        'event_clock_et': '08:30:00',
        'development_sessions': ['2013-08-23', '2017-12-29'],
    }


def test_official_date_overrides_bad_status_and_excludes_unofficial_date():
    calendar = xcals.get_calendar('XNYS')
    official = {'CPI': {'2014-04-16', '2014-04-18', '2018-01-02'}, 'EMPLOYMENT': set()}
    accepted = _row()
    unofficial = _row(day='2014-04-17')
    closed = _row(day='2014-04-18')
    future = _row(day='2018-01-02')
    other = _row(family='PPI')
    events, excluded = MODULE.select_events(
        [accepted, unofficial, closed, future, other], official, _contract(), calendar
    )
    assert events == [{'family': 'CPI', 'date_et': '2014-04-16',
                       'calendar_id': 'US_BLS_CPI_2014-03'}]
    assert excluded['not_in_official_dates'] == 1
    assert excluded['market_closed'] == 1
    assert excluded['outside_development'] == 1
    assert excluded['other_family'] == 1


def test_calendar_rejects_duplicate_and_mismatched_timezone():
    calendar = xcals.get_calendar('XNYS')
    official = {'CPI': {'2014-04-16'}, 'EMPLOYMENT': set()}
    with pytest.raises(ValueError, match='duplicate family/date'):
        MODULE.select_events([_row(), _row()], official, _contract(), calendar)
    bad = _row()
    bad['scheduled_at'] = '2014-04-16T13:30:00Z'
    with pytest.raises(ValueError, match='timezone mismatch'):
        MODULE.select_events([bad], official, _contract(), calendar)
    assert MODULE._utc_stamp('2014-03-07', 9, 45) == '2014-03-07T14:45:00Z'
    assert MODULE._utc_stamp('2014-03-10', 9, 45) == '2014-03-10T13:45:00Z'


def test_price_observation_requires_exact_previous_close_and_source_digest(tmp_path):
    calendar = xcals.get_calendar('XNYS')
    path = tmp_path / 'SPY.csv'
    header = 'timestamp_utc,symbol,open,high,low,close,volume\n'
    rows = (
        '2014-03-07T20:55:00Z,SPY,100,100,100,100,10\n'
        '2014-03-10T13:45:00Z,SPY,101,101,101,101,10\n'
        '2014-03-10T13:55:00Z,SPY,101,101,101,101,10\n'
        '2014-03-10T19:55:00Z,SPY,102,102,102,102,10\n'
    )
    path.write_text(header + rows)
    digest = MODULE.sha256_file(path)
    observed = MODULE.observe_symbol(path, 'SPY', {'2014-03-10'}, calendar, digest, 4)
    assert observed['2014-03-10']['previous']['close'] == '100'
    assert observed['2014-03-10']['entry']['open'] == '101'
    with pytest.raises(ValueError, match='price source mismatch'):
        MODULE.observe_symbol(path, 'SPY', {'2014-03-10'}, calendar, '0' * 64, 4)
    path.write_text(header + rows.replace('20:55:00Z', '20:50:00Z'))
    missing = MODULE.observe_symbol(
        path, 'SPY', {'2014-03-10'}, calendar, MODULE.sha256_file(path), 4
    )
    assert 'previous' not in missing['2014-03-10']


def test_missing_volume_and_cost_do_not_create_fictitious_gain():
    event = {'family': 'CPI', 'date_et': '2014-04-16'}
    observed = {
        'previous': {'close': '100'},
        'signal': {'close': '101', 'volume': '100'},
        'entry': {'open': '101', 'volume': '100'},
        'exit': {'open': '101.5', 'volume': '100'},
    }
    result = MODULE.score_pair(event, 'SPY', observed, {'base': 31, 'stress': 40})
    assert result['status'] == 'REFERENCE_PAIR'
    assert float(result['returns']['gross']) > 0
    assert float(result['returns']['base']) < 0
    assert float(result['returns']['stress']) < float(result['returns']['base'])
    assert MODULE.score_pair(event, 'SPY', {**observed, 'exit': None}, {'base': 31})[
        'status'
    ] == 'MISSING_OBSERVATION'
    no_volume = {**observed, 'entry': {'open': '101', 'volume': '0'}}
    assert MODULE.score_pair(event, 'SPY', no_volume, {'base': 31})[
        'status'
    ] == 'INVALID_PRICE_OR_VOLUME'
    no_signal = {**observed, 'signal': {'close': '99', 'volume': '100'}}
    assert MODULE.score_pair(event, 'SPY', no_signal, {'base': 31})['status'] == 'NO_LONG_SIGNAL'


def test_input_mutation_and_output_overwrite_fail_closed(tmp_path, monkeypatch):
    calendar_dir = tmp_path / 'calendar'
    calendar_dir.mkdir()
    (calendar_dir / 'hf-calendar-api-export.json').write_text('[]')
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        MODULE.load_inputs(calendar_dir, tmp_path)
    altered = tmp_path / 'contract.json'
    altered.write_text(MODULE.CONTRACT.read_text().replace('"base": 31', '"base": 0'))
    monkeypatch.setattr(MODULE, 'CONTRACT', altered)
    with pytest.raises(ValueError, match='preregistration SHA-256 mismatch'):
        MODULE.load_inputs(calendar_dir, tmp_path)
    output = tmp_path / 'existing.json'
    output.write_text('{}')
    with pytest.raises(FileExistsError):
        MODULE.run(calendar_dir, tmp_path, output)
