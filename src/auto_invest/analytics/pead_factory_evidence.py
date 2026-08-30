"""Independent fail-closed consumer for diagnostic PEAD research evidence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from auto_invest.analytics.research_family_audit import (
    build_research_family_audit,
    classify_research_family,
)

EXPECTED_FAMILY = "equity-post-earnings-announcement-drift"
EXPECTED_SAFETY = {
    "research_only": True,
    "research_canary_eligible": False,
    "promotion_allowed": False,
    "capital_allocation_fraction": 0.0,
    "orders_submitted": 0,
    "selected_deploy_config": None,
}
EXPECTED_CRITERION_VALIDITY = {
    "feasibility_preview_contaminated": True,
    "untouched_holdout": False,
    "point_in_time_constituents": False,
    "account_execution_parity": False,
}


@dataclass(frozen=True)
class PeadEvidenceAssessment:
    valid: bool
    verdict: str | None
    historical_published_edge: bool
    capital_eligible: bool
    recomputed_trial_count: int
    recomputed_family_count: int
    recomputed_family_size_counts: dict[str, int]
    recomputed_conservative_upper_bound: float | None
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _reason(reasons: list[str], value: str) -> None:
    if value not in reasons:
        reasons.append(value)


def assess_pead_evidence(evidence: object) -> PeadEvidenceAssessment:
    reasons: list[str] = []
    verdict: str | None = None
    trial_count = 0
    family_count = 0
    family_size_counts: dict[str, int] = {}
    conservative_bound: float | None = None
    if not isinstance(evidence, Mapping):
        return PeadEvidenceAssessment(
            False,
            None,
            False,
            False,
            0,
            0,
            {},
            None,
            ("root_not_object",),
        )

    raw_verdict = evidence.get("verdict")
    if isinstance(raw_verdict, str):
        verdict = raw_verdict
    if (
        evidence.get("schema_version") != "1.0"
        or evidence.get("gate_version") != "3.2"
        or evidence.get("family_id") != EXPECTED_FAMILY
    ):
        _reason(reasons, "identity_contract_mismatch")
    if verdict not in {"PUBLISHED_EDGE", "PAPER_CHALLENGER", "NO_FACTORY_EDGE"}:
        _reason(reasons, "verdict_invalid")

    audit = evidence.get("audit_records")
    family_rows: list[dict[str, Any]] = []
    pead_rows: list[Mapping[str, object]] = []
    candidate_ids: list[str] = []
    fingerprints: list[str] = []
    if not isinstance(audit, list):
        _reason(reasons, "audit_records_missing")
    else:
        trial_count = len(audit)
        try:
            for row in audit:
                if not isinstance(row, Mapping):
                    raise ValueError("row")
                candidate_id = row.get("candidate_id")
                fingerprint = row.get("strategy_fingerprint")
                if (
                    not isinstance(candidate_id, str)
                    or not isinstance(fingerprint, str)
                    or row.get("status") not in {"complete", "EXPLORATORY_REJECTED"}
                ):
                    raise ValueError("identity")
                candidate_ids.append(candidate_id)
                fingerprints.append(fingerprint)
                if classify_research_family(row) == EXPECTED_FAMILY:
                    pead_rows.append(row)
            family_rows = build_research_family_audit(audit)
        except (TypeError, ValueError):
            _reason(reasons, "audit_reconstruction_failed")
    if trial_count != 816:
        _reason(reasons, "trial_count_mismatch")
    if len(set(candidate_ids)) != 816:
        _reason(reasons, "candidate_id_uniqueness_failed")
    if len(set(fingerprints)) != 816:
        _reason(reasons, "strategy_fingerprint_uniqueness_failed")
    family_count = len(family_rows)
    sizes = Counter(int(row["candidate_count"]) for row in family_rows)
    family_size_counts = {str(key): sizes[key] for key in sorted(sizes)}
    if family_count != 21:
        _reason(reasons, "family_count_mismatch")
    if family_size_counts != {"16": 11, "64": 10}:
        _reason(reasons, "family_size_mix_mismatch")
    if len(pead_rows) != 16:
        _reason(reasons, "pead_family_count_mismatch")

    registry = evidence.get("candidate_registry")
    trials = evidence.get("trial_records")
    try:
        registry_identities = {
            (str(row["candidate_id"]), str(row["strategy_fingerprint"]))
            for row in registry
            if isinstance(row, Mapping)
        }
        trial_identities = {
            (str(row["candidate_id"]), str(row["strategy_fingerprint"]))
            for row in trials
            if isinstance(row, Mapping)
        }
        pead_identities = {
            (str(row["candidate_id"]), str(row["strategy_fingerprint"])) for row in pead_rows
        }
        if (
            not isinstance(registry, list)
            or not isinstance(trials, list)
            or len(registry) != 16
            or len(trials) != 16
            or registry_identities != pead_identities
            or trial_identities != pead_identities
        ):
            _reason(reasons, "pead_registry_identity_mismatch")
    except (KeyError, TypeError):
        _reason(reasons, "pead_registry_identity_mismatch")

    producer_audit = evidence.get("global_audit")
    if not isinstance(producer_audit, Mapping):
        _reason(reasons, "producer_global_audit_missing")
    elif (
        producer_audit.get("trial_count") != trial_count
        or producer_audit.get("unique_candidate_id_count") != len(set(candidate_ids))
        or producer_audit.get("unique_strategy_fingerprint_count") != len(set(fingerprints))
        or producer_audit.get("family_count") != family_count
        or producer_audit.get("family_size_counts") != family_size_counts
    ):
        _reason(reasons, "producer_global_audit_mismatch")

    calibration = evidence.get("program_calibration")
    expected_caps = {"16": 0.01, "64": 0.009}
    expected_mix = {"16": 11, "64": 10}
    if not isinstance(calibration, Mapping):
        _reason(reasons, "program_calibration_missing")
    else:
        caps = calibration.get("family_caps")
        mix = calibration.get("family_mix")
        if not isinstance(caps, Mapping) or not isinstance(mix, Mapping):
            _reason(reasons, "program_calibration_shape_invalid")
        else:
            try:
                conservative_bound = round(
                    sum(float(caps[size]) * family_size_counts.get(size, 0) for size in caps),
                    6,
                )
            except (KeyError, TypeError, ValueError):
                _reason(reasons, "program_bound_recalculation_failed")
        if (
            calibration.get("gate_version") != "3.2"
            or calibration.get("method") != "family-size-bonferroni-v2"
            or calibration.get("family_caps") != expected_caps
            or calibration.get("family_mix") != expected_mix
            or calibration.get("calibrated") is not True
            or calibration.get("capital_entry_eligible") is not False
            or calibration.get("false_acceptance_budget") != 0.2
            or calibration.get("conservative_upper_bound") != 0.2
            or conservative_bound != 0.2
        ):
            _reason(reasons, "program_calibration_contract_mismatch")

    if evidence.get("criterion_validity") != EXPECTED_CRITERION_VALIDITY:
        _reason(reasons, "criterion_validity_mismatch")
    if evidence.get("safety") != EXPECTED_SAFETY:
        _reason(reasons, "safety_contract_mismatch")
    if evidence.get("promotion_allowed") is not False:
        _reason(reasons, "top_level_promotion_not_blocked")
    forward = evidence.get("forward_observation")
    if (
        not isinstance(forward, Mapping)
        or forward.get("observed_earnings_events") != 0
        or forward.get("observed_calendar_months") != 0
        or forward.get("eligible_for_next_review") is not False
    ):
        _reason(reasons, "forward_observation_not_empty")

    decision = evidence.get("decision")
    if not isinstance(decision, Mapping):
        _reason(reasons, "decision_missing")
    else:
        if (
            decision.get("verdict") != verdict
            or decision.get("research_canary_eligible") is not False
            or decision.get("promotion_allowed") is not False
            or decision.get("selected_deploy_config") is not None
            or decision.get("threshold_change_after_results") is not False
        ):
            _reason(reasons, "decision_safety_mismatch")
        selected_trials = [row for row in pead_rows if row.get("selected_by_development") is True]
        if len(selected_trials) != 1:
            _reason(reasons, "development_winner_count_mismatch")
        else:
            winner = selected_trials[0]
            if decision.get("provisional_best_candidate_id") != winner.get("candidate_id"):
                _reason(reasons, "development_winner_identity_mismatch")
            if verdict == "PUBLISHED_EDGE":
                if (
                    decision.get("historical_edge_passed") is not True
                    or decision.get("selected_candidate_id") != winner.get("candidate_id")
                    or decision.get("selected_strategy_fingerprint")
                    != winner.get("strategy_fingerprint")
                ):
                    _reason(reasons, "published_edge_selection_mismatch")
            elif (
                decision.get("historical_edge_passed") is not False
                or decision.get("selected_candidate_id") is not None
                or decision.get("selected_strategy_fingerprint") is not None
            ):
                _reason(reasons, "non_published_selection_mismatch")

    valid = not reasons
    return PeadEvidenceAssessment(
        valid=valid,
        verdict=verdict,
        historical_published_edge=valid and verdict == "PUBLISHED_EDGE",
        capital_eligible=False,
        recomputed_trial_count=trial_count,
        recomputed_family_count=family_count,
        recomputed_family_size_counts=family_size_counts,
        recomputed_conservative_upper_bound=conservative_bound,
        reasons=tuple(reasons),
    )


__all__ = ["PeadEvidenceAssessment", "assess_pead_evidence"]
