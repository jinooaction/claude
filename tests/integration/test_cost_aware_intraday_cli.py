from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_existing_output_refused_before_any_input_read(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    output.mkdir()
    preserved = output / "result.json"
    preserved.write_text("original evidence")
    result = subprocess.run(
        [sys.executable, "scripts/cost_aware_intraday_probe.py", "develop",
         "--bars-dir", str(tmp_path / "missing"), "--manifest", str(tmp_path / "missing.json"),
         "--output-dir", str(output)],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert "already exists" in result.stderr
    assert preserved.read_text() == "original evidence"


def test_development_command_has_no_holdout_input() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/cost_aware_intraday_probe.py", "--help"],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    assert "--holdout" not in result.stdout
