from __future__ import annotations

import json
import subprocess
import sys


def test_calibration_probe_writes_promotable_machine_evidence(tmp_path) -> None:
    output = tmp_path / "calibration.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/edge_gate_calibration_probe.py",
            "--seed",
            "60000",
            "--repetitions",
            "500",
            "--timestamp-utc",
            "2026-08-23T00:00:00Z",
            "--code-commit",
            "abc123",
            "--json-out",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["verdict"] == "CALIBRATED"
    assert payload["revised"]["false_acceptance_rate"] <= 0.05
    assert payload["revised"]["detection_rate"] >= 0.80
    assert payload["family_calibrations"]["16"]["live_calibrated"] is True
    assert payload["family_calibrations"]["64"]["live_calibrated"] is True
    assert payload["family_calibrations"]["16"]["research_entry_calibrated"] is True
    assert payload["family_calibrations"]["64"]["research_entry_calibrated"] is True
