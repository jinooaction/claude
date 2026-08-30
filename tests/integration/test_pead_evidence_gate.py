from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from runpy import run_path

_payload = run_path(
    str(Path(__file__).parents[1] / "unit" / "test_pead_factory_evidence.py")
)["_payload"]


def test_cli_accepts_integrity_without_claiming_capital_eligibility(tmp_path) -> None:
    evidence = tmp_path / "pead.json"
    evidence.write_text(json.dumps(_payload()), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/pead_evidence_gate.py", "--evidence", str(evidence)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assessment = json.loads(result.stdout)
    assert assessment["valid"] is True
    assert assessment["historical_published_edge"] is True
    assert assessment["capital_eligible"] is False


def test_cli_rejects_tampered_audit(tmp_path) -> None:
    payload = deepcopy(_payload())
    payload["global_audit"]["trial_count"] = 815
    evidence = tmp_path / "pead.json"
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/pead_evidence_gate.py", "--evidence", str(evidence)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 3
    assessment = json.loads(result.stdout)
    assert assessment["valid"] is False
    assert assessment["capital_eligible"] is False
