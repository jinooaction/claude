"""CLI probe for the shared factory-evidence contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scripts" / "factory_evidence_gate.py"

_spec = importlib.util.spec_from_file_location("factory_evidence_gate", PROBE)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)


def _payload() -> dict:
    return {
        "gate_version": "2.0",
        "candidate_count": 16,
        "complete_trial_count": 16,
        "global_audit_trial_count": 704,
        "unique_trial_fingerprint_count": 704,
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_candidate_id": "winner",
            "selected_strategy_fingerprint": "sha256:winner",
            "selected_deploy_config": "[portfolio]\nid='winner'\n",
            "gates": [
                {
                    "gate_id": "complete_family_trials",
                    "passed": True,
                    "actual": "16",
                    "required": "16",
                },
                {
                    "gate_id": "prior_audit_complete",
                    "passed": True,
                    "actual": "688",
                    "required": "688",
                },
                {
                    "gate_id": "global_audit_trials",
                    "passed": True,
                    "actual": "704",
                    "required": "704",
                },
                {
                    "gate_id": "unique_audit_fingerprints",
                    "passed": True,
                    "actual": "704",
                    "required": "704",
                },
                {
                    "gate_id": "holdout_excess_psr",
                    "passed": True,
                    "actual": "0.96",
                    "required": "0.95",
                },
            ],
        },
    }


def test_probe_exits_zero_and_writes_assessment_for_complete_v2(tmp_path: Path) -> None:
    evidence = tmp_path / "factory.json"
    output = tmp_path / "assessment.json"
    evidence.write_text(json.dumps(_payload()), encoding="utf-8")

    assert _probe.main(["--evidence", str(evidence), "--json-out", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["eligible"] is True
    assert result["contract_version"] == "family-complete-v2"


def test_probe_exits_three_for_ineligible_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "factory.json"
    payload = _payload()
    payload["decision"]["verdict"] = "NO_FACTORY_EDGE"
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    assert _probe.main(["--evidence", str(evidence)]) == 3


def test_probe_exits_two_for_unreadable_input(tmp_path: Path) -> None:
    assert _probe.main(["--evidence", str(tmp_path / "missing.json")]) == 2
