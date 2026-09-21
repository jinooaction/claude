import json
import subprocess
import sys
from pathlib import Path


def test_cli_empty_input_and_output_preservation(tmp_path):
    script = Path(__file__).resolve().parents[2]/'scripts/earnings_event_inputs.py'
    input_path = tmp_path/'input.json'
    input_path.write_text(json.dumps({'schema_version': 1, 'issuers': ['0000789019'],
                                     'documents': [], 'events': []}))
    result = subprocess.run([sys.executable, str(script), 'import', '--input', str(input_path),
                             '--output', str(tmp_path/'bundle')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    command = [sys.executable, str(script), 'query', '--bundle', str(tmp_path/'bundle'),
               '--as-of', '2014-01-01T00:00:00Z', '--output', str(tmp_path/'query.json')]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    raw = (tmp_path/'query.json').read_bytes()
    assert json.loads(raw)['events'] == []
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert (tmp_path/'query.json').read_bytes() == raw
