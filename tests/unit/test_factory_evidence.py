"""Versioned strategy-factory evidence completeness contract."""

from __future__ import annotations

from copy import deepcopy

from auto_invest.portfolio.factory_evidence import assess_factory_evidence


def _v2_payload(*, candidate_count: int = 16) -> dict:
    global_count = 704
    return {
        "schema_version": "1.0",
        "gate_version": "2.0",
        "candidate_count": candidate_count,
        "complete_trial_count": candidate_count,
        "global_audit_trial_count": global_count,
        "unique_trial_fingerprint_count": global_count,
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_candidate_id": "candidate-v2",
            "selected_strategy_fingerprint": "sha256:strategy",
            "selected_deploy_config": "[portfolio]\nid = 'candidate-v2'\n",
            "gates": [
                {
                    "gate_id": "complete_family_trials",
                    "passed": True,
                    "actual": str(candidate_count),
                    "required": str(candidate_count),
                    "blocking": True,
                },
                {
                    "gate_id": "prior_audit_complete",
                    "passed": True,
                    "actual": str(global_count - candidate_count),
                    "required": str(global_count - candidate_count),
                    "blocking": True,
                },
                {
                    "gate_id": "global_audit_trials",
                    "passed": True,
                    "actual": str(global_count),
                    "required": str(global_count),
                    "blocking": True,
                },
                {
                    "gate_id": "unique_audit_fingerprints",
                    "passed": True,
                    "actual": str(global_count),
                    "required": str(global_count),
                    "blocking": True,
                },
                {
                    "gate_id": "development_dsr_diagnostic",
                    "passed": False,
                    "actual": "0.50",
                    "required": "0.95",
                    "blocking": False,
                },
                {
                    "gate_id": "holdout_excess_psr",
                    "passed": True,
                    "actual": "0.96",
                    "required": "0.95",
                    "blocking": True,
                },
            ],
        },
    }


def _legacy_payload() -> dict:
    return {
        "candidate_count": 64,
        "complete_trial_count": 64,
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_candidate_id": "legacy",
            "selected_strategy_fingerprint": "sha256:legacy",
            "selected_deploy_config": "[portfolio]\nid = 'legacy'\n",
            "gates": [{"gate_id": "complete_trials", "passed": True}],
        },
    }


def test_v2_complete_sixteen_candidate_family_is_eligible() -> None:
    result = assess_factory_evidence(_v2_payload())

    assert result.eligible is True
    assert result.contract_version == "family-complete-v2"
    assert result.candidate_count == 16
    assert result.reasons == ()


def test_v2_complete_family_can_have_more_than_sixteen_candidates() -> None:
    result = assess_factory_evidence(_v2_payload(candidate_count=64))

    assert result.eligible is True
    assert result.candidate_count == 64


def test_v2_rejects_family_smaller_than_minimum() -> None:
    result = assess_factory_evidence(_v2_payload(candidate_count=15))

    assert result.eligible is False
    assert "candidate_count_minimum" in result.reasons


def test_v2_rejects_partial_family() -> None:
    payload = _v2_payload()
    payload["complete_trial_count"] = 15

    result = assess_factory_evidence(payload)

    assert result.eligible is False
    assert "all_candidates_complete" in result.reasons


def test_v2_rejects_missing_required_audit_gate() -> None:
    payload = _v2_payload()
    payload["decision"]["gates"] = [
        gate
        for gate in payload["decision"]["gates"]
        if gate["gate_id"] != "prior_audit_complete"
    ]

    result = assess_factory_evidence(payload)

    assert result.eligible is False
    assert "required_audit_gates" in result.reasons


def test_v2_rejects_failed_blocking_gate_but_ignores_diagnostic_gate() -> None:
    payload = _v2_payload()
    blocking = next(
        gate
        for gate in payload["decision"]["gates"]
        if gate["gate_id"] == "holdout_excess_psr"
    )
    blocking["passed"] = False

    result = assess_factory_evidence(payload)

    assert result.eligible is False
    assert "all_blocking_gates_pass" in result.reasons


def test_v2_rejects_audit_count_mismatch() -> None:
    payload = _v2_payload()
    payload["unique_trial_fingerprint_count"] = 703

    result = assess_factory_evidence(payload)

    assert result.eligible is False
    assert "global_audit_unique" in result.reasons


def test_v2_rejects_producer_claim_without_selected_config() -> None:
    payload = _v2_payload()
    payload["decision"]["selected_deploy_config"] = None

    result = assess_factory_evidence(payload)

    assert result.eligible is False
    assert "selected_output_complete" in result.reasons


def test_current_no_edge_payload_remains_ineligible() -> None:
    payload = _v2_payload()
    payload["decision"]["verdict"] = "NO_FACTORY_EDGE"
    payload["decision"]["research_canary_eligible"] = False
    payload["decision"]["selected_candidate_id"] = None
    payload["decision"]["selected_strategy_fingerprint"] = None
    payload["decision"]["selected_deploy_config"] = None

    result = assess_factory_evidence(payload)

    assert result.eligible is False
    assert "factory_edge" in result.reasons
    assert "research_canary_eligible" in result.reasons


def test_legacy_contract_still_requires_exactly_sixty_four_complete_trials() -> None:
    assert assess_factory_evidence(_legacy_payload()).eligible is True

    partial = deepcopy(_legacy_payload())
    partial["candidate_count"] = 16
    partial["complete_trial_count"] = 16
    result = assess_factory_evidence(partial)
    assert result.eligible is False
    assert "legacy_64_complete" in result.reasons


def test_non_mapping_input_fails_closed() -> None:
    result = assess_factory_evidence(None)

    assert result.eligible is False
    assert result.reasons == ("evidence_mapping",)

