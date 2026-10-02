"""Time and observation boundaries for the research-only filing-price screen."""

import importlib.util
from pathlib import Path

import exchange_calendars as xcals

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/earnings_event_price_diagnostic.py'
SPEC = importlib.util.spec_from_file_location('earnings_event_price_diagnostic', SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_session_mapping_preserves_holidays_and_daylight_savings():
    calendar = xcals.get_calendar('XNYS')
    assert MODULE.entry_session('2014-04-16T12:00:00Z', calendar) == '2014-04-16'
    assert MODULE.entry_session('2014-04-16T15:00:00Z', calendar) == '2014-04-17'
    assert MODULE.entry_session('2014-04-18T12:00:00Z', calendar) == '2014-04-21'
    assert MODULE.utc_stamp('2014-03-07', 9, 45) == b'2014-03-07T14:45:00+00:00'
    assert MODULE.utc_stamp('2014-03-10', 9, 45) == b'2014-03-10T13:45:00+00:00'


def test_duplicate_and_future_session_rejected_from_development():
    calendar = xcals.get_calendar('XNYS')
    contract = {
        'development_entry_sessions': ['2014-03-03', '2017-12-29'],
        'excluded_symbols': ['DD', 'UTX'],
    }
    base = {
        'symbol': 'AXP', 'universe_known_at_acceptance': True, 'lineage_blocked': False,
        'is_amendment': False, 'publisher_knowledge_estimated': False,
        'source_claimed_acceptance_utc': '2014-04-16T12:00:00Z', 'accession': 'a',
    }
    second = dict(base, accession='b', source_claimed_acceptance_utc='2014-04-16T12:01:00Z')
    future = dict(base, accession='c', source_claimed_acceptance_utc='2018-01-02T12:00:00Z')
    rows, counts = MODULE.select_events({'events': [second, future, base]}, contract, calendar)
    assert len(rows) == 1 and rows[0]['accession'] == 'a'
    assert counts['duplicate_symbol_session'] == 1
    assert counts['outside_development_entry_sessions'] == 1


def test_signal_uses_completed_bar_and_never_fills_missing_exit():
    event = {'accession': 'a', 'symbol': 'AXP', 'entry_session': '2014-04-16'}
    observed = {
        'previous_close': '100',
        '0945': {'close': '101', 'volume': '100'},
        '0947': {'open': '101', 'volume': '100'},
        '1556': {'open': '101.3', 'volume': '100'},
    }
    result = MODULE.score_event(event, observed, {'base': 31, 'stress': 40})
    assert result['status'] == 'REFERENCE_PAIR'
    assert float(result['returns']['gross']) > 0
    assert float(result['returns']['base']) < 0
    assert float(result['returns']['stress']) < float(result['returns']['base'])
    no_signal = dict(observed, **{'0945': {'close': '99', 'volume': '100'}})
    assert MODULE.score_event(event, no_signal, {'base': 31})['status'] == 'NO_LONG_SIGNAL'
    missing_exit = dict(observed, **{'1556': None})
    assert MODULE.score_event(event, missing_exit, {'base': 31})['status'] == 'MISSING_OBSERVATION'


def test_price_digest_and_previous_session_must_match(tmp_path):
    calendar = xcals.get_calendar('XNYS')
    path = tmp_path / 'AXP.csv'
    path.write_text(
        'timestamp_utc,symbol,open,high,low,close,volume\n'
        '2014-03-07T20:59:00+00:00,AXP,100,100,100,100,10\n'
        '2014-03-10T13:45:00+00:00,AXP,101,101,101,101,10\n'
        '2014-03-10T13:47:00+00:00,AXP,101,101,101,101,10\n'
        '2014-03-10T19:56:00+00:00,AXP,102,102,102,102,10\n'
    )
    actual = MODULE.sha256_file(path)
    observed = MODULE.observe_symbol(path, 'AXP', {'2014-03-10'}, calendar, actual)
    assert observed['2014-03-10']['previous_close'] == '100'
    assert observed['2014-03-10']['0945']['close'] == '101'
    try:
        MODULE.observe_symbol(path, 'AXP', {'2014-03-10'}, calendar, '0' * 64)
    except ValueError as error:
        assert 'SHA-256 mismatch' in str(error)
    else:
        raise AssertionError('modified input accepted')


def test_only_declared_legacy_file_alias_is_accepted():
    assert MODULE.file_symbol_matches('UTX', 'RTX')
    assert MODULE.file_symbol_matches('AXP', 'AXP')
    assert not MODULE.file_symbol_matches('AXP', 'RTX')
    assert not MODULE.file_symbol_matches('UTX', 'AXP')
