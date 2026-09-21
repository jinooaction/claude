import hashlib
import json
import runpy
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from auto_invest.analytics.observed_intraday_inputs import Minute, ObservedSeries, Source
from auto_invest.analytics.sparse_opening_research import (
    CONTRACT_SHA256,
    INVENTORY_SHA256,
    ResearchAccount,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/sparse_opening_research.py'


def cli(*arguments):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, arguments)],
                          cwd=ROOT, capture_output=True, text=True, timeout=30)


def result_fixture(directory):
    source = Source('TEST', '0'*64, 'synthetic', 'none', 'unverified')
    day = date(2014, 3, 3)
    empty = ObservedSeries(source, day, day, [])
    lo, _ = empty.bounds(day)
    data = ObservedSeries(source, day, day, [Minute(lo, 10, 11, 9, 10, 200),
                                           Minute(lo+timedelta(minutes=1), 11, 12, 10, 11, 200)])
    result = {'schema_version': 1, 'scenarios': {}, 'ledger_sha256': {},
              'contract_sha256': CONTRACT_SHA256, 'inventory_sha256': INVENTORY_SHA256,
              'status': 'DEVELOPMENT_REJECTED', 'live_eligible': False,
              'promotion_allowed': False, 'orders_submitted': 0, 'actual_capital_fraction': 0}
    for name, cost in [('base', 31), ('stress', 40)]:
        account = ResearchAccount(cost)
        account.reserve('TEST', lo, 10, 9)
        account.observe_entry('TEST', data, lo+timedelta(minutes=1))
        account.request_exit('TEST', lo+timedelta(minutes=1))
        account.observe_exit('TEST', data, lo+timedelta(minutes=1), lo+timedelta(minutes=2))
        raw = ''.join(json.dumps(event)+'\n' for event in account.events).encode()
        (directory/f'{name}.jsonl').write_bytes(raw)
        result['ledger_sha256'][name] = hashlib.sha256(raw).hexdigest()
        result['scenarios'][name] = account.summary()
    manifest = b'{"synthetic_verifier_test": true}'
    (directory/'input-manifest.json').write_bytes(manifest)
    result['manifest_sha256'] = hashlib.sha256(manifest).hexdigest()
    (directory/'result.json').write_text(json.dumps(result))
    return result


def test_cli_independent_verification_preserves_artifacts(tmp_path):
    result_fixture(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = cli('verify', '--result', tmp_path)
    assert result.returncode == 0, result.stdout+result.stderr
    assert json.loads(result.stdout)['verified'] is True
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('change', ['hash', 'cash', 'proceeds', 'promotion', 'contract', 'due'])
def test_cli_rejects_tampering_even_when_ledger_is_rehashed(tmp_path, change):
    result = result_fixture(tmp_path)
    if change in ('hash', 'proceeds', 'due'):
        path = tmp_path/'base.jsonl'
        events = [json.loads(line) for line in path.read_text().splitlines()]
        if change == 'due':
            events[-1]['due'] = '2014-03-06T14:30:00+00:00'
        else:
            events[-1]['proceeds'] += 1
        path.write_text(''.join(json.dumps(e)+'\n' for e in events))
        if change in ('proceeds', 'due'):
            result['ledger_sha256']['base'] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif change == 'cash':
        result['scenarios']['base']['cash'] += 1
    elif change == 'promotion':
        result['promotion_allowed'] = True
    else:
        result['contract_sha256'] = '0'*64
    (tmp_path/'result.json').write_text(json.dumps(result))
    check = cli('verify', '--result', tmp_path)
    assert check.returncode == 2 and 'error' in json.loads(check.stdout)
    assert not check.stderr


def test_cli_invalid_manifest_reports_no_private_path(tmp_path):
    path = tmp_path/'private-account-name.json'
    path.write_text('{}')
    result = cli('replay', '--manifest', path, '--output', tmp_path/'output')
    assert result.returncode == 2
    assert str(path) not in result.stdout+result.stderr
    assert not (tmp_path/'output').exists()


def test_replay_existing_output_is_refused_after_input_check(tmp_path, monkeypatch):
    from contextlib import contextmanager

    import auto_invest.analytics.sparse_opening_research as engine

    manifest = tmp_path/'input.json'
    manifest.write_text('{}')

    @contextmanager
    def inputs(*args):
        yield {'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}

    monkeypatch.setattr(engine, 'research_inputs', inputs)
    script = runpy.run_path(str(SCRIPT))
    with pytest.raises(FileExistsError):
        script['replay'](manifest, tmp_path)
    assert manifest.read_text() == '{}'


def test_replay_refuses_success_if_code_changes_during_execution(tmp_path, monkeypatch):
    from contextlib import contextmanager

    import auto_invest.analytics.sparse_opening_research as engine

    manifest = tmp_path/'input.json'
    manifest.write_text('{}')

    @contextmanager
    def inputs(*args):
        yield {'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}

    monkeypatch.setattr(engine, 'research_inputs', inputs)
    monkeypatch.setattr(engine, 'replay_research', lambda *args: {})
    script = runpy.run_path(str(SCRIPT))
    calls = []
    original = script['fingerprint']

    def changing_fingerprint(path):
        if path == SCRIPT:
            calls.append(path)
            return ('0' if len(calls) == 1 else '1')*64
        return original(path)

    monkeypatch.setitem(script['replay'].__globals__, 'fingerprint', changing_fingerprint)
    with pytest.raises(ValueError):
        script['replay'](manifest, tmp_path/'output')
    assert not (tmp_path/'output/result.json').exists()
