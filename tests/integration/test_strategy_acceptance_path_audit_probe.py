from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_acceptance_path_probe_writes_machine_and_human_evidence(tmp_path: Path) -> None:
    edge = tmp_path / "edge.json"
    edge.write_text(
        json.dumps(
            {
                "verdict": "CALIBRATED",
                "family_calibrations": {
                    "16": {
                        "null_research_entry_acceptance_rate": 0.01,
                        "target_research_entry_detection_rate": 0.84,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    forward = tmp_path / "forward.json"
    forward.write_text(
        json.dumps(
            {
                "verdict": "UNDERPOWERED",
                "scenario": {"observations": 48, "planted_active_sharpe_annual": 1.5},
                "required": {"minimum_detection_rate": 0.8},
                "planted_edge": {
                    "paired_active_return": {
                        "paper_acceptance_rate": 0.424,
                        "live_acceptance_rate": 0.1545,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "audit.json"
    markdown = tmp_path / "LAST_RUN.md"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/strategy_acceptance_path_audit_probe.py",
            "--regime-result",
            "specs/171-parallel-regime-edge-challenger/production-result.json",
            "--edge-calibration",
            str(edge),
            "--forward-calibration",
            str(forward),
            "--json-out",
            str(output),
            "--markdown-out",
            str(markdown),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["calibration_coverage"]["status"] == (
        "PARTIAL_COVERAGE"
    )
    assert "7/8" in markdown.read_text(encoding="utf-8")
