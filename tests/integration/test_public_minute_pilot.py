from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from auto_invest.market_data.public_minute import SOURCES, PilotError

SPEC = importlib.util.spec_from_file_location(
    'public_minute_pilot', Path(__file__).resolve().parents[2] / 'scripts/public_minute_pilot.py')
assert SPEC and SPEC.loader
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def test_failed_collect_emits_safe_incomplete_receipt(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('secret-contact@example.test')
    monkeypatch.setattr(pilot, 'collect', fail)
    assert pilot.run_collect(tmp_path / 'raw', tmp_path / 'report') == 1
    report = json.loads((tmp_path / 'report/report.json').read_text())
    assert not report['full_source_verified'] and not report['archive_complete']
    assert report['orders_submitted'] == 0 and not report['returns_examined']
    assert not report['provider_eligible'] and not report['strategy_eligible']
    assert 'secret-contact' not in str(report)


@pytest.mark.parametrize('value', ['', 'bad', 'x' * 64])
def test_pack_missing_or_invalid_key_does_not_emit_raw(tmp_path, monkeypatch, value):
    monkeypatch.setenv('SPARSE_RESEARCH_INPUT_KEY', value)
    with pytest.raises(PilotError):
        pilot.pack(tmp_path, tmp_path / 'archive')
    assert not (tmp_path / 'archive').exists()


def test_archive_authenticated_with_unique_nonce_and_context(tmp_path, monkeypatch):
    AESGCM = pytest.importorskip('cryptography.hazmat.primitives.ciphers.aead').AESGCM
    InvalidTag = pytest.importorskip('cryptography.exceptions').InvalidTag
    raw = tmp_path / 'raw'
    raw.mkdir()
    sources = []
    for source, value in zip(SOURCES, [b'first', b'second'], strict=True):
        (raw / source.name).write_bytes(value)
        sources.append(replace(source, size=len(value), sha256=hashlib.sha256(value).hexdigest()))
    monkeypatch.setenv('SPARSE_RESEARCH_INPUT_KEY', '42' * 32)
    archive = tmp_path / 'archive'
    pilot.pack(raw, archive, sources=tuple(sources))
    index = json.loads((archive / 'archive-index.json').read_text())
    assert len({item['nonce'] for item in index['files']}) == 2
    assert pilot.verify_archive(archive, sources=tuple(sources)) == 2
    first = index['files'][0]
    sealed = (archive / first['path']).read_bytes()
    with pytest.raises(InvalidTag):
        AESGCM(bytes.fromhex('42' * 32)).decrypt(bytes.fromhex(first['nonce']), sealed, b'wrong')
    with pytest.raises(PilotError):
        pilot.pack(raw, archive, sources=tuple(sources))
    (archive / first['path']).write_bytes(sealed[:-1] + bytes([sealed[-1] ^ 1]))
    with pytest.raises(PilotError):
        pilot.verify_archive(archive, sources=tuple(sources))


def test_production_and_holdout_are_not_imported():
    source = Path(SPEC.origin).read_text()
    assert 'auto_invest.execution' not in source
    assert 'KIS' not in source
    assert '495' not in source


def test_remote_digest_mismatch_cannot_claim_archive(tmp_path):
    data = tmp_path / 'safe'
    data.mkdir()
    for i in range(4):
        (data / f'{i}.json').write_bytes(b'{}')
    assets = tmp_path / 'assets.json'
    assets.write_text(json.dumps([{'name': f'{i}.json', 'size': 2, 'digest': 'sha256:wrong'}
                                 for i in range(4)]))
    receipt = tmp_path / 'receipt.json'
    with pytest.raises(PilotError):
        pilot.verify_assets(data, assets, receipt)
    assert not receipt.exists()


def test_valid_remote_assets_are_independently_confirmed(tmp_path, monkeypatch):
    pytest.importorskip('cryptography.hazmat.primitives.ciphers.aead')
    monkeypatch.setenv('SPARSE_RESEARCH_INPUT_KEY', '42' * 32)
    data = tmp_path / 'safe'
    raw = tmp_path / 'raw'
    raw.mkdir()
    sources = tuple(replace(s, size=2, sha256=hashlib.sha256(b'{}').hexdigest()) for s in SOURCES)
    for source in sources:
        (raw / source.name).write_bytes(b'{}')
    pilot.pack(raw, data, sources=sources)
    (data / 'claim.json').write_bytes(b'{}')
    (data / 'report.json').write_text(json.dumps({
        'full_source_verified': True, 'revision': pilot.REVISION,
        'files': [{'month': s.month, 'size': s.size, 'sha256': s.sha256} for s in sources],
        'strategy_eligible': False, 'provider_eligible': False, 'returns_examined': False,
        'orders_submitted': 0}))
    assets = tmp_path / 'assets.json'
    assets.write_text(json.dumps([{'name': p.name, 'size': p.stat().st_size,
                                 'digest': 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()}
                                 for p in data.iterdir()]))
    receipt = tmp_path / 'receipt.json'
    pilot.verify_assets(data, assets, receipt, sources=sources)
    result = json.loads(receipt.read_text())
    assert result['archive_complete'] and not result['strategy_eligible']
    assert result['orders_submitted'] == 0


def test_incomplete_remote_inventory_cannot_claim_whole_archive(tmp_path):
    data = tmp_path / 'safe'
    data.mkdir()
    (data / 'claim.json').write_bytes(b'{}')
    assets = tmp_path / 'assets.json'
    assets.write_text('[]')
    with pytest.raises(PilotError):
        pilot.verify_assets(data, assets, tmp_path / 'receipt.json')


def test_remote_job_requires_review_and_persistent_claim_before_network():
    source = (Path(__file__).resolve().parents[2] /
              '.github/workflows/public-minute-pilot.yml').read_text()
    assert 'vars.PUBLIC_MINUTE_SOURCE_SHA == github.event.pull_request.head.sha' in source
    assert source.index('gh release create') < source.index('public_minute_pilot.py collect')
    assert 'gh release delete' not in source and '--clobber' not in source
    assert 'SPARSE_RESEARCH_INPUT_KEY' in source
    assert 'raw/' not in source.split('path:')[-1]
