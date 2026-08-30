"""Consumer-recomputed strategy-factory evidence contract."""

from __future__ import annotations

import random
from copy import deepcopy
from decimal import Decimal

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probability_of_backtest_overfitting,
)
from auto_invest.analytics.research_family_audit import (
    annotate_research_families,
    build_research_family_audit,
)
from auto_invest.portfolio.factory_evidence import assess_factory_evidence


def _prior_rows(prior_count: int) -> list[dict]:
    families: list[tuple[str, dict[str, str]]] = [
        *(('factory', {'batch_id': f'strategy-factory-{index}'}) for index in range(4)),
        *(('exploratory', {'exploration_batch_id': name}) for name in ('mild', 'price', 'strong')),
        ('credit-spread', {}),
        ('macro-cycle', {}),
        ('treasury-carry', {}),
        ('fx-carry', {}),
        ('commodity-carry', {}),
        ('commodity-positioning-signal', {}),
        ('commodity-supply-demand-signal', {}),
        ('usda-crop-signal', {}),
        ('energy-cross-signal', {}),
    ]
    rows = []
    for index in range(prior_count):
        prefix, extra = families[index % len(families)]
        rows.append(
            {
                "candidate_id": f"{prefix}-{index:03d}",
                "strategy_fingerprint": f"sha256:prior-{index:03d}",
                "status": "EXPLORATORY_REJECTED",
                **extra,
            }
        )
    return rows


def _calibration() -> dict:
    return {
        "gate_version": "2.0",
        "research_entry_gate_version": "3.1",
        "verdict": "CALIBRATED",
        "code_commit": "abc123",
        "scenario": {"seed": 60_000, "repetitions": 500},
        "thresholds": {
            "holdout_psr_min": 0.95,
            "paper_psr_min": 0.80,
            "research_entry_pbo_max": 0.25,
        },
        "required": {
            "family_false_acceptance_max": 0.01,
            "detection_min": 0.80,
            "program_false_acceptance_budget": 0.20,
            "maximum_research_families": 20,
        },
        "family_calibrations": {
            "16": {
                "research_entry_calibrated": True,
                "null_research_entry_acceptance_rate": 0.01,
                "target_research_entry_detection_rate": 0.84,
            },
            "64": {
                "research_entry_calibrated": True,
                "null_research_entry_acceptance_rate": 0.004,
                "target_research_entry_detection_rate": 0.804,
            },
        },
    }


def _v3_payload(*, candidate_count: int = 16, prior_count: int = 16) -> dict:
    prior = _prior_rows(prior_count)
    trials = [
        {
            "candidate_id": f"options-vrp-family-{index:03d}",
            "strategy_fingerprint": f"sha256:family-{index:03d}",
            "status": "complete",
        }
        for index in range(candidate_count)
    ]
    rng = random.Random(4)
    development_returns = []
    development_segments = []
    for row in trials:
        returns = [rng.gauss(0, 1) for _ in range(80)]
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
    winner_index = max(
        range(candidate_count),
        key=lambda index: annualized_sharpe(development_returns[index]),
    )
    winner = trials[winner_index]
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index],
        [annualized_sharpe(row) for row in development_returns],
        effective_trial_count=effective_trials,
    )
    assert dsr is not None
    audit_records = annotate_research_families(prior + deepcopy(trials))
    trials = audit_records[-candidate_count:]
    family_audit = build_research_family_audit(audit_records)
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
        "gate_version": "3.1",
        "code_commit": "abc123",
        "candidate_count": candidate_count,
        "complete_trial_count": candidate_count,
        "prior_trial_count": prior_count,
        "global_audit_trial_count": global_count,
        "unique_trial_fingerprint_count": global_count,
        "program_research_family_count": len(family_audit),
        "research_family_audit": family_audit,
        "trial_records": trials,
        "audit_records": audit_records,
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
        "development_selection": {"selected_candidate_id": winner["candidate_id"]},
        "repository_gate_calibration": _calibration(),
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


def test_v31_complete_family_is_eligible_after_consumer_recalculation() -> None:
    result = assess_factory_evidence(_v3_payload())

    assert result.eligible is True
    assert result.contract_version == "calibrated-family-entry-v3.1"
    assert result.candidate_count == 16
    assert result.global_audit_trial_count == 32
    assert result.reasons == ()
    assert result.program_multiplicity["method"] == "calibrated-family-risk-budget-v1"
    assert result.program_multiplicity["research_family_count"] == 17
    assert result.program_multiplicity["dsr_diagnostic"]["blocking"] is False
    assert result.program_multiplicity["dsr_diagnostic"]["passed"] is False


def test_v31_complete_family_can_have_more_than_sixteen_candidates() -> None:
    result = assess_factory_evidence(_v3_payload(candidate_count=20))

    assert result.eligible is True
    assert result.candidate_count == 20


def test_v31_recomputes_784_rows_and_19_families_but_live_parity_still_blocks() -> None:
    payload = _v3_payload(prior_count=768)
    for index, row in enumerate(payload["audit_records"][:16]):
        row.pop("batch_id", None)
        row.pop("exploration_batch_id", None)
        prefix = "regime-joint-weakness" if index < 8 else "calendar-turn-restored"
        row["candidate_id"] = f"{prefix}-{index:03d}"
        row["strategy_fingerprint"] = f"sha256:{prefix}-{index:03d}"
    payload["audit_records"] = annotate_research_families(payload["audit_records"])
    payload["research_family_audit"] = build_research_family_audit(payload["audit_records"])
    payload["program_research_family_count"] = 19
    payload["decision"]["selected_deploy_config"] = None
    payload["decision"]["research_canary_eligible"] = False
    payload["research_live_parity"]["passed"] = False

    result = assess_factory_evidence(payload)

    assert result.global_audit_trial_count == 784
    assert result.program_multiplicity["research_family_count"] == 19
    assert result.program_multiplicity["program_false_acceptance_bound"] == "0.19"
    assert result.eligible is False
    assert "research_live_parity" in result.reasons
    assert "selected_output_complete" in result.reasons


def test_v31_rejects_partial_or_missing_raw_rows() -> None:
    partial = _v3_payload()
    partial["complete_trial_count"] = 15
    missing = _v3_payload()
    missing.pop("audit_records")

    partial_result = assess_factory_evidence(partial)
    missing_result = assess_factory_evidence(missing)

    assert "all_candidates_complete" in partial_result.reasons
    assert "audit_rows_present" in missing_result.reasons


def test_v31_rejects_duplicate_identity_and_wrong_family_tail() -> None:
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


def test_v31_rejects_producer_gate_count_claim_that_disagrees_with_rows() -> None:
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


def test_v31_rejects_missing_selected_output_or_selected_record() -> None:
    missing_config = _v3_payload()
    missing_config["decision"]["selected_deploy_config"] = None
    wrong_record = _v3_payload()
    wrong_record["decision"]["selected_candidate_id"] = "not-in-family"

    assert "selected_output_complete" in assess_factory_evidence(missing_config).reasons
    assert "selected_record_match" in assess_factory_evidence(wrong_record).reasons


def test_v31_rejects_reused_non_vintage_or_execution_mismatched_data() -> None:
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


def test_v31_retains_raw_bonferroni_as_nonblocking_diagnostic() -> None:
    payload = _v3_payload(prior_count=736)
    payload["decision"]["psr"] = "0.96"
    selected_id = payload["decision"]["selected_candidate_id"]
    next(row for row in payload["trial_records"] if row["candidate_id"] == selected_id)[
        "holdout_psr"
    ] = "0.96"
    next(row for row in payload["audit_records"] if row["candidate_id"] == selected_id)[
        "holdout_psr"
    ] = "0.96"

    result = assess_factory_evidence(payload)

    assert result.global_audit_trial_count == 752
    assert result.eligible is True
    diagnostic = result.program_multiplicity["raw_bonferroni_diagnostic"]
    assert diagnostic["blocking"] is False
    assert Decimal(diagnostic["adjusted_p"]) == Decimal("1")
    assert Decimal(diagnostic["required_psr"]) > Decimal("0.9999")


def test_v31_rejects_claimed_statistics_that_disagree_with_raw_inputs() -> None:
    payload = _v3_payload()
    payload["decision"]["dsr"] = "0.94"
    payload["decision"]["pbo"] = "0.21"
    payload["decision"]["gates"][-1]["passed"] = False

    result = assess_factory_evidence(payload)

    assert "family_dsr_recomputed" in result.reasons
    assert "family_pbo_recomputed" in result.reasons
    assert "all_blocking_gates_pass" in result.reasons


def test_v31_reports_weak_dsr_but_only_high_pbo_blocks() -> None:
    weak = _v3_payload()
    rng = random.Random(0)
    high_pbo_segments = [[rng.gauss(0, 1) for _ in range(8)] for _ in range(16)]
    high_pbo = probability_of_backtest_overfitting(high_pbo_segments)
    assert high_pbo is not None
    weak["development_segment_sharpes"] = high_pbo_segments
    weak["decision"]["pbo"] = str(high_pbo)

    result = assess_factory_evidence(weak)

    assert "family_dsr" not in result.reasons
    assert "family_pbo" in result.reasons
    assert result.program_multiplicity["dsr_diagnostic"]["blocking"] is False


def test_v31_rejects_family_ledger_or_calibration_mutation() -> None:
    family_mutation = _v3_payload()
    family_mutation["audit_records"][0]["research_family_id"] = "wrong"
    calibration_mutation = _v3_payload()
    calibration_mutation["repository_gate_calibration"]["family_calibrations"]["64"][
        "target_research_entry_detection_rate"
    ] = 0.79

    assert "research_family_ids_recomputed" in assess_factory_evidence(
        family_mutation
    ).reasons
    assert "repository_calibration" in assess_factory_evidence(calibration_mutation).reasons


def test_v31_blocks_the_twenty_first_research_family_before_results() -> None:
    payload = _v3_payload()
    extra = [
        {
            "candidate_id": f"factory-extra-{index}",
            "strategy_fingerprint": f"sha256:extra-{index}",
            "status": "EXPLORATORY_REJECTED",
            "batch_id": f"strategy-factory-extra-{index}",
        }
        for index in range(4)
    ]
    audit = annotate_research_families(
        payload["audit_records"][:-16] + extra + payload["audit_records"][-16:]
    )
    payload["prior_trial_count"] = 20
    payload["global_audit_trial_count"] = 36
    payload["unique_trial_fingerprint_count"] = 36
    payload["audit_records"] = audit
    payload["trial_records"] = audit[-16:]
    payload["research_family_audit"] = build_research_family_audit(audit)
    payload["program_research_family_count"] = 21
    for gate in payload["decision"]["gates"]:
        if gate["gate_id"] == "prior_audit_complete":
            gate["actual"] = gate["required"] = "20"
        elif gate["gate_id"] in {"global_audit_trials", "unique_audit_fingerprints"}:
            gate["actual"] = gate["required"] = "36"

    result = assess_factory_evidence(payload)

    assert result.program_multiplicity["program_false_acceptance_bound"] == "0.21"
    assert "program_research_budget" in result.reasons


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
    assert result.program_multiplicity["recomputed_pbo"] is not None


def test_v3_v2_and_legacy_contracts_are_diagnostic_only() -> None:
    v3 = _v3_payload()
    v3["gate_version"] = "3.0"
    v2 = _v3_payload()
    v2["gate_version"] = "2.0"
    legacy = _v3_payload()
    legacy.pop("gate_version")

    v3_result = assess_factory_evidence(v3)
    v2_result = assess_factory_evidence(v2)
    legacy_result = assess_factory_evidence(legacy)

    assert v3_result.contract_version == "family-complete-v3-diagnostic"
    assert v2_result.contract_version == "family-complete-v2-diagnostic"
    assert legacy_result.contract_version == "legacy-64-diagnostic"
    assert v3_result.reasons == ("calibrated_family_entry_v31_required",)
    assert v2_result.reasons == ("calibrated_family_entry_v31_required",)
    assert legacy_result.reasons == ("calibrated_family_entry_v31_required",)


def test_non_mapping_input_fails_closed() -> None:
    result = assess_factory_evidence(None)

    assert result.eligible is False
    assert result.reasons == ("evidence_mapping",)
