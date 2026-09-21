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
