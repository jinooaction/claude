"""CLI probe for the shared factory-evidence contract."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probability_of_backtest_overfitting,
)

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scripts" / "factory_evidence_gate.py"

_spec = importlib.util.spec_from_file_location("factory_evidence_gate", PROBE)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)


def _payload() -> dict:
    prior = [
        {
            "candidate_id": f"prior-{index}",
            "strategy_fingerprint": f"sha256:prior-{index}",
            "status": "EXPLORATORY_REJECTED",
        }
        for index in range(16)
    ]
    trials = [
        {
            "candidate_id": f"candidate-{index}",
            "strategy_fingerprint": f"sha256:candidate-{index}",
            "status": "complete",
        }
        for index in range(16)
    ]
    development_returns = []
    development_segments = []
    for index, row in enumerate(trials):
        mean = 0.005 if index == 15 else -0.001 + 0.00005 * index
        returns = [mean + 0.01 * math.sin(month * 1.7 + index) for month in range(80)]
        segments = [
            annualized_sharpe(returns[start : start + 10]) for start in range(0, 80, 10)
        ]
        row["holdout_psr"] = "0.999"
        development_returns.append(returns)
        development_segments.append(segments)
    dsr = deflated_sharpe_from_trials(
        development_returns[-1],
        [annualized_sharpe(row) for row in development_returns],
        effective_trial_count=effective_independent_trials(development_returns),
    )
    pbo = probability_of_backtest_overfitting(development_segments)
    assert dsr is not None and pbo is not None
    winner = trials[-1]
    return {
        "gate_version": "3.0",
        "candidate_count": 16,
        "complete_trial_count": 16,
        "prior_trial_count": 16,
        "global_audit_trial_count": 32,
        "unique_trial_fingerprint_count": 32,
        "audit_records": prior + trials,
        "trial_records": trials,
        "development_returns": development_returns,
        "development_segment_sharpes": development_segments,
        "criterion_audit": {
            "historical_reuse": False,
            "public_history_point_in_time": True,
            "benchmark_execution_parity": True,
            "threshold_change_after_results": False,
            "prior_candidate_reclassification": False,
        },
        "research_live_parity": {
            "passed": True,
            "candidate_id": winner["candidate_id"],
            "strategy_fingerprint": winner["strategy_fingerprint"],
        },
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_candidate_id": winner["candidate_id"],
            "selected_strategy_fingerprint": winner["strategy_fingerprint"],
            "selected_deploy_config": "[portfolio]\nid='winner'\n",
            "psr": "0.999",
            "dsr": str(dsr),
            "pbo": str(pbo),
            "gates": [
                {
                    "gate_id": gate_id,
                    "passed": True,
                    "actual": str(actual),
                    "required": str(actual),
                    "blocking": True,
                }
                for gate_id, actual in (
                    ("complete_family_trials", 16),
                    ("prior_audit_complete", 16),
                    ("global_audit_trials", 32),
                    ("unique_audit_fingerprints", 32),
                )
            ],
        },
    }


def test_probe_exits_zero_and_writes_assessment_for_complete_v3(tmp_path: Path) -> None:
    evidence = tmp_path / "factory.json"
    output = tmp_path / "assessment.json"
    evidence.write_text(json.dumps(_payload()), encoding="utf-8")

    assert _probe.main(["--evidence", str(evidence), "--json-out", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["eligible"] is True
    assert result["contract_version"] == "family-complete-v3"
    assert result["program_multiplicity"]["method"] == "bonferroni-global-fwer-v1"


def test_probe_exits_three_for_v2_or_no_edge_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "factory.json"
    payload = _payload()
    payload["gate_version"] = "2.0"
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    assert _probe.main(["--evidence", str(evidence)]) == 3

    payload["gate_version"] = "3.0"
    payload["decision"]["verdict"] = "NO_FACTORY_EDGE"
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    assert _probe.main(["--evidence", str(evidence)]) == 3


def test_probe_exits_two_for_unreadable_input(tmp_path: Path) -> None:
    assert _probe.main(["--evidence", str(tmp_path / "missing.json")]) == 2
