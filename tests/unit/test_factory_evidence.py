"""Consumer-recomputed strategy-factory evidence contract."""

from __future__ import annotations

import math
import random
from copy import deepcopy
from decimal import Decimal

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probability_of_backtest_overfitting,
)
from auto_invest.portfolio.factory_evidence import assess_factory_evidence


def _v3_payload(*, candidate_count: int = 16, prior_count: int = 16) -> dict:
    prior = [
        {
            "candidate_id": f"prior-{index:03d}",
            "strategy_fingerprint": f"sha256:prior-{index:03d}",
            "status": "EXPLORATORY_REJECTED",
        }
        for index in range(prior_count)
    ]
    trials = [
        {
            "candidate_id": f"family-{index:03d}",
            "strategy_fingerprint": f"sha256:family-{index:03d}",
            "status": "complete",
        }
        for index in range(candidate_count)
    ]
    development_returns = []
    development_segments = []
    for index, row in enumerate(trials):
        mean = 0.005 if index == candidate_count - 1 else -0.001 + 0.00005 * index
        returns = [mean + 0.01 * math.sin(month * 1.7 + index) for month in range(80)]
        segments = [
            annualized_sharpe(returns[start : start + 10]) for start in range(0, 80, 10)
        ]
        row.update(
            {
                "holdout_psr": "0.999",
                "development_sharpe": annualized_sharpe(returns),
                "segment_sharpes": segments,
            }
        )
        development_returns.append(returns)
        development_segments.append(segments)
    effective_trials = effective_independent_trials(development_returns)
    dsr = deflated_sharpe_from_trials(
        development_returns[-1],
        [annualized_sharpe(row) for row in development_returns],
        effective_trial_count=effective_trials,
    )
    pbo = probability_of_backtest_overfitting(development_segments)
    assert dsr is not None and pbo is not None
    global_count = prior_count + candidate_count
    winner = trials[-1]
    gates = [
        {
            "gate_id": gate_id,
            "passed": True,
            "actual": str(actual),
            "required": str(actual),
            "blocking": True,
        }
        for gate_id, actual in (
            ("complete_family_trials", candidate_count),
            ("prior_audit_complete", prior_count),
            ("global_audit_trials", global_count),
            ("unique_audit_fingerprints", global_count),
        )
    ]
    gates.append(
        {
            "gate_id": "holdout_excess_psr",
            "passed": True,
            "actual": "0.999",
            "required": "0.95",
            "blocking": True,
        }
    )
    return {
        "schema_version": "1.0",
        "gate_version": "3.0",
        "candidate_count": candidate_count,
        "complete_trial_count": candidate_count,
        "prior_trial_count": prior_count,
        "global_audit_trial_count": global_count,
        "unique_trial_fingerprint_count": global_count,
        "trial_records": trials,
        "audit_records": prior + deepcopy(trials),
        "development_returns": development_returns,
        "development_segment_sharpes": development_segments,
        "criterion_audit": {
            "threshold_change_after_results": False,
            "prior_candidate_reclassification": False,
            "historical_reuse": False,
            "public_history_point_in_time": True,
            "benchmark_execution_parity": True,
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
            "selected_deploy_config": "[portfolio]\nid = 'family-winner'\n",
            "psr": "0.999",
            "dsr": str(dsr),
            "pbo": str(pbo),
            "gates": gates,
        },
    }


def test_v3_complete_family_is_eligible_after_consumer_recalculation() -> None:
    result = assess_factory_evidence(_v3_payload())

    assert result.eligible is True
    assert result.contract_version == "family-complete-v3"
    assert result.candidate_count == 16
    assert result.global_audit_trial_count == 32
    assert result.reasons == ()
    assert result.program_multiplicity["method"] == "bonferroni-global-fwer-v1"


def test_v3_complete_family_can_have_more_than_sixteen_candidates() -> None:
    result = assess_factory_evidence(_v3_payload(candidate_count=20))

    assert result.eligible is True
    assert result.candidate_count == 20


def test_v3_rejects_partial_or_missing_raw_rows() -> None:
    partial = _v3_payload()
    partial["complete_trial_count"] = 15
    missing = _v3_payload()
    missing.pop("audit_records")

    partial_result = assess_factory_evidence(partial)
    missing_result = assess_factory_evidence(missing)

    assert "all_candidates_complete" in partial_result.reasons
    assert "audit_rows_present" in missing_result.reasons


def test_v3_rejects_duplicate_identity_and_wrong_family_tail() -> None:
    duplicate = _v3_payload()
    duplicate["audit_records"][1]["candidate_id"] = duplicate["audit_records"][0][
        "candidate_id"
    ]
    duplicate["audit_records"][1]["strategy_fingerprint"] = duplicate[
        "audit_records"
    ][0]["strategy_fingerprint"]
    wrong_tail = _v3_payload()
    wrong_tail["trial_records"][0], wrong_tail["trial_records"][1] = (
        wrong_tail["trial_records"][1],
        wrong_tail["trial_records"][0],
    )

    duplicate_result = assess_factory_evidence(duplicate)
    tail_result = assess_factory_evidence(wrong_tail)

    assert "audit_candidate_ids_unique" in duplicate_result.reasons
    assert "audit_fingerprints_unique" in duplicate_result.reasons
    assert "current_family_is_audit_tail" in tail_result.reasons


def test_v3_rejects_producer_gate_count_claim_that_disagrees_with_rows() -> None:
    payload = _v3_payload()
    gate = next(
        row
        for row in payload["decision"]["gates"]
        if row["gate_id"] == "global_audit_trials"
    )
    gate["actual"] = "999"
    gate["required"] = "999"

    result = assess_factory_evidence(payload)

    assert result.eligible is False
    assert "audit_gate_counts_match" in result.reasons


def test_v3_rejects_missing_selected_output_or_selected_record() -> None:
    missing_config = _v3_payload()
    missing_config["decision"]["selected_deploy_config"] = None
    wrong_record = _v3_payload()
    wrong_record["decision"]["selected_candidate_id"] = "not-in-family"

    assert "selected_output_complete" in assess_factory_evidence(missing_config).reasons
    assert "selected_record_match" in assess_factory_evidence(wrong_record).reasons


def test_v3_rejects_reused_non_vintage_or_execution_mismatched_data() -> None:
    payload = _v3_payload()
    payload["criterion_audit"].update(
        {
            "historical_reuse": True,
            "public_history_point_in_time": False,
            "benchmark_execution_parity": False,
        }
    )

    result = assess_factory_evidence(payload)

    assert "historical_data_not_reused" in result.reasons
    assert "point_in_time_data" in result.reasons
    assert "benchmark_execution_parity" in result.reasons


def test_v3_charges_all_trials_not_only_the_current_family() -> None:
    payload = _v3_payload(prior_count=736)
    payload["decision"]["psr"] = "0.96"

    result = assess_factory_evidence(payload)

    assert result.global_audit_trial_count == 752
    assert result.eligible is False
    assert "program_wide_multiplicity" in result.reasons
    assert Decimal(result.program_multiplicity["adjusted_p"]) == Decimal("1")
    assert Decimal(result.program_multiplicity["required_psr"]) > Decimal("0.9999")


def test_v3_rejects_claimed_statistics_that_disagree_with_raw_inputs() -> None:
    payload = _v3_payload()
    payload["decision"]["dsr"] = "0.94"
    payload["decision"]["pbo"] = "0.21"
    payload["decision"]["gates"][-1]["passed"] = False

    result = assess_factory_evidence(payload)

    assert "family_dsr_recomputed" in result.reasons
    assert "family_pbo_recomputed" in result.reasons
    assert "all_blocking_gates_pass" in result.reasons


def test_v3_rejects_recomputed_weak_dsr_and_high_pbo() -> None:
    weak = _v3_payload()
    selected = weak["development_returns"][-1]
    weak["development_returns"][-1] = [
        0.003 + 0.01 * math.sin(month * 1.7 + 15) for month in range(len(selected))
    ]
    effective_trials = effective_independent_trials(weak["development_returns"])
    weak_dsr = deflated_sharpe_from_trials(
        weak["development_returns"][-1],
        [annualized_sharpe(row) for row in weak["development_returns"]],
        effective_trial_count=effective_trials,
    )
    rng = random.Random(0)
    high_pbo_segments = [[rng.gauss(0, 1) for _ in range(8)] for _ in range(16)]
    high_pbo = probability_of_backtest_overfitting(high_pbo_segments)
    assert weak_dsr is not None and high_pbo is not None
    weak["development_segment_sharpes"] = high_pbo_segments
    weak["decision"]["dsr"] = str(weak_dsr)
    weak["decision"]["pbo"] = str(high_pbo)

    result = assess_factory_evidence(weak)

    assert "family_dsr" in result.reasons
    assert "family_pbo" in result.reasons


def test_current_no_edge_payload_remains_ineligible() -> None:
    payload = _v3_payload()
    payload["decision"].update(
        {
            "verdict": "NO_FACTORY_EDGE",
            "research_canary_eligible": False,
            "selected_candidate_id": None,
            "selected_strategy_fingerprint": None,
            "selected_deploy_config": None,
            "psr": None,
            "dsr": None,
            "pbo": None,
        }
    )

    result = assess_factory_evidence(payload)

    assert result.eligible is False
    assert "factory_edge" in result.reasons
    assert "research_canary_eligible" in result.reasons


def test_v2_and_legacy_contracts_are_diagnostic_only() -> None:
    v2 = _v3_payload()
    v2["gate_version"] = "2.0"
    legacy = _v3_payload()
    legacy.pop("gate_version")

    v2_result = assess_factory_evidence(v2)
    legacy_result = assess_factory_evidence(legacy)

    assert v2_result.contract_version == "family-complete-v2-diagnostic"
    assert legacy_result.contract_version == "legacy-64-diagnostic"
    assert v2_result.reasons == ("family_complete_v3_required",)
    assert legacy_result.reasons == ("family_complete_v3_required",)


def test_non_mapping_input_fails_closed() -> None:
    result = assess_factory_evidence(None)

    assert result.eligible is False
    assert result.reasons == ("evidence_mapping",)
