import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from auto_invest.analytics.observed_intraday_inputs import audit_manifest


def fixture(tmp_path, rows=''):
    data = ('timestamp_utc,symbol,open,high,low,close,volume\n'+rows).encode()
    (tmp_path/'TEST.csv').write_bytes(data)
    manifest = {'schema_version': 1, 'symbols': ['TEST'], 'start': '2024-03-08',
                'end': '2024-03-11', 'calendar': 'XNYS', 'files': {'TEST': {
                    'path': 'TEST.csv', 'sha256': hashlib.sha256(data).hexdigest(),
                    'provider': 'synthetic', 'adjustment': 'none',
                    'issuer_lineage_status': 'unverified'}}}
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest))
    return path


def test_empty_symbol_stays_in_report(tmp_path):
    report = audit_manifest(fixture(tmp_path))
    file = report['files'][0]
    assert file['expected_sessions'] == 2
    assert file['missing_minutes'] == 780 and file['observed_minutes'] == 0
    assert not report['strategy_admitted'] and not report['live_eligible']
    assert file['issuer_lineage_status'] == 'unverified'


@pytest.mark.parametrize('change', ['hash', 'symbol', 'provider', 'schema', 'calendar'])
def test_invalid_manifest_rejected(tmp_path, change):
    path = fixture(tmp_path)
    doc = json.loads(path.read_text())
    if change == 'hash':
        doc['files']['TEST']['sha256'] = '0'*64
    elif change == 'symbol':
        doc['symbols'].append('MISSING')
    elif change == 'provider':
        doc['files']['TEST']['provider'] = ''
    elif change == 'schema':
        doc['schema_version'] = True
    else:
        doc['calendar'] = '24/7'
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        audit_manifest(path)


def test_cli_preserves_existing_output_and_rejects_tampering(tmp_path):
    path = fixture(tmp_path, '2024-03-08T14:30:00Z,TEST,100,101,99,100,10\n')
    output = tmp_path/'report.json'
    script = Path(__file__).resolve().parents[2]/'scripts/observed_intraday_probe.py'
    cmd = [sys.executable, str(script), '--manifest', str(path), '--output', str(output)]
    assert subprocess.run(cmd, capture_output=True).returncode == 0
    original = output.read_bytes()
    assert subprocess.run(cmd, capture_output=True).returncode == 2
    assert output.read_bytes() == original
    (tmp_path/'TEST.csv').write_text('tampered')
    output2 = tmp_path/'rejected.json'
    assert subprocess.run(cmd[:-1]+[str(output2)], capture_output=True).returncode == 2
    assert not output2.exists()
