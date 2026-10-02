"""Small offline transfer/CLI counterexamples; actual data replay runs remotely."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def command():
    spec = importlib.util.spec_from_file_location(
        'volume_priority_command', ROOT/'scripts/volume_priority_research.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def transfer(tmp_path, monkeypatch, command):
    pytest.importorskip('cryptography', reason='pinned research runtime required by 206 CI')
    from auto_invest.analytics import sparse_opening_research as parent
    from auto_invest.analytics import volume_priority_research as candidate

    source = tmp_path/'source'
    source.mkdir()
    members, files, inventory = ['AAA', 'BBB'], {}, {}
    for symbol in members:
        raw = (f'timestamp_utc,symbol,open,high,low,close,volume\n'
               f'2014-03-03T14:30:00+00:00,{symbol},10,11,9,10,100\n').encode()
        (source/f'{symbol}.csv').write_bytes(raw)
        inventory[symbol] = dict(sha256='a'*64, file_symbol=symbol)
        files[symbol] = dict(path=f'{symbol}.csv', sha256=hashlib.sha256(raw).hexdigest(),
                             original_sha256='a'*64, file_symbol=symbol,
                             provider='hfdatalibrary-pitrading',
                             adjustment='source-split-dividend-adjusted',
                             issuer_lineage_status='unverified')
    raw = json.dumps(dict(schema_version=2, symbols=members, start='2014-03-02',
                          end='2014-03-03', calendar='XNYS', files=files)).encode()
    manifest = source/'manifest.json'
    manifest.write_bytes(raw)
    contract = candidate.read_contract()
    contract['input_manifest_sha256'] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(candidate, 'read_contract', lambda: contract)
    monkeypatch.setattr(parent, 'sealed_contract', lambda _: (
        dict(members=members, period=dict(first='2014-03-02', last='2014-03-03')), inventory))
    monkeypatch.setenv('SPARSE_RESEARCH_INPUT_KEY', '1a'*32)
    monkeypatch.setattr(command.time, 'sleep', lambda _: None)
    output = tmp_path/'encrypted'
    command.stage(manifest, output)
    monkeypatch.setattr(command, 'LOCK', output/'input-lock.json')
    return command, source, output


def test_existing_output_is_refused_before_credentials_or_input(command, tmp_path, monkeypatch):
    monkeypatch.delenv('SPARSE_RESEARCH_INPUT_KEY', raising=False)
    with pytest.raises(FileExistsError):
        command.stage(tmp_path/'absent', tmp_path)


def test_roundtrip_authenticates_raw_identity_without_publishing_plaintext(transfer):
    command, source, output = transfer
    assert not list(output.glob('*.csv'))
    with command.plaintext_inputs(output) as manifest:
        assert manifest.read_bytes() == (source/'manifest.json').read_bytes()
        for symbol in ('AAA', 'BBB'):
            assert (manifest.parent/f'{symbol}.csv').read_bytes() == (
                source/f'{symbol}.csv').read_bytes()
        directory = manifest.parent
    assert not directory.exists()


@pytest.mark.parametrize('key', ['', 'secret-example', '2b'*32, 'ff'*31])
def test_missing_malformed_or_wrong_key_is_refused(transfer, monkeypatch, key):
    command, _, output = transfer
    monkeypatch.setenv('SPARSE_RESEARCH_INPUT_KEY', key)
    with pytest.raises(ValueError), command.plaintext_inputs(output):
        pytest.fail('bad key reached price consumer')


def test_ciphertext_change_is_refused_before_decryption(transfer):
    command, _, output = transfer
    path = output/'AAA.csv.aesgcm'
    raw = path.read_bytes()
    path.write_bytes(raw[:-1]+bytes([raw[-1] ^ 1]))
    with pytest.raises(ValueError), command.plaintext_inputs(output):
        pytest.fail('tampered ciphertext reached consumer')


def test_duplicate_nonce_does_not_write_a_completion_receipt(transfer, tmp_path, monkeypatch):
    command, source, _ = transfer
    monkeypatch.setattr(command.secrets, 'token_bytes', lambda _: b'x'*12)
    failed = tmp_path/'failed'
    with pytest.raises(ValueError):
        command.stage(source/'manifest.json', failed)
    assert not (failed/'COMPLETE.json').exists()


def test_symlink_source_is_refused_without_touching_target(transfer, tmp_path):
    command, source, _ = transfer
    target = tmp_path/'unchanged'
    raw = (source/'AAA.csv').read_bytes()
    target.write_bytes(raw)
    (source/'AAA.csv').unlink()
    (source/'AAA.csv').symlink_to(target)
    with pytest.raises(ValueError):
        command.stage(source/'manifest.json', tmp_path/'refused')
    assert target.read_bytes() == raw


def test_plaintext_limit_is_enforced_before_success_receipt(transfer, tmp_path, monkeypatch):
    command, source, _ = transfer
    monkeypatch.setattr(command, 'RAW_LIMIT', 20)
    output = tmp_path/'too-large'
    with pytest.raises(ValueError):
        command.stage(source/'manifest.json', output)
    assert not (output/'COMPLETE.json').exists()


def test_duplicate_json_keys_are_refused(command):
    with pytest.raises(ValueError):
        command.json_value(b'{"files": {}, "files": {}}')


def test_cli_replay_and_full_recompute_are_independently_repeatable(
        transfer, tmp_path, monkeypatch, capsys):
    command, _, fixture = transfer
    # Small synthetic source only. Production has no identity override flag.
    monkeypatch.setattr(command, 'code_identity', lambda: {'synthetic_test_only': 'a'*64})
    output = tmp_path/'evidence'
    assert command.main(['replay', '--fixture', str(fixture), '--output', str(output)]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'DEVELOPMENT_REJECTED'
    assert command.main(['verify', '--fixture', str(fixture), '--evidence', str(output)]) == 0
    assert json.loads(capsys.readouterr().out)['recomputed'] is True
    before = (output/'result.json').read_bytes()
    assert command.main(['replay', '--fixture', str(fixture), '--output', str(output)]) == 2
    assert 'RESEARCH_INPUT_OR_EVIDENCE_REJECTED' in capsys.readouterr().out
    assert (output/'result.json').read_bytes() == before


def test_self_consistent_tampered_ledger_is_rejected_by_source_recomputation(
        transfer, tmp_path, monkeypatch):
    command, _, fixture = transfer
    monkeypatch.setattr(command, 'code_identity', lambda: {'synthetic_test_only': 'a'*64})
    output = tmp_path/'evidence'
    checked = command.replay(fixture, output)
    result = json.loads((output/'result.json').read_bytes())
    for scenario in ('base', 'stress'):
        path = output/f'{scenario}.jsonl'
        events = [json.loads(line) for line in path.read_text().splitlines()]
        assert events and all(row['kind'] == 'INPUT_UNAVAILABLE' for row in events)
        for row in events:
            row['reason'] = 'OPENING_MISSING'
        path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in events))
        result['scenarios'][scenario]['input_unavailable_counts'] = {'OPENING_MISSING': len(events)}
        result['ledger_sha256'][scenario] = command.fingerprint(path)[0]
    (output/'result.json').write_bytes(command.encoded(result))
    (output/'COMPLETE.json').write_bytes(command.encoded(dict(
        result_sha256=command.fingerprint(output/'result.json')[0], **checked)))
    assert command.verify_evidence(output, command.fingerprint(fixture/'index.json')[0]) == checked
    with pytest.raises(ValueError):
        command.verify(fixture, output)


def test_cli_error_does_not_print_contact_key_or_private_path(
        command, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('SPARSE_RESEARCH_INPUT_KEY', 'private-key-example')
    private = tmp_path/'private-contact@example.invalid'
    assert command.main(['stage', '--manifest', str(private),
                         '--output', str(tmp_path/'output')]) == 2
    message = capsys.readouterr().out
    assert json.loads(message) == {'error': 'RESEARCH_INPUT_OR_EVIDENCE_REJECTED'}
    assert 'private-key' not in message and str(private) not in message and '@' not in message


@pytest.mark.parametrize('field,value', [
    ('path', '../AAA.csv.aesgcm'), ('nonce', '00'), ('plaintext_size', True),
    ('plaintext_size', 65*1024*1024), ('ciphertext_size', 0),
    ('compressed_size', -1), ('plaintext_sha256', '0'*64),
])
def test_even_resealed_invalid_transfer_metadata_is_refused(transfer, field, value):
    command, _, output = transfer
    index = json.loads((output/'index.json').read_bytes())
    index['files']['AAA'][field] = value
    raw = command.encoded(index)
    (output/'index.json').write_bytes(raw)
    lock = json.loads((output/'input-lock.json').read_bytes())
    lock['index_sha256'] = command.sha(raw)
    (output/'input-lock.json').write_bytes(command.encoded(lock))
    (output/'COMPLETE.json').write_bytes(command.encoded(dict(
        schema_version=1, index_sha256=command.sha(raw))))
    with pytest.raises(ValueError), command.plaintext_inputs(output):
        pytest.fail('invalid sealed metadata reached consumer')


def test_duplicate_nonce_in_transfer_index_is_refused(transfer):
    command, _, output = transfer
    index = json.loads((output/'index.json').read_bytes())
    index['files']['BBB']['nonce'] = index['files']['AAA']['nonce']
    raw = command.encoded(index)
    (output/'index.json').write_bytes(raw)
    lock = json.loads((output/'input-lock.json').read_bytes())
    lock['index_sha256'] = command.sha(raw)
    (output/'input-lock.json').write_bytes(command.encoded(lock))
    (output/'COMPLETE.json').write_bytes(command.encoded(dict(
        schema_version=1, index_sha256=command.sha(raw))))
    with pytest.raises(ValueError), command.plaintext_inputs(output):
        pytest.fail('duplicate nonce reached consumer')


def reseal_index(command, output, index):
    raw = command.encoded(index)
    (output/'index.json').write_bytes(raw)
    lock = json.loads((output/'input-lock.json').read_bytes())
    lock['index_sha256'] = command.sha(raw)
    (output/'input-lock.json').write_bytes(command.encoded(lock))
    (output/'COMPLETE.json').write_bytes(command.encoded(dict(
        schema_version=1, index_sha256=command.sha(raw))))


def test_authenticated_gzip_expansion_is_bounded_by_declared_plaintext_size(transfer):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    command, _, output = transfer
    index = json.loads((output/'index.json').read_bytes())
    item = index['files']['AAA']
    item['plaintext_size'] = 8
    compressed = gzip.compress(b'x'*4096, mtime=0)
    encrypted = AESGCM(command.research_key()).encrypt(
        bytes.fromhex(item['nonce']), compressed,
        command.aad(index['manifest_sha256'], 'AAA', item['plaintext_sha256'], 8))
    item.update(compressed_size=len(compressed), ciphertext_size=len(encrypted),
                ciphertext_sha256=command.sha(encrypted))
    (output/item['path']).write_bytes(encrypted)
    reseal_index(command, output, index)
    with pytest.raises(ValueError), command.plaintext_inputs(output):
        pytest.fail('authenticated compressed bomb reached consumer')


def test_authenticated_identity_cannot_be_changed_by_resealing_metadata(transfer):
    command, _, output = transfer
    index = json.loads((output/'index.json').read_bytes())
    index['files']['AAA']['plaintext_size'] += 1
    reseal_index(command, output, index)
    with pytest.raises(ValueError, match='authentication'), command.plaintext_inputs(output):
        pytest.fail('changed AAD reached consumer')


@pytest.mark.parametrize('change', ['missing_receipt', 'manifest', 'symbol'])
def test_incomplete_or_changed_scope_is_rejected_before_key_access(
        transfer, monkeypatch, change):
    command, _, output = transfer
    if change == 'missing_receipt':
        (output/'COMPLETE.json').unlink()
    elif change == 'manifest':
        (output/'input-manifest.json').write_bytes(b'{}')
    else:
        index = json.loads((output/'index.json').read_bytes())
        index['files']['CCC'] = index['files'].pop('BBB')
        reseal_index(command, output, index)

    def forbidden():
        pytest.fail('credentials accessed before source identity')

    monkeypatch.setattr(command, 'research_key', forbidden)
    with pytest.raises(ValueError), command.plaintext_inputs(output):
        pytest.fail('changed scope reached consumer')


def test_symlink_in_intermediate_source_directory_is_refused(transfer, tmp_path):
    command, source, _ = transfer
    alias = tmp_path/'directory-alias'
    alias.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError):
        command.stage(alias/'manifest.json', tmp_path/'refused-directory')


def test_fifo_source_is_refused_without_blocking(transfer, tmp_path):
    import os

    command, source, _ = transfer
    path = source/'AAA.csv'
    path.unlink()
    os.mkfifo(path)
    with pytest.raises(ValueError):
        command.stage(source/'manifest.json', tmp_path/'refused-fifo')
