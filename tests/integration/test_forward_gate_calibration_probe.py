from __future__ import annotations

import json
import subprocess
import sys


def test_forward_gate_calibration_probe_writes_no_order_evidence(tmp_path) -> None:
    output = tmp_path / "forward-gate-calibration.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/forward_gate_calibration_probe.py",
            "--seed",
            "159001",
            "--repetitions",
            "2000",
            "--code-commit",
            "abc123",
            "--json-out",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["verdict"] == "CALIBRATED"
    assert payload["significance_method"] == "paired_active_return_psr_v1"
    assert payload["code_commit"] == "abc123"
    assert "no orders" in payload["safety"]
