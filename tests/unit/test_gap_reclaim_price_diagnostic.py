"""Counterexamples for the fixed opening gap diagnostic, never broker orders."""

import gzip
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import exchange_calendars as xcals
import pytest

PATH = Path(__file__).resolve().parents[2] / 'scripts/gap_reclaim_price_diagnostic.py'
spec = importlib.util.spec_from_file_location('gap_reclaim', PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def observed(**changes):
    row = {'previous': {'close': '100', 'volume': '1'},
           'opening': {'open': '98', 'close': '98', 'volume': '1'},
           'signal': {'open': '98', 'close': '99', 'volume': '1'},
           'entry': {'open': '99', 'close': '99', 'volume': '1'},
           'exit': {'open': '101', 'close': '101', 'volume': '1'}}
    row.update(changes)
    return row


def test_gap_boundary_and_fee_application_are_exact():
    row = mod.score_day('MSFT', '2017-01-03', observed(), {'base': 31, 'stress': 40})
    assert row['status'] == 'REFERENCE_PAIR'
    assert Decimal(row['returns']['base']) == Decimal('101') * Decimal('.9969') / (
        Decimal('99') * Decimal('1.0031')) - 1
    assert mod.score_day('MSFT', '2017-01-03', observed(opening={
        'open': '98.000001', 'close': '98', 'volume': '1'}), {'base': 31})['status'] == 'NO_SIGNAL'


def test_missing_future_reference_cannot_change_no_signal():
    data = observed(signal={'open': '98', 'close': '97', 'volume': '1'}, entry=None, exit=None)
    assert mod.score_day('MSFT', '2017-01-03', data, {'base': 31})['status'] == 'NO_SIGNAL'
    assert mod.score_day('MSFT', '2017-01-03', observed(exit=None), {
        'base': 31})['status'] == 'MISSING_REFERENCE'
    assert mod.score_day('MSFT', '2017-01-03', observed(previous=None), {
        'base': 31})['status'] == 'MISSING_SIGNAL_OBSERVATION'


def test_calendar_uses_exact_prior_close_dst_and_early_close():
    cal = xcals.get_calendar('XNYS')
    plan = mod.clock_plan(cal, ['2014-07-07', '2017-03-13', '2017-11-24'])
    assert plan['2014-07-07']['previous'] == b'2014-07-03T16:59:00+00:00'
    assert plan['2017-03-13']['opening'] == b'2017-03-13T13:30:00+00:00'
    assert plan['2017-11-24']['exit'] not in mod.allowed_stamps(cal, plan)


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '0'])
def test_invalid_prices_are_not_trading_observations(value):
    with pytest.raises(ValueError):
        mod.parse_bar([b'2017-01-03T14:30:00+00:00', b'MSFT', value.encode(),
                       b'100', b'1', b'99', b'1'])


def test_positive_reference_pairs_cannot_grant_live_authority():
    rows = [mod.score_day('MSFT', '2017-01-03', observed(), {'base': 31, 'stress': 40})] * 200
    summary = mod.summarize(rows, 200)
    assert summary['verdict'] == 'EXECUTION_MODEL_REQUIRED'
    assert summary['live_eligible'] is False
    assert summary['promotion_allowed'] is False
    assert summary['orders_submitted'] == summary['actual_capital_fraction'] == 0
    assert mod.summarize(rows[:199], 200)['verdict'] == 'INSUFFICIENT_REFERENCE_PAIRS'


@pytest.fixture
def fixed_slice(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    stamps = ['2016-12-30T20:59:00+00:00', '2017-01-03T14:30:00+00:00',
              '2017-01-03T14:45:00+00:00', '2017-01-03T14:47:00+00:00',
              '2017-01-03T20:56:00+00:00']
    files = {}
    for symbol in ('MSFT', 'DD', 'UTX'):
        lines = [mod.HEADER + b'\n']
        for stamp, price in zip(stamps, (100, 98, 99, 99, 101), strict=True):
            lines.append(f'{stamp},{symbol},{price},{price+1},{price-1},{price},1\n'.encode())
        path = source / f'{symbol}.csv'
        path.write_bytes(b''.join(lines))
        files[symbol] = {'path': path.name, 'provider': 'hfdatalibrary-pitrading',
                         'adjustment': 'source-split-dividend-adjusted', 'sha256': mod.digest(path)}
    manifest = source / 'manifest.json'
    manifest.write_text(json.dumps({'calendar': 'XNYS', 'files': files}))
    contract = {'universe': ['MSFT'], 'excluded_symbols': ['DD', 'UTX'],
                'development_sessions': ['2017-01-03', '2017-01-03'],
                'price_manifest_sha256': mod.digest(manifest), 'family_id': 'unit-only',
                'minimum_prior_trials': 33, 'minimum_reference_pairs': 200,
                'costs_per_side_bps': {'base': 31, 'stress': 40}}
    monkeypatch.setattr(mod, 'read_contract', lambda: contract)
    fixture = tmp_path / 'fixture'
    prepared = mod.stage(manifest, source, fixture, 0)
    lock = tmp_path / 'lock.json'
    lock.write_text(json.dumps({'index_sha256': prepared['index_sha256']}))
    monkeypatch.setattr(mod, 'LOCK', lock)
    monkeypatch.setattr(mod, 'LOCK_SHA', mod.digest(lock))
    return fixture, contract, source, manifest


def test_full_source_verification_and_reference_slice_replay(fixed_slice):
    fixture, contract, source, _ = fixed_slice
    assert gzip.decompress((fixture / 'MSFT.csv.gz').read_bytes()) == (
        source / 'MSFT.csv').read_bytes()
    index = json.loads((fixture / 'index.json').read_text())
    assert set(index['files']) == {'MSFT'}
    report = mod.calculate(fixture)
    assert report['summary']['reference_pairs_not_fills'] == 1
    assert report['summary']['live_eligible'] is False
    assert mod.read_views(fixture, contract)['MSFT']['2017-01-03']['previous']['close'] == '100'
    assert mod.calculate(fixture) == report


@pytest.mark.parametrize('name', ['index.json', 'MSFT.csv.gz', 'source-manifest.json'])
def test_any_slice_tamper_is_refused_before_scoring(fixed_slice, name):
    fixture, _, _, _ = fixed_slice
    with (fixture / name).open('ab') as handle:
        handle.write(b'tampered')
    with pytest.raises(ValueError):
        mod.calculate(fixture)


def test_failed_full_source_never_publishes_completed_index(fixed_slice, tmp_path):
    _, _, source, manifest = fixed_slice
    with (source / 'UTX.csv').open('ab') as handle:
        handle.write(b'2018-01-03T20:56:00+00:00,UTX,100,101,99,100,1\n')
    output = tmp_path / 'failed'
    with pytest.raises(ValueError, match='full source SHA'):
        mod.stage(manifest, source, output, 0)
    assert not (output / 'index.json').exists()


def test_prepare_and_score_refuse_overwrite(fixed_slice, monkeypatch):
    fixture, _, source, manifest = fixed_slice
    with pytest.raises(FileExistsError):
        mod.stage(manifest, source, fixture, 0)
    output = fixture / 'existing.json'
    output.write_text('keep me')
    monkeypatch.setattr(sys, 'argv', ['gap', 'score', '--fixture-dir', str(fixture),
                                     '--output', str(output)])
    with pytest.raises(FileExistsError):
        mod.main()
    assert output.read_text() == 'keep me'


def test_unlocked_input_cannot_score(fixed_slice, monkeypatch):
    fixture, _, _, _ = fixed_slice
    monkeypatch.setattr(mod, 'LOCK_SHA', '0' * 64)
    with pytest.raises(ValueError, match='input not locked'):
        mod.calculate(fixture)


def test_duplicate_source_timestamp_is_not_silently_deduplicated(fixed_slice, tmp_path):
    _, _, source, manifest = fixed_slice
    path = source / 'MSFT.csv'
    first = path.read_bytes().splitlines(keepends=True)[1]
    with path.open('ab') as handle:
        handle.write(first)
    with pytest.raises(ValueError, match='out-of-order source'):
        mod.stage(manifest, source, tmp_path / 'duplicate', 0)


def test_future_or_out_of_session_slice_is_rejected_even_with_new_lock(fixed_slice, monkeypatch):
    fixture, _, _, _ = fixed_slice
    path = fixture / 'MSFT.csv.gz'
    raw = gzip.decompress(path.read_bytes()) + b'2018-01-03T20:56:00+00:00,MSFT,100,101,99,100,1\n'
    path.write_bytes(gzip.compress(raw, mtime=0))
    index_path = fixture / 'index.json'
    index = json.loads(index_path.read_text())
    index['files']['MSFT']['gzip_sha256'] = mod.digest(path)
    index_path.write_text(json.dumps(index))
    mod.LOCK.write_text(json.dumps({'index_sha256': mod.digest(index_path)}))
    monkeypatch.setattr(mod, 'LOCK_SHA', mod.digest(mod.LOCK))
    with pytest.raises(ValueError, match='slice timestamp'):
        mod.calculate(fixture)


def test_preregistration_tamper_cannot_change_rule(tmp_path, monkeypatch):
    path = tmp_path / 'contract.json'
    path.write_bytes(mod.CONTRACT.read_bytes() + b' ')
    monkeypatch.setattr(mod, 'CONTRACT', path)
    with pytest.raises(ValueError, match='preregistration changed'):
        mod.read_contract()
