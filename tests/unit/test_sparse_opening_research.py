import hashlib
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from auto_invest.analytics.observed_intraday_inputs import (
    Minute,
    ObservedSeries,
    Source,
)
from auto_invest.analytics.sparse_opening_research import (
    OpeningSignals,
    ResearchAccount,
    replay_research,
    research_inputs,
    sealed_contract,
)

SOURCE = Source('TEST', '0'*64, 'synthetic', 'none', 'unverified')
CONTRACTS = Path(__file__).resolve().parents[2]/'specs/194-sparse-opening-research/contracts'


def manifest_fixture(tmp_path):
    contract, inventory = sealed_contract(CONTRACTS)
    raw = b'timestamp_utc,symbol,open,high,low,close,volume\n'
    (tmp_path/'empty.csv').write_bytes(raw)
    manifest = {'schema_version': 2, 'symbols': contract['members'], 'start': '2014-03-01',
                'end': '2020-03-06', 'calendar': 'XNYS', 'files': {}}
    for member, source in inventory.items():
        manifest['files'][member] = {
            'path': 'empty.csv', 'sha256': hashlib.sha256(raw).hexdigest(),
            'original_sha256': source['sha256'], 'file_symbol': source['file_symbol'],
            'provider': 'hfdatalibrary-pitrading', 'adjustment': 'source-split-dividend-adjusted',
            'issuer_lineage_status': 'unverified'}
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest))
    return path, manifest


def test_contract_change_is_rejected(tmp_path):
    for name in ('preregistration.json', 'source-inventory.json'):
        shutil.copyfile(CONTRACTS/name, tmp_path/name)
    path = tmp_path/'preregistration.json'
    path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError, match='contract changed'):
        sealed_contract(tmp_path)


def test_snapshots_keep_empty_symbols_and_ignore_later_file_mutation(tmp_path):
    path, _ = manifest_fixture(tmp_path)
    with research_inputs(path, CONTRACTS) as data:
        (tmp_path/'empty.csv').write_text('changed after snapshot')
        day, symbols = next(data['days'])
        assert day == date(2014, 3, 3) and len(symbols) == 30
        for value in symbols.values():
            lo, _ = value.bounds(day)
            assert not value.window(day, 0, 5, lo+timedelta(minutes=5)).complete


@pytest.mark.parametrize('field,value', [('original_sha256', '0'*64),
                                       ('issuer_lineage_status', 'verified'),
                                       ('file_symbol', 'WRONG')])
def test_source_claim_changes_are_rejected(tmp_path, field, value):
    path, manifest = manifest_fixture(tmp_path)
    manifest['files']['DD'][field] = value
    path.write_text(json.dumps(manifest))
    with (pytest.raises(ValueError, match='source descriptor'),
          research_inputs(path, CONTRACTS)):
        pass


def test_csv_hash_change_is_rejected(tmp_path):
    path, _ = manifest_fixture(tmp_path)
    (tmp_path/'empty.csv').write_text('changed')
    with pytest.raises(ValueError, match='fingerprint'), research_inputs(path, CONTRACTS):
        pass


def fixture(missing_prior=False, afternoon=False, volume=20):
    start, end = date(2014, 3, 3), date(2014, 3, 24)
    empty = ObservedSeries(SOURCE, start, end, [])
    days = empty.sessions[:15]
    rows = []
    for i, day in enumerate(days):
        lo, _ = empty.bounds(day)
        for m in range(5):
            if missing_prior and i == 10 and m == 2:
                continue
            rows.append(Minute(lo+timedelta(minutes=m), 10, 11, 9, 10.5,
                               10 if i < 14 else volume))
        if i == 14:
            rows.extend(Minute(lo+timedelta(minutes=m), 11, 13, 10, 12, 10)
                        for m in range(5, 65))
            if afternoon:
                rows.append(Minute(lo+timedelta(minutes=300), 1, 1000, 1, 999, 9999))
    return ObservedSeries(SOURCE, start, end, rows), days


def prepare(data, days):
    signals = OpeningSignals(days)
    for day in days[:-1]:
        lo, _ = data.bounds(day)
        assert signals.entry(data, day, lo+timedelta(minutes=5)) is None
    return signals


def test_first_trigger_and_daily_attempt_are_fixed():
    data, days = fixture()
    signal = prepare(data, days)
    day = days[-1]
    lo, _ = data.bounds(day)
    assert signal.entry(data, day, lo+timedelta(minutes=5)) is None
    value = signal.entry(data, day, lo+timedelta(minutes=10))
    assert value['signal_close'] == 12 and value['opening_low'] == 9
    assert value['relative_volume'] == 2
    assert signal.entry(data, day, lo+timedelta(minutes=15)) is None


def test_missing_prior_window_is_not_skipped():
    data, days = fixture(missing_prior=True)
    signals = prepare(data, days)
    lo, _ = data.bounds(days[-1])
    assert signals.entry(data, days[-1], lo+timedelta(minutes=10)) is None


def test_future_afternoon_does_not_change_entry():
    results = []
    for future in (False, True):
        data, days = fixture(afternoon=future)
        signal = prepare(data, days)
        lo, _ = data.bounds(days[-1])
        results.append(signal.entry(data, days[-1], lo+timedelta(minutes=10)))
    assert results[0] == results[1]


def test_signal_cutoff_inclusive_and_next_window_rejected():
    for offset, expected in [(60, True), (65, False)]:
        data, days = fixture()
        signal = prepare(data, days)
        lo, _ = data.bounds(days[-1])
        assert (signal.entry(data, days[-1], lo+timedelta(minutes=offset)) is not None) == expected


def test_low_relative_volume_has_no_entry():
    data, days = fixture(volume=19)
    signal = prepare(data, days)
    lo, _ = data.bounds(days[-1])
    assert signal.entry(data, days[-1], lo+timedelta(minutes=10)) is None


def test_exchange_close_exit_does_not_need_last_observation():
    day = date(2014, 11, 28)
    data = ObservedSeries(SOURCE, day, day, [])
    _, close = data.bounds(day)
    assert OpeningSignals.exit_due(data, day, close-timedelta(minutes=5), 9)
    assert not OpeningSignals.exit_due(data, day, close-timedelta(minutes=10), 9)


def account_fixture():
    data, days = fixture()
    lo, _ = data.bounds(days[0])
    return ResearchAccount(31), data, days, lo


def test_reservations_compete_for_shared_cash_and_slots():
    account, _, _, lo = account_fixture()
    for symbol in ('A', 'B', 'C', 'D'):
        assert account.reserve(symbol, lo, 10, 9)
    assert not account.reserve('E', lo, 10, 9)
    assert not account.reserve('A', lo, 10, 9)
    assert account.cash + account.reserved == pytest.approx(10000)
    assert account.reserved <= 8000


def test_partial_entry_releases_unused_cash_and_charges_cost_once():
    account, data, days, lo = account_fixture()
    assert account.reserve('TEST', lo, 10, 9)
    # Only 1 share is observable; remaining reservation must be cancelled.
    data = ObservedSeries(SOURCE, days[0], days[0], [Minute(lo, 10, 11, 9, 10, 100)])
    account.observe_entry('TEST', data, lo+timedelta(minutes=1))
    assert account.positions['TEST']['quantity'] == 1
    assert account.positions['TEST']['basis'] == pytest.approx(10.031)
    assert account.cash == pytest.approx(9989.969)
    assert account.reserved == 0
    assert account.summary()['net_profit'] is None


@pytest.mark.parametrize('open_price,volume', [(11, 10000), (10, 99), (10, 0)])
def test_unfilled_entry_is_cancelled(open_price, volume):
    account, _, days, lo = account_fixture()
    account.reserve('TEST', lo, 10, 9)
    data = ObservedSeries(SOURCE, days[0], days[0],
                          [Minute(lo, open_price, 12, 9, 10, volume)])
    account.observe_entry('TEST', data, lo+timedelta(minutes=1))
    assert not account.positions and not account.entries
    assert account.cash == pytest.approx(10000)


def test_pending_minute_cannot_release_reservation():
    account, data, _, lo = account_fixture()
    account.reserve('TEST', lo, 10, 9)
    before = account.cash
    with pytest.raises(ValueError, match='not yet observable'):
        account.observe_entry('TEST', data, lo)
    assert account.cash == before and 'TEST' in account.entries


def test_missing_entry_does_not_seek_later_price():
    account, _, days, lo = account_fixture()
    account.reserve('TEST', lo, 10, 9)
    data = ObservedSeries(SOURCE, days[0], days[0],
                          [Minute(lo+timedelta(minutes=1), 10, 11, 9, 10, 10000)])
    account.observe_entry('TEST', data, lo+timedelta(minutes=1))
    assert not account.positions and account.cash == pytest.approx(10000)


def test_empty_settlement_step_still_prevents_clock_reversal():
    account, _, _, lo = account_fixture()
    account.release_settlements(lo+timedelta(minutes=1))
    with pytest.raises(ValueError, match='chronological'):
        account.reserve('TEST', lo, 10, 9)


def test_exit_retries_missing_minutes_and_settles_two_sessions_later():
    account, _, days, lo = account_fixture()
    data = ObservedSeries(SOURCE, days[0], days[0],
                          [Minute(lo, 10, 11, 9, 10, 200),
                           Minute(lo+timedelta(minutes=2), 11, 12, 10, 11, 100)])
    account.reserve('TEST', lo, 10, 9)
    account.observe_entry('TEST', data, lo+timedelta(minutes=1))
    account.request_exit('TEST', lo+timedelta(minutes=1))
    assert not account.reserve('OTHER', lo+timedelta(minutes=1), 10, 9)
    account.observe_exit('TEST', data, lo+timedelta(minutes=1), lo+timedelta(minutes=2))
    assert account.positions['TEST']['quantity'] == 2
    account.observe_exit('TEST', data, lo+timedelta(minutes=2), lo+timedelta(minutes=3))
    assert account.positions['TEST']['quantity'] == 1
    assert account.positions['TEST']['basis'] == pytest.approx(10.031)
    assert account.closed_roundtrips == 0
    with pytest.raises(ValueError, match='repeated exit'):
        account.observe_exit('TEST', data, lo+timedelta(minutes=2), lo+timedelta(minutes=3))
    cash = account.cash
    next_lo, _ = ObservedSeries(SOURCE, days[1], days[1], []).bounds(days[1])
    account.release_settlements(next_lo)
    assert account.cash == cash
    second_lo, _ = ObservedSeries(SOURCE, days[2], days[2], []).bounds(days[2])
    account.release_settlements(second_lo)
    assert account.cash == pytest.approx(cash+10.9659)
    next_data = ObservedSeries(SOURCE, days[2], days[2],
                               [Minute(second_lo, 12, 13, 11, 12, 100)])
    account.observe_exit('TEST', next_data, second_lo, second_lo+timedelta(minutes=1))
    assert not account.positions and account.closed_roundtrips == 1
    assert account.summary()['net_profit'] == pytest.approx(22.9287-20.062)


def replay_fixture(next_day=True):
    calendar = ObservedSeries(SOURCE, date(2014, 3, 3), date(2014, 3, 24), [])
    days = calendar.sessions[:16 if next_day else 15]
    inputs = []
    for index, day in enumerate(days):
        lo, _ = calendar.bounds(day)
        rows = [Minute(lo+timedelta(minutes=m), 10, 11, 9, 10.5,
                       100 if index != 14 else 200) for m in range(5)]
        if index == 14:
            rows += [Minute(lo+timedelta(minutes=m), 11, 13, 10, 12, 100)
                     for m in range(5, 10)]
            rows += [Minute(lo+timedelta(minutes=10), 12, 13, 11, 12, 100000)]
        if index == 15:
            rows = [Minute(lo+timedelta(minutes=m), 13, 14, 12, 13, 10000)
                    for m in range(5)]
        inputs.append((day, {'TEST': ObservedSeries(SOURCE, day, day, rows)}))
    return {'sessions': days, 'contract': {'members': ['TEST']}, 'days': inputs}


def test_replay_keeps_overnight_quantity_and_uses_original_cash():
    events = {'base': [], 'stress': []}
    result = replay_research(replay_fixture(), {s: rows.append for s, rows in events.items()})
    for name, scenario in result['scenarios'].items():
        assert scenario['closed_roundtrips'] == 1
        assert scenario['unclosed_quantity'] == 0 and scenario['net_profit'] > 0
        assert scenario['cash'] < 10000 and scenario['unsettled'] > 0
        assert scenario['cash']+scenario['unsettled']-10000 == pytest.approx(
            scenario['net_profit'])
        sales = [e for e in events[name] if e['kind'] == 'EXIT_OBSERVED' and e['quantity']]
        assert [e['quantity'] for e in sales] == [100, 65]
        assert all(e['at'].startswith('2014-03-24') for e in sales)
        assert all(e['due'].startswith('2014-03-26') for e in sales)
        assert [e['sequence'] for e in events[name]] == list(range(1, len(events[name])+1))
    assert result['status'] == 'DEVELOPMENT_REJECTED'  # One roundtrip is not 200.
    assert result['orders_submitted'] == 0 and not result['live_eligible']


def test_terminal_unclosed_replay_has_no_invented_liquidation():
    result = replay_research(replay_fixture(next_day=False))
    for scenario in result['scenarios'].values():
        assert scenario['unclosed_quantity'] == 165
        assert scenario['net_profit'] is None and scenario['net_return'] is None
        assert scenario['closed_roundtrips'] == 0
        assert scenario['positions']['TEST']['exit_pending']


def test_replay_rejects_skipped_session_and_missing_member():
    inputs = replay_fixture()
    inputs['days'] = inputs['days'][1:]
    with pytest.raises(ValueError, match='every calendar session'):
        replay_research(inputs)
    inputs = replay_fixture()
    inputs['days'][0][1].clear()
    with pytest.raises(ValueError, match='every calendar session'):
        replay_research(inputs)
