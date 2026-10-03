#!/usr/bin/env python3
"""Pinned anonymous development source acquisition and authenticated private archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
from pathlib import Path

from auto_invest.market_data.public_minute import (
    REPOSITORY,
    REVISION,
    SOURCES,
    PilotError,
    collect,
    diagnose,
    fingerprint,
    require,
)


def write_new(path: Path, data: dict) -> None:
    with path.open('x') as handle:
        json.dump(data, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')


def run_collect(raw: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'repository': REPOSITORY, 'revision': REVISION,
              'full_source_verified': False, 'quality_accepted': False,
              'archive_complete': False, 'strategy_eligible': False,
              'provider_eligible': False, 'orders_submitted': 0, 'returns_examined': False,
              'authentication_used': False, 'files': [], 'outcome': 'SOURCE_UNAVAILABLE',
              'limitations': ['UPLOADER_PROVENANCE_ONLY', 'ADJUSTMENTS_UNVERIFIED',
                              'POINT_IN_TIME_UNIVERSE_UNVERIFIED', 'LICENSE_UNDECLARED',
                              'EXECUTION_PARITY_UNVERIFIED']}
    exit_code = 1
    try:
        report['files'] = collect(raw)
        report['full_source_verified'] = True
        report['quality'] = [diagnose(raw / s.name, s.month) for s in SOURCES]
        report['quality_accepted'] = all(item['quality_accepted'] for item in report['quality'])
        report['outcome'] = ('SOURCE_QUALITY_ACCEPTED' if report['quality_accepted']
                             else 'SOURCE_QUALITY_REJECTED')
        # A rejected source remains an acquired raw source, never a qualified strategy.
        exit_code = 0
    except Exception as exc:
        report['reason'] = str(exc) if isinstance(exc, PilotError) and re.fullmatch(
            '[A-Z_]{1,80}', str(exc)) else 'COLLECTION_OR_DIAGNOSTIC_FAILED'
        if report['full_source_verified']:
            report['outcome'] = 'DIAGNOSTIC_INCOMPLETE'
    write_new(output / 'report.json', report)
    return exit_code


def cipher():
    value = os.environ.get('SPARSE_RESEARCH_INPUT_KEY', '')
    require(bool(re.fullmatch('[a-fA-F0-9]{64}', value)), 'ARCHIVE_KEY_UNAVAILABLE')
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(bytes.fromhex(value))


def aad(source) -> bytes:
    return f'public-minute-207|{REVISION}|{source.month}|{source.size}|{source.sha256}'.encode()


def pack(raw: Path, output: Path, *, sources=SOURCES) -> None:
    encryption = cipher()
    require(not output.exists(), 'ARCHIVE_EXISTS')
    for source in sources:
        require(fingerprint(raw / source.name) == (source.size, source.sha256),
                'SOURCE_FINGERPRINT_MISMATCH')
    output.mkdir(parents=True, exist_ok=False)
    index = {'schema_version': 1, 'revision': REVISION, 'files': []}
    for source in sources:
        nonce = os.urandom(12)
        sealed = encryption.encrypt(nonce, (raw / source.name).read_bytes(), aad(source))
        path = source.name + '.aesgcm'
        with (output / path).open('xb') as handle:
            handle.write(sealed)
        index['files'].append({'path': path, 'nonce': nonce.hex(), 'month': source.month,
                               'ciphertext_size': len(sealed),
                               'ciphertext_sha256': hashlib.sha256(sealed).hexdigest(),
                               'source_size': source.size, 'source_sha256': source.sha256})
    write_new(output / 'archive-index.json', index)
    verify_archive(output, sources=sources)


def verify_archive(output: Path, *, sources=SOURCES) -> int:
    encryption = cipher()
    path = output / 'archive-index.json'
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 * 1024,
            'ARCHIVE_INDEX_REJECTED')
    index = json.loads(path.read_text())
    require(set(index) == {'schema_version', 'revision', 'files'} and index['schema_version'] == 1
            and index['revision'] == REVISION and len(index['files']) == len(sources),
            'ARCHIVE_INDEX_REJECTED')
    nonces = set()
    for source, item in zip(sources, index['files'], strict=True):
        require(item['path'] == source.name + '.aesgcm' and item['month'] == source.month
                and item['source_size'] == source.size and item['source_sha256'] == source.sha256
                and re.fullmatch('[a-f0-9]{24}', item['nonce']) is not None
                and item['nonce'] not in nonces, 'ARCHIVE_INDEX_REJECTED')
        nonces.add(item['nonce'])
        path = output / item['path']
        require(item['ciphertext_size'] == source.size + 16
                and fingerprint(path) == (source.size + 16, item['ciphertext_sha256']),
                'ARCHIVE_FINGERPRINT_MISMATCH')
        try:
            data = encryption.decrypt(bytes.fromhex(item['nonce']), path.read_bytes(), aad(source))
        except Exception:
            raise PilotError('ARCHIVE_AUTHENTICATION_FAILED') from None
        require(len(data) == source.size and hashlib.sha256(data).hexdigest() == source.sha256,
                'ARCHIVE_SOURCE_MISMATCH')
    return len(sources)


def verify_assets(directory: Path, assets_path: Path, output: Path, *, sources=SOURCES) -> None:
    """Use GitHub's server-side SHA digest, never download or publish plaintext prices."""
    assets = json.loads(assets_path.read_text())
    require(isinstance(assets, list) and len(assets) <= 100, 'REMOTE_ASSETS_REJECTED')
    names = {item['name']: item for item in assets}
    expected_names = {'claim.json', 'report.json', 'archive-index.json'} | {
        s.name + '.aesgcm' for s in sources}
    require({p.name for p in directory.iterdir()} == expected_names
            and set(names) == expected_names and len(names) == len(assets),
            'REMOTE_ARCHIVE_INCOMPLETE')
    report = json.loads((directory / 'report.json').read_text())
    require(report.get('full_source_verified') is True
            and report.get('revision') == REVISION
            and report.get('files') == [{'month': s.month, 'size': s.size, 'sha256': s.sha256}
                                       for s in sources]
            and report.get('strategy_eligible') is False
            and report.get('provider_eligible') is False
            and report.get('returns_examined') is False and report.get('orders_submitted') == 0,
            'REMOTE_REPORT_REJECTED')
    verify_archive(directory, sources=sources)
    verified = []
    for path in sorted(directory.iterdir()):
        size, digest = fingerprint(path)
        item = names.get(path.name, {})
        require(item.get('size') == size and item.get('digest') == 'sha256:' + digest,
                'REMOTE_ARCHIVE_MISMATCH')
        verified.append({'name': path.name, 'size': size, 'sha256': digest})
    write_new(output, {'schema_version': 1, 'archive_complete': True,
                       'archive_authentication_verified': True, 'assets': verified,
                       'strategy_eligible': False, 'provider_eligible': False,
                       'returns_examined': False, 'orders_submitted': 0})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['collect', 'pack', 'verify-archive', 'verify-assets'])
    parser.add_argument('--raw', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'collect':
            def expired(*_args):
                raise PilotError('DEADLINE_EXCEEDED')
            signal.signal(signal.SIGALRM, expired)
            signal.alarm(900)
            require(args.raw is not None, 'RAW_DIRECTORY_REQUIRED')
            return run_collect(args.raw, args.output)
        if args.command == 'pack':
            require(args.raw is not None, 'RAW_DIRECTORY_REQUIRED')
            pack(args.raw, args.output)
        elif args.command == 'verify-archive':
            verify_archive(args.output)
        else:
            require(args.raw is not None and args.assets is not None, 'ASSET_INPUT_REQUIRED')
            verify_assets(args.raw, args.assets, args.output)
        return 0
    except Exception:
        print('PUBLIC_MINUTE_PILOT_FAILED')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
