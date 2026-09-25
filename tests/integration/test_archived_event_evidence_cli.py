"""Exercise the actual process boundary using a linked synthetic archive."""

import json
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Reuse the fixture builder without depending on pytest collection order or
# treating the repository's non-package tests directory as an installed package.
linked_manifest = runpy.run_path(
    str(ROOT / "tests/unit/test_archived_event_evidence.py")
)["linked_manifest"]


def run_cli(source, output):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/archived_event_evidence.py"), "inspect",
         "--input", str(source), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def test_cli_success_and_overwrite_rejection(tmp_path):
    source = linked_manifest(tmp_path)
    output = tmp_path / "report.json"
    assert run_cli(source, output).returncode == 0
    original = output.read_bytes()
    result = json.loads(original)
    assert result["live_eligible"] is False
    assert run_cli(source, output).returncode == 2
    assert output.read_bytes() == original


def test_cli_failure_does_not_echo_source_or_publish_report(tmp_path):
    source = linked_manifest(tmp_path)
    source.write_text("PRIVATE SOURCE SHOULD NOT BE ECHOED")
    output = tmp_path / "report.json"
    result = run_cli(source, output)
    assert result.returncode == 2
    assert "PRIVATE SOURCE" not in result.stderr + result.stdout
    assert not output.exists()
