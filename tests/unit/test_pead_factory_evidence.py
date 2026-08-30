from __future__ import annotations

from copy import deepcopy

from auto_invest.analytics.pead_factory_evidence import assess_pead_evidence


def _payload(verdict: str = "PUBLISHED_EDGE") -> dict[str, object]:
    rows = []
    for family in range(20):
        count = 16 if family < 10 else 64
        for index in range(count):
            rows.append(
                {
                    "candidate_id": f"prior-{family:02d}-{index:03d}",
                    "strategy_fingerprint": f"sha256:prior-{family:02d}-{index:03d}",
                    "status": "complete",
                    "batch_id": f"prior-family-{family:02d}",
                }
            )
    pead_rows = []
    for index in range(16):
        pead_rows.append(
            {
                "candidate_id": f"pead-{index:02d}",
                "strategy_fingerprint": f"sha256:pead-{index:02d}",
                "status": "complete",
                "selected_by_development": index == 3,
            }
        )
    rows.extend(pead_rows)
    selected = "pead-03" if verdict == "PUBLISHED_EDGE" else None
    selected_fingerprint = "sha256:pead-03" if selected is not None else None
    return {
        "schema_version": "1.0",
        "gate_version": "3.2",
        "family_id": "equity-post-earnings-announcement-drift",
        "verdict": verdict,
        "candidate_count": 16,
        "candidate_registry": [
            {
                "candidate_id": row["candidate_id"],
                "strategy_fingerprint": row["strategy_fingerprint"],
            }
            for row in pead_rows
        ],
        "trial_records": pead_rows,
        "audit_records": rows,
        "global_audit": {
            "trial_count": 816,
            "unique_candidate_id_count": 816,
            "unique_strategy_fingerprint_count": 816,
            "family_count": 21,
            "family_size_counts": {"16": 11, "64": 10},
        },
        "program_calibration": {
            "gate_version": "3.2",
            "method": "family-size-bonferroni-v2",
            "family_caps": {"16": 0.01, "64": 0.009},
            "family_mix": {"16": 11, "64": 10},
            "conservative_upper_bound": 0.2,
            "false_acceptance_budget": 0.2,
            "calibrated": True,
            "capital_entry_eligible": False,
        },
        "criterion_validity": {
            "feasibility_preview_contaminated": True,
            "untouched_holdout": False,
            "point_in_time_constituents": False,
            "account_execution_parity": False,
        },
        "forward_observation": {
            "observed_earnings_events": 0,
            "observed_calendar_months": 0,
            "eligible_for_next_review": False,
        },
        "decision": {
            "verdict": verdict,
            "historical_edge_passed": verdict == "PUBLISHED_EDGE",
            "provisional_best_candidate_id": "pead-03",
            "selected_candidate_id": selected,
            "selected_strategy_fingerprint": selected_fingerprint,
            "selected_deploy_config": None,
            "research_canary_eligible": False,
            "promotion_allowed": False,
            "threshold_change_after_results": False,
        },
        "promotion_allowed": False,
        "safety": {
            "research_only": True,
            "research_canary_eligible": False,
            "promotion_allowed": False,
            "capital_allocation_fraction": 0.0,
            "orders_submitted": 0,
            "selected_deploy_config": None,
        },
    }


def test_independent_consumer_reconstructs_all_identities_families_and_budget() -> None:
    assessment = assess_pead_evidence(_payload())
    assert assessment.valid is True
    assert assessment.verdict == "PUBLISHED_EDGE"
    assert assessment.historical_published_edge is True
    assert assessment.capital_eligible is False
    assert assessment.recomputed_trial_count == 816
    assert assessment.recomputed_family_count == 21
    assert assessment.recomputed_family_size_counts == {"16": 11, "64": 10}
    assert assessment.recomputed_conservative_upper_bound == 0.2
    assert assessment.reasons == ()


def test_non_published_verdict_can_be_valid_but_never_capital_eligible() -> None:
    assessment = assess_pead_evidence(_payload("PAPER_CHALLENGER"))
    assert assessment.valid is True
    assert assessment.historical_published_edge is False
    assert assessment.capital_eligible is False


def test_consumer_rejects_identity_family_budget_and_money_path_tampering() -> None:
    mutations = []
    duplicate = deepcopy(_payload())
    duplicate["audit_records"][-1]["strategy_fingerprint"] = duplicate["audit_records"][0][
        "strategy_fingerprint"
    ]
    mutations.append(duplicate)
    family = deepcopy(_payload())
    family["audit_records"][-1]["candidate_id"] = "unknown-family-candidate"
    mutations.append(family)
    budget = deepcopy(_payload())
    budget["program_calibration"]["family_caps"]["64"] = 0.01
    mutations.append(budget)
    order = deepcopy(_payload())
    order["safety"]["orders_submitted"] = 1
    mutations.append(order)
    deploy = deepcopy(_payload())
    deploy["decision"]["selected_deploy_config"] = {"strategy": "pead"}
    mutations.append(deploy)
    for payload in mutations:
        assessment = assess_pead_evidence(payload)
        assert assessment.valid is False
        assert assessment.capital_eligible is False
        assert assessment.reasons

