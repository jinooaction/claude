#!/usr/bin/env python3
"""Authenticate retained 207 inputs; emit only price-free observation diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import signal
import tempfile
from pathlib import Path

from auto_invest.market_data.intraday import SYMBOLS
from auto_invest.market_data.public_minute import SOURCES, PilotError, fingerprint, require
from auto_invest.market_data.public_minute_bridge import analyse

SPEC = importlib.util.spec_from_file_location('retained_pilot_207',
                                            Path(__file__).with_name('public_minute_pilot.py'))
assert SPEC and SPEC.loader
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)

INPUT_TAG = 'research-207-public-minute-fcfd9a6c3fe2209830aeaa7adf1725be62788d6f'
INPUT_RELEASE = 402595786
INPUT_ASSETS = (
    ('archive-index.json', 863,
     '561bfc715a698c13ee487ff56248461c9d1b26eadaa0a1b5bdbdae4e47c9a667'),
    ('archive-receipt.json', 1005,
     '5b3075c1d16184fcb81cbe46b124cf71cdfe2df41956e289bd8d011d26f20948'),
    ('claim.json', 161,
     '68a750a0e450a0475796058bd6ba8d164b1ea68892061bfe9b8c36268d403cef'),
    ('ohlcv_2014-01.parquet.aesgcm', 256575705,
     '1faf7a2f5327805bb480ecb4a4281238a914776097de5e2dcb11c89b5b64e188'),
    ('ohlcv_2019-12.parquet.aesgcm', 257874693,
     '23597ff3e13549dbbf8897b1edcc2afd5da8ea17893d2db3d8668df988630ec6'),
    ('report.json', 3229177,
     '3757ec115e39251019bc1d4c8c4f8a0dce7024dea876c6df4f7ddbaec1f028b7'),
)


def verify_inputs(directory: Path, assets: Path, *, expected=None) -> None:
    expected = INPUT_ASSETS if expected is None else expected
    require(directory.is_dir() and not directory.is_symlink()
            and {p.name for p in directory.iterdir()} == {x[0] for x in expected},
            'ARCHIVE_INVENTORY_REJECTED')
    require(assets.is_file() and not assets.is_symlink() and assets.stat().st_size <= 1024 * 1024,
            'REMOTE_METADATA_REJECTED')
    values = json.loads(assets.read_text())
    require(isinstance(values, list) and len(values) == len(expected), 'REMOTE_INVENTORY_REJECTED')
    by_name = {item['name']: item for item in values}
    require(len(by_name) == len(expected) and set(by_name) == {x[0] for x in expected},
            'REMOTE_INVENTORY_REJECTED')
    for name, size, sha in expected:
        item = by_name[name]
        require(item.get('size') == size and item.get('digest') == 'sha256:' + sha,
                'REMOTE_FINGERPRINT_REJECTED')
        require(fingerprint(directory / name) == (size, sha), 'INPUT_FINGERPRINT_REJECTED')


def crosscheck(result: dict, original: dict) -> None:
    require(result['calendar_sessions'] == original['calendar_sessions'], 'CALENDAR_MISMATCH')
    for symbol in SYMBOLS:
        old = original['runtime_universe_coverage'][symbol]
        require(result['regular_minutes_by_symbol'][symbol] == old['regular_rows']
                and result['missing_minutes_by_symbol'][symbol] == old['missing_regular_minutes']
                and len(result['minute_complete_sessions_by_symbol'][symbol])
                == old['complete_sessions'], 'ORIGINAL_COVERAGE_MISMATCH')


def run(archive: Path, assets: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema_version=1, input_tag=INPUT_TAG, input_release_id=INPUT_RELEASE,
                  source_authenticated=False, analysis_complete=False, months=[],
                  input_assets_verified=False, input_assets=[],
                  provider_eligible=False, strategy_eligible=False, promotion_eligible=False,
                  orders_submitted=0, returns_examined=False, prior_trials_minimum=36,
                  heldout_sessions_opened=0, outcome='INPUT_OR_ANALYSIS_FAILED',
                  limitations=['PROVENANCE_UNVERIFIED', 'ADJUSTMENTS_UNVERIFIED',
                               'POINT_IN_TIME_UNIVERSE_UNVERIFIED', 'LICENSE_UNDECLARED',
                               'TIMESTAMP_SEMANTICS_UNVERIFIED', 'PUBLISH_DELAY_MODELED',
                               'EXECUTION_PARITY_UNVERIFIED'])
    exit_code = 1
    try:
        verify_inputs(archive, assets)
        report['input_assets_verified'] = True
        report['input_assets'] = [{'name': name, 'size': size, 'sha256': sha}
                                  for name, size, sha in INPUT_ASSETS]
        pilot.verify_archive(archive, sources=SOURCES)
        report['source_authenticated'] = True
        original = json.loads((archive / 'report.json').read_text())
        index = json.loads((archive / 'archive-index.json').read_text())
        encryption = pilot.cipher()
        with tempfile.TemporaryDirectory(prefix='private-minute-bridge-') as temporary:
            for source, item, old in zip(SOURCES, index['files'], original['quality'], strict=True):
                data = encryption.decrypt(bytes.fromhex(item['nonce']),
                                          (archive / item['path']).read_bytes(), pilot.aad(source))
                require(len(data) == source.size and hashlib.sha256(data).hexdigest()
                        == source.sha256, 'RESTORED_SOURCE_MISMATCH')
                path = Path(temporary) / source.name
                with path.open('xb') as handle:
                    handle.write(data)
                del data
                result = analyse(path, source.month)
                crosscheck(result, old)
                report['months'].append(result)
                path.unlink()
        report['analysis_complete'] = True
        report['outcome'] = 'OBSERVATION_MODEL_DIAGNOSTIC_COMPLETE'
        exit_code = 0
    except Exception as exc:
        report['reason'] = str(exc) if isinstance(exc, PilotError) and re.fullmatch(
            '[A-Z_]{1,80}', str(exc)) else 'AUTHENTICATION_OR_ANALYSIS_FAILED'
    pilot.write_new(output / 'report.json', report)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def expired(*_):
        raise PilotError('DEADLINE_EXCEEDED')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(900)
    try:
        return run(args.archive, args.assets, args.output)
    except Exception:
        print('PUBLIC_MINUTE_BRIDGE_FAILED')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
