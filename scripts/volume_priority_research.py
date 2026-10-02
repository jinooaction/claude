"""Authenticated offline research transfer, replay, and full source recomputation."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
import re
import secrets
import stat
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'specs/194-sparse-opening-research/contracts'
LOCK = ROOT/'research-fixtures/206/input-lock.json'
CHUNK = 1024*1024
RAW_LIMIT, RAW_TOTAL = 64*CHUNK, 1536*CHUNK
CIPHER_LIMIT, CIPHER_TOTAL = 64*CHUNK, 512*CHUNK
JSON_LIMIT = CHUNK


def require(value):
    if not value:
        raise ValueError('research input or evidence rejected')


def json_value(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value)
            value[key] = item
        return value

    def reject_constant(_):
        raise ValueError('invalid JSON constant')

    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hex_value(value, length=64):
    return isinstance(value, str) and re.fullmatch(f'[0-9a-f]{{{length}}}', value) is not None


@contextmanager
def regular(path):
    # Walk directory descriptors: intermediate symlink replacement cannot redirect reads.
    path = Path(path).absolute()
    require('..' not in path.parts)
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            try:
                following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=directory)
            except OSError:
                raise ValueError('research path rejected') from None
            os.close(directory)
            directory = following
        try:
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 dir_fd=directory)
        except OSError:
            raise ValueError('research path rejected') from None
        with os.fdopen(descriptor, 'rb') as handle:
            require(stat.S_ISREG(os.fstat(handle.fileno()).st_mode))
            yield handle
    finally:
        os.close(directory)


def bounded(path, maximum):
    with regular(path) as handle:
        require(os.fstat(handle.fileno()).st_size <= maximum)
        raw = handle.read(maximum+1)
    require(len(raw) <= maximum)
    return raw


def fingerprint(path, maximum=None):
    digest, size = hashlib.sha256(), 0
    with regular(path) as handle:
        while chunk := handle.read(CHUNK):
            size += len(chunk)
            require(maximum is None or size <= maximum)
            digest.update(chunk)
    return digest.hexdigest(), size


def write_new(path, raw):
    with Path(path).open('xb') as handle:
        handle.write(raw)


def research_key():
    value = os.environ.get('SPARSE_RESEARCH_INPUT_KEY', '')
    require(hex_value(value))
    return bytes.fromhex(value)


def manifest_identity(raw):
    from auto_invest.analytics.sparse_opening_research import sealed_contract
    from auto_invest.analytics.volume_priority_research import read_contract

    contract = read_contract()
    require(sha(raw) == contract['input_manifest_sha256'])
    manifest = json_value(raw)
    parent, inventory = sealed_contract(PARENT)
    require(isinstance(manifest, dict) and set(manifest) == {
        'schema_version', 'symbols', 'start', 'end', 'calendar', 'files'})
    require(type(manifest['schema_version']) is int and manifest['schema_version'] == 2
            and manifest['calendar'] == 'XNYS'
            and manifest['start'] == parent['period']['first']
            and manifest['end'] == parent['period']['last'])
    members, files = manifest['symbols'], manifest['files']
    require(isinstance(members, list) and all(isinstance(s, str) for s in members)
            and len(members) == len(inventory) and set(members) == set(inventory)
            and isinstance(files, dict) and set(files) == set(inventory))
    for symbol, item in files.items():
        require(isinstance(item, dict) and set(item) == {
            'path', 'sha256', 'original_sha256', 'file_symbol', 'provider',
            'adjustment', 'issuer_lineage_status'})
        require(item['path'] == f'{symbol}.csv' and hex_value(item['sha256'])
                and item['original_sha256'] == inventory[symbol]['sha256']
                and item['file_symbol'] == inventory[symbol]['file_symbol']
                and item['provider'] == 'hfdatalibrary-pitrading'
                and item['adjustment'] == 'source-split-dividend-adjusted'
                and item['issuer_lineage_status'] == 'unverified')
    return contract, manifest


def identity():
    from auto_invest.analytics.volume_priority_research import CONTRACT_SHA256

    return CONTRACT_SHA256


def aad(manifest_sha, symbol, digest, size):
    return encoded(dict(contract_sha256=identity(), manifest_sha256=manifest_sha,
                        symbol=symbol, plaintext_sha256=digest, plaintext_size=size))


def stage(manifest_path, output):
    """Hash/gzip one file at a time, throttle local reads, then authenticate it."""
    # Refuse an existing output even when input/credentials are invalid.
    if output.exists() or output.is_symlink():
        raise FileExistsError('existing research output')
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw = bounded(manifest_path, JSON_LIMIT)
    _, manifest = manifest_identity(raw)
    cipher = AESGCM(research_key())
    output.mkdir(parents=True, exist_ok=False)
    nonces, items, raw_total, cipher_total = set(), {}, 0, 0
    for symbol in sorted(manifest['files']):
        info = manifest['files'][symbol]
        buffer, digest, size = io.BytesIO(), hashlib.sha256(), 0
        with regular(manifest_path.parent/info['path']) as handle:
            require(os.fstat(handle.fileno()).st_size <= RAW_LIMIT)
            with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=1, mtime=0) as zipped:
                while chunk := handle.read(CHUNK):
                    size += len(chunk)
                    require(size <= RAW_LIMIT and raw_total+size <= RAW_TOTAL)
                    digest.update(chunk)
                    zipped.write(chunk)
                    require(buffer.tell() <= CIPHER_LIMIT-16)
                    time.sleep(.05)
        require(size > 0 and digest.hexdigest() == info['sha256'])
        nonce = secrets.token_bytes(12)
        require(nonce not in nonces)
        nonces.add(nonce)
        compressed = buffer.getvalue()
        encrypted = cipher.encrypt(nonce, compressed, aad(sha(raw), symbol, info['sha256'], size))
        cipher_total += len(encrypted)
        raw_total += size
        require(len(encrypted) <= CIPHER_LIMIT and cipher_total <= CIPHER_TOTAL)
        name = f'{symbol}.csv.aesgcm'
        write_new(output/name, encrypted)
        items[symbol] = dict(path=name, nonce=nonce.hex(), plaintext_sha256=info['sha256'],
                             plaintext_size=size, compressed_size=len(compressed),
                             ciphertext_sha256=sha(encrypted), ciphertext_size=len(encrypted))
    index = encoded(dict(schema_version=1, contract_sha256=identity(),
                         manifest_sha256=sha(raw), files=items))
    lock = encoded(dict(schema_version=1, contract_sha256=identity(),
                        manifest_sha256=sha(raw), index_sha256=sha(index)))
    write_new(output/'input-manifest.json', raw)
    write_new(output/'index.json', index)
    write_new(output/'input-lock.json', lock)
    write_new(output/'COMPLETE.json', encoded(dict(schema_version=1, index_sha256=sha(index))))
    return dict(prepared=True, file_count=len(items), plaintext_bytes=raw_total,
                ciphertext_bytes=cipher_total, index_sha256=sha(index), orders_submitted=0)


def fixture_identity(directory):
    raw = bounded(directory/'input-manifest.json', JSON_LIMIT)
    _, manifest = manifest_identity(raw)
    index_raw = bounded(directory/'index.json', JSON_LIMIT)
    index = json_value(index_raw)
    lock = json_value(bounded(LOCK, JSON_LIMIT))
    receipt = json_value(bounded(directory/'COMPLETE.json', JSON_LIMIT))
    require(isinstance(lock, dict) and type(lock.get('schema_version')) is int
            and isinstance(receipt, dict) and type(receipt.get('schema_version')) is int)
    require(lock == dict(schema_version=1, contract_sha256=identity(),
                         manifest_sha256=sha(raw), index_sha256=sha(index_raw)))
    require(json_value(bounded(directory/'input-lock.json', JSON_LIMIT)) == lock)
    require(receipt == dict(schema_version=1, index_sha256=sha(index_raw)))
    require(isinstance(index, dict) and set(index) == {
        'schema_version', 'contract_sha256', 'manifest_sha256', 'files'})
    require(type(index['schema_version']) is int and index['schema_version'] == 1
            and index['contract_sha256'] == identity() and index['manifest_sha256'] == sha(raw)
            and isinstance(index['files'], dict)
            and set(index['files']) == set(manifest['files']))
    require({path.name for path in directory.iterdir()} == {
        'input-manifest.json', 'input-lock.json', 'index.json', 'COMPLETE.json',
        *(f'{s}.csv.aesgcm' for s in manifest['files'])})
    nonces, raw_total, cipher_total = set(), 0, 0
    for symbol, item in index['files'].items():
        require(isinstance(item, dict) and set(item) == {
            'path', 'nonce', 'plaintext_sha256', 'plaintext_size', 'compressed_size',
            'ciphertext_sha256', 'ciphertext_size'})
        require(item['path'] == f'{symbol}.csv.aesgcm' and hex_value(item['nonce'], 24)
                and item['nonce'] not in nonces and hex_value(item['ciphertext_sha256'])
                and item['plaintext_sha256'] == manifest['files'][symbol]['sha256'])
        nonces.add(item['nonce'])
        require(all(type(item[k]) is int for k in (
            'plaintext_size', 'compressed_size', 'ciphertext_size')))
        require(0 < item['plaintext_size'] <= RAW_LIMIT
                and 0 < item['compressed_size'] <= CIPHER_LIMIT-16
                and item['ciphertext_size'] == item['compressed_size']+16)
        raw_total += item['plaintext_size']
        cipher_total += item['ciphertext_size']
        require(raw_total <= RAW_TOTAL and cipher_total <= CIPHER_TOTAL)
        require(fingerprint(directory/item['path'], CIPHER_LIMIT) == (
            item['ciphertext_sha256'], item['ciphertext_size']))
    return raw, index


@contextmanager
def plaintext_inputs(directory):
    """Authenticate sealed files before exposing a private bounded plaintext snapshot."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw, index = fixture_identity(directory)
    cipher = AESGCM(research_key())
    with tempfile.TemporaryDirectory(prefix='research-206-') as folder:
        # Canonicalize only our newly created private directory (macOS /var is a symlink).
        private = Path(folder).resolve()
        for symbol in sorted(index['files']):
            item = index['files'][symbol]
            encrypted = bounded(directory/item['path'], CIPHER_LIMIT)
            require(len(encrypted) == item['ciphertext_size']
                    and sha(encrypted) == item['ciphertext_sha256'])
            try:
                compressed = cipher.decrypt(bytes.fromhex(item['nonce']), encrypted,
                    aad(sha(raw), symbol, item['plaintext_sha256'], item['plaintext_size']))
            except InvalidTag:
                raise ValueError('research authentication rejected') from None
            require(len(compressed) == item['compressed_size'])
            digest, size = hashlib.sha256(), 0
            with (gzip.GzipFile(fileobj=io.BytesIO(compressed), mode='rb') as zipped,
                  (private/f'{symbol}.csv').open('xb') as target):
                os.chmod(target.name, 0o600)
                while chunk := zipped.read(min(CHUNK, item['plaintext_size']-size+1)):
                    size += len(chunk)
                    require(size <= item['plaintext_size'] and size <= RAW_LIMIT)
                    digest.update(chunk)
                    target.write(chunk)
            require(size == item['plaintext_size']
                    and digest.hexdigest() == item['plaintext_sha256'])
        manifest = private/'manifest.json'
        write_new(manifest, raw)
        os.chmod(manifest, 0o600)
        yield manifest


def code_identity():
    paths = [Path(__file__).resolve(), ROOT/'scripts/sparse_opening_research.py',
             ROOT/'scripts/volume-priority-requirements.txt', LOCK,
             ROOT/'src/auto_invest/analytics/volume_priority_research.py',
             ROOT/'src/auto_invest/analytics/sparse_opening_research.py',
             ROOT/'src/auto_invest/analytics/observed_intraday_inputs.py',
             ROOT/'specs/206-volume-priority-research/contracts/preregistration.json',
             PARENT/'preregistration.json', PARENT/'source-inventory.json']
    return {str(p.relative_to(ROOT)): fingerprint(p)[0] for p in paths}


def arithmetic_verifier():
    path = ROOT/'scripts/sparse_opening_research.py'
    spec = importlib.util.spec_from_file_location('research_194_arithmetic', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_ledger


def verify_evidence(directory, index_sha256):
    from auto_invest.analytics.sparse_opening_research import INVENTORY_SHA256
    from auto_invest.analytics.volume_priority_research import read_contract

    contract = read_contract()
    result = json_value(bounded(directory/'result.json', JSON_LIMIT))
    require(result['contract_sha256'] == identity()
            and result['parent_contract_sha256'] == contract['parent_contract_sha256']
            and result['manifest_sha256'] == contract['input_manifest_sha256']
            and result['inventory_sha256'] == INVENTORY_SHA256
            and result['index_sha256'] == index_sha256
            and result['code_sha256'] == code_identity()
            and result['family_id'] == contract['family_id'] and result['candidate_count'] == 1
            and result['minimum_prior_trials'] == 35 and result['minimum_total_trials'] == 36
            and result['holdout_read'] is False)
    require(fingerprint(directory/'input-manifest.json')[0] == result['manifest_sha256'])
    require(set(result['scenarios']) == set(result['ledger_sha256']) == {'base', 'stress'})
    ledger = arithmetic_verifier()
    for name, cost in [('base', .0031), ('stress', .004)]:
        path = directory/f'{name}.jsonl'
        require(fingerprint(path)[0] == result['ledger_sha256'][name])
        ledger(path, result['scenarios'][name], cost)
    passed = result['scenarios']['base']['closed_roundtrips'] >= 200 and all(
        row['net_profit'] is not None and row['net_profit'] > 0 and row['unclosed_quantity'] == 0
        for row in result['scenarios'].values())
    require(result['status'] == ('INDEPENDENT_VALIDATION_REQUIRED' if passed
                                 else 'DEVELOPMENT_REJECTED'))
    require(result['live_eligible'] is False and result['promotion_allowed'] is False
            and result['orders_submitted'] == 0 and result['actual_capital_fraction'] == 0)
    return dict(verified=True, status=result['status'], live_eligible=False, orders_submitted=0)


def replay(fixture, output):
    if output.exists() or output.is_symlink():
        raise FileExistsError('existing research output')
    from auto_invest.analytics.sparse_opening_research import INVENTORY_SHA256, research_inputs
    from auto_invest.analytics.volume_priority_research import replay_volume_priority

    code = code_identity()
    with (plaintext_inputs(fixture) as manifest,
          research_inputs(manifest, PARENT) as inputs):
        output.mkdir(parents=True, exist_ok=False)
        write_new(output/'input-manifest.json', bounded(manifest, JSON_LIMIT))
        with ExitStack() as stack:
            files = {name: stack.enter_context((output/f'{name}.jsonl').open('x'))
                     for name in ('base', 'stress')}
            sinks = {name: (lambda event, handle=handle:
                     handle.write(json.dumps(event, sort_keys=True, allow_nan=False)+'\n'))
                     for name, handle in files.items()}
            result = replay_volume_priority(inputs, sinks)
        require(code == code_identity())
        index_sha = fingerprint(fixture/'index.json', JSON_LIMIT)[0]
        result.update(inventory_sha256=INVENTORY_SHA256, index_sha256=index_sha,
                      code_sha256=code, ledger_sha256={
                          name: fingerprint(output/f'{name}.jsonl')[0] for name in files})
        write_new(output/'result.json', encoded(result))
    verified = verify_evidence(output, index_sha)
    write_new(output/'COMPLETE.json', encoded(dict(
        result_sha256=fingerprint(output/'result.json')[0], **verified)))
    return verified


def verify(fixture, evidence):
    fixture_identity(fixture)
    checked = verify_evidence(evidence, fingerprint(fixture/'index.json', JSON_LIMIT)[0])
    require(json_value(bounded(evidence/'COMPLETE.json', JSON_LIMIT)) == dict(
        result_sha256=fingerprint(evidence/'result.json')[0], **checked))
    # A self-sealed ledger is insufficient: rerun all prices and compare exact evidence.
    with tempfile.TemporaryDirectory(prefix='research-206-recompute-') as folder:
        repeated = Path(folder).resolve()/'evidence'
        replay(fixture, repeated)
        for name in ('input-manifest.json', 'base.jsonl', 'stress.jsonl', 'result.json'):
            require(fingerprint(repeated/name) == fingerprint(evidence/name))
    return dict(**checked, recomputed=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('stage')
    prepare.add_argument('--manifest', type=Path, required=True)
    prepare.add_argument('--output', type=Path, required=True)
    run = commands.add_parser('replay')
    run.add_argument('--fixture', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('--fixture', type=Path, required=True)
    check.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'stage':
            result = stage(args.manifest, args.output)
        elif args.command == 'replay':
            result = replay(args.fixture, args.output)
        else:
            result = verify(args.fixture, args.evidence)
    except (OSError, ValueError, KeyError, TypeError, StopIteration, IndexError,
            OverflowError, EOFError, ImportError):
        print(json.dumps(dict(error='RESEARCH_INPUT_OR_EVIDENCE_REJECTED')))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
