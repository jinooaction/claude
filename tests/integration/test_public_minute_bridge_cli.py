from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from auto_invest.market_data.public_minute import SOURCES, PilotError, diagnose, fingerprint

SPEC = importlib.util.spec_from_file_location(
    'public_minute_bridge', Path(__file__).resolve().parents[2] / 'scripts/public_minute_bridge.py')
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def fixture(tmp_path):
    directory = tmp_path / 'archive'
    directory.mkdir()
    (directory / 'only.json').write_bytes(b'fixture')
    expected = (('only.json', 7, hashlib.sha256(b'fixture').hexdigest()),)
    metadata = [{'name': name, 'size': size, 'digest': 'sha256:' + sha}
                for name, size, sha in expected]
    assets = tmp_path / 'assets.json'
    assets.write_text(json.dumps(metadata))
    return directory, assets, expected, metadata


def test_production_asset_pins_match_whole_original_receipt():
    assert len(bridge.INPUT_ASSETS) == 6
    assert sum(s[1] for s in bridge.INPUT_ASSETS) == 517681604
    assert bridge.INPUT_TAG.endswith('fcfd9a6c3fe2209830aeaa7adf1725be62788d6f')
    assert bridge.INPUT_RELEASE == 402595786


@pytest.mark.parametrize('mutation', ['extra', 'duplicate', 'size', 'digest', 'local', 'symlink'])
def test_local_and_remote_asset_counterexamples(tmp_path, mutation):
    directory, assets, expected, metadata = fixture(tmp_path)
    if mutation == 'extra':
        (directory / 'unreviewed.json').write_text('extra')
    elif mutation == 'duplicate':
        metadata.append(metadata[0])
    elif mutation in ('size', 'digest'):
        metadata[0][mutation] = 99 if mutation == 'size' else 'sha256:' + '0' * 64
    elif mutation == 'local':
        (directory / 'only.json').write_text('changed')
    else:
        (directory / 'only.json').unlink()
        (directory / 'only.json').symlink_to(assets)
    assets.write_text(json.dumps(metadata))
    with pytest.raises(PilotError):
        bridge.verify_inputs(directory, assets, expected=expected)


def test_valid_metadata_and_local_bytes_are_both_required(tmp_path):
    directory, assets, expected, _ = fixture(tmp_path)
    bridge.verify_inputs(directory, assets, expected=expected)


def test_failed_input_never_reaches_key_or_analysis(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('key accessed')
    monkeypatch.setattr(bridge.pilot, 'cipher', forbidden)
    archive = tmp_path / 'archive'
    archive.mkdir()
    assets = tmp_path / 'assets.json'
    assets.write_text('[]')
    output = tmp_path / 'result'
    assert bridge.run(archive, assets, output) == 1
    report = json.loads((output / 'report.json').read_text())
    assert report['source_authenticated'] is False and report['analysis_complete'] is False
    assert report['strategy_eligible'] is False and report['provider_eligible'] is False
    assert report['orders_submitted'] == 0 and report['returns_examined'] is False
    assert report['reason'] == 'ARCHIVE_INVENTORY_REJECTED'


def test_unexpected_error_and_contact_are_sanitized(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('private-contact@example.test')
    monkeypatch.setattr(bridge, 'verify_inputs', fail)
    assert bridge.run(tmp_path, tmp_path / 'assets.json', tmp_path / 'result') == 1
    assert 'private-contact' not in (tmp_path / 'result/report.json').read_text()


def test_crosscheck_rejects_original_report_disagreement():
    from auto_invest.market_data.intraday import SYMBOLS
    derived = {'calendar_sessions': 21, 'regular_minutes_by_symbol': dict.fromkeys(SYMBOLS, 1),
               'missing_minutes_by_symbol': dict.fromkeys(SYMBOLS, 8189),
               'minute_complete_sessions_by_symbol': dict.fromkeys(SYMBOLS, [])}
    original = {'calendar_sessions': 21, 'runtime_universe_coverage': {
        s: {'regular_rows': 1, 'missing_regular_minutes': 8189, 'complete_sessions': 0}
        for s in SYMBOLS}}
    bridge.crosscheck(derived, original)
    original['runtime_universe_coverage']['GLD']['missing_regular_minutes'] = 0
    with pytest.raises(PilotError, match='ORIGINAL_COVERAGE_MISMATCH'):
        bridge.crosscheck(derived, original)


def encrypted_fixture(tmp_path, monkeypatch):
    import duckdb
    raw = tmp_path / 'raw'
    raw.mkdir()
    sources = []
    for source, date in zip(SOURCES, ['2014-01-02', '2019-12-02'], strict=True):
        path = raw / source.name
        with duckdb.connect() as con:
            con.execute('CREATE TABLE bars(timestamp TIMESTAMPTZ, open DOUBLE, high DOUBLE, '
                        'low DOUBLE, close DOUBLE, volume DOUBLE, ticker VARCHAR)')
            for minute in range(5):
                con.execute('INSERT INTO bars VALUES (?, 10, 11, 9, 10, 100, ?)',
                            [f'{date}T14:{30+minute}:00Z', 'SPY'])
            con.execute('COPY bars TO ? (FORMAT PARQUET)', [str(path)])
        size, sha = fingerprint(path)
        sources.append(replace(source, size=size, sha256=sha))
    monkeypatch.setenv('SPARSE_RESEARCH_INPUT_KEY', '42' * 32)
    archive = tmp_path / 'archive'
    bridge.pilot.pack(raw, archive, sources=tuple(sources))
    bridge.pilot.write_new(archive / 'report.json', {'quality': [
        diagnose(raw / s.name, s.month) for s in sources]})
    bridge.pilot.write_new(archive / 'claim.json', {'strategy_eligible': False})
    bridge.pilot.write_new(archive / 'archive-receipt.json', {'archive_complete': True})
    expected = tuple((p.name, *fingerprint(p)) for p in sorted(archive.iterdir()))
    monkeypatch.setattr(bridge, 'INPUT_ASSETS', expected)
    monkeypatch.setattr(bridge, 'SOURCES', tuple(sources))
    assets = tmp_path / 'assets.json'
    assets.write_text(json.dumps([{'name': name, 'size': size, 'digest': 'sha256:' + sha}
                                 for name, size, sha in expected]))
    return archive, assets


def test_real_aead_restore_and_minute_analysis_emit_only_diagnostics(tmp_path, monkeypatch):
    archive, assets = encrypted_fixture(tmp_path, monkeypatch)
    output = tmp_path / 'result'
    assert bridge.run(archive, assets, output) == 0
    report = json.loads((output / 'report.json').read_text())
    assert report['source_authenticated'] is True and report['analysis_complete'] is True
    assert len(report['months']) == 2 and report['returns_examined'] is False
    assert report['heldout_sessions_opened'] == 0 and report['prior_trials_minimum'] == 36
    assert report['months'][0]['sessions'][0]['symbols']['SPY']['usable_bins'] == 1
    assert {p.name for p in output.iterdir()} == {'report.json'}
    assert set(archive.iterdir()) and not list(output.glob('*.parquet'))
    before = (output / 'report.json').read_bytes()
    with pytest.raises(FileExistsError):
        bridge.run(archive, assets, output)
    assert (output / 'report.json').read_bytes() == before


def test_wrong_key_does_not_authenticate_or_create_price_output(tmp_path, monkeypatch):
    archive, assets = encrypted_fixture(tmp_path, monkeypatch)
    monkeypatch.setenv('SPARSE_RESEARCH_INPUT_KEY', '43' * 32)
    assert bridge.run(archive, assets, tmp_path / 'result') == 1
    report = json.loads((tmp_path / 'result/report.json').read_text())
    assert report['source_authenticated'] is False and report['months'] == []
    assert report['reason'] == 'ARCHIVE_AUTHENTICATION_FAILED'


def test_analysis_failure_preserves_authenticated_state_without_completion(tmp_path, monkeypatch):
    archive, assets = encrypted_fixture(tmp_path, monkeypatch)
    def fail(*args, **kwargs):
        raise PilotError('SYNTHETIC_ANALYSIS_REJECTED')
    monkeypatch.setattr(bridge, 'analyse', fail)
    assert bridge.run(archive, assets, tmp_path / 'result') == 1
    report = json.loads((tmp_path / 'result/report.json').read_text())
    assert report['source_authenticated'] is True and report['analysis_complete'] is False
    assert report['strategy_eligible'] is False and report['orders_submitted'] == 0
