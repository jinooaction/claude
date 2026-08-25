"""Fail-closed completeness contract for strategy-factory evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

MIN_V2_CANDIDATES = 16
REQUIRED_V2_AUDIT_GATES = (
    "complete_family_trials",
    "prior_audit_complete",
    "global_audit_trials",
    "unique_audit_fingerprints",
)


@dataclass(frozen=True)
class FactoryEvidenceAssessment:
    """Pure factory-contract result consumed by every capital entry path."""

    eligible: bool
    contract_version: str
    candidate_count: int | None
    complete_trial_count: int | None
    selected_candidate_id: str | None
    selected_strategy_fingerprint: str | None
    checks: dict[str, bool]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 and str(parsed) == value.strip() else None
    return None


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _gate_rows(decision: Mapping[str, object]) -> list[Mapping[str, object]] | None:
    gates = decision.get("gates")
    if not isinstance(gates, Sequence) or isinstance(gates, (str, bytes)):
        return None
    if not gates or not all(isinstance(gate, Mapping) for gate in gates):
        return None
    return list(gates)


def _assessment(
    *,
    contract_version: str,
    candidate_count: int | None,
    complete_trial_count: int | None,
    selected_candidate_id: str | None,
    selected_strategy_fingerprint: str | None,
    checks: dict[str, bool],
) -> FactoryEvidenceAssessment:
    reasons = tuple(name for name, passed in checks.items() if not passed)
    return FactoryEvidenceAssessment(
        eligible=not reasons,
        contract_version=contract_version,
        candidate_count=candidate_count,
        complete_trial_count=complete_trial_count,
        selected_candidate_id=selected_candidate_id,
        selected_strategy_fingerprint=selected_strategy_fingerprint,
        checks=checks,
        reasons=reasons,
    )


def _assess_v2(
    evidence: Mapping[str, object],
    decision: Mapping[str, object],
    *,
    candidate_count: int | None,
    complete_trial_count: int | None,
    selected_candidate_id: str | None,
    selected_strategy_fingerprint: str | None,
    selected_deploy_config: str | None,
) -> FactoryEvidenceAssessment:
    gates = _gate_rows(decision)
    gate_by_id = {
        str(gate.get("gate_id")): gate
        for gate in gates or ()
        if _nonempty_string(gate.get("gate_id"))
    }
    required_gates = [gate_by_id.get(gate_id) for gate_id in REQUIRED_V2_AUDIT_GATES]

    parsed_required_counts: dict[str, int] = {}
    audit_gate_counts_match = all(gate is not None for gate in required_gates)
    if audit_gate_counts_match:
        for gate_id, gate in zip(REQUIRED_V2_AUDIT_GATES, required_gates, strict=True):
            assert gate is not None
            actual = _nonnegative_int(gate.get("actual"))
            required = _nonnegative_int(gate.get("required"))
            if actual is None or required is None or actual != required:
                audit_gate_counts_match = False
                break
            parsed_required_counts[gate_id] = actual

    global_count = _nonnegative_int(evidence.get("global_audit_trial_count"))
    unique_count = _nonnegative_int(evidence.get("unique_trial_fingerprint_count"))
    if audit_gate_counts_match:
        audit_gate_counts_match = bool(
            candidate_count is not None
            and global_count is not None
            and unique_count is not None
            and parsed_required_counts["complete_family_trials"] == candidate_count
            and parsed_required_counts["prior_audit_complete"] + candidate_count == global_count
            and parsed_required_counts["global_audit_trials"] == global_count
            and parsed_required_counts["unique_audit_fingerprints"] == unique_count
        )

    checks = {
        "candidate_count_minimum": bool(
            candidate_count is not None and candidate_count >= MIN_V2_CANDIDATES
        ),
        "all_candidates_complete": bool(
            candidate_count is not None
            and complete_trial_count is not None
            and complete_trial_count == candidate_count
        ),
        "factory_edge": decision.get("verdict") == "FACTORY_EDGE",
        "research_canary_eligible": decision.get("research_canary_eligible") is True,
        "gate_rows_present": gates is not None,
        "required_audit_gates": bool(
            required_gates
            and all(gate is not None and gate.get("passed") is True for gate in required_gates)
        ),
        "audit_gate_counts_match": audit_gate_counts_match,
        "all_blocking_gates_pass": bool(
            gates is not None
            and all(gate.get("blocking") is False or gate.get("passed") is True for gate in gates)
        ),
        "global_audit_unique": bool(
            global_count is not None
            and global_count > 0
            and unique_count is not None
            and unique_count == global_count
        ),
        "selected_output_complete": all(
            (
                selected_candidate_id,
                selected_strategy_fingerprint,
                selected_deploy_config,
            )
        ),
    }
    return _assessment(
        contract_version="family-complete-v2",
        candidate_count=candidate_count,
        complete_trial_count=complete_trial_count,
        selected_candidate_id=selected_candidate_id,
        selected_strategy_fingerprint=selected_strategy_fingerprint,
        checks=checks,
    )


def _assess_legacy(
    decision: Mapping[str, object],
    *,
    candidate_count: int | None,
    complete_trial_count: int | None,
    selected_candidate_id: str | None,
    selected_strategy_fingerprint: str | None,
    selected_deploy_config: str | None,
) -> FactoryEvidenceAssessment:
    gates = _gate_rows(decision)
    checks = {
        "legacy_64_complete": candidate_count == 64 and complete_trial_count == 64,
        "factory_edge": decision.get("verdict") == "FACTORY_EDGE",
        "research_canary_eligible": decision.get("research_canary_eligible") is True,
        "all_gate_rows_pass": bool(
            gates is not None and all(gate.get("passed") is True for gate in gates)
        ),
        "selected_output_complete": all(
            (
                selected_candidate_id,
                selected_strategy_fingerprint,
                selected_deploy_config,
            )
        ),
    }
    return _assessment(
        contract_version="legacy-64",
        candidate_count=candidate_count,
        complete_trial_count=complete_trial_count,
        selected_candidate_id=selected_candidate_id,
        selected_strategy_fingerprint=selected_strategy_fingerprint,
        checks=checks,
    )


def assess_factory_evidence(evidence: object) -> FactoryEvidenceAssessment:
    """Validate factory completeness without freshness or live-state assumptions."""

    if not isinstance(evidence, Mapping):
        return _assessment(
            contract_version="unknown",
            candidate_count=None,
            complete_trial_count=None,
            selected_candidate_id=None,
            selected_strategy_fingerprint=None,
            checks={"evidence_mapping": False},
        )

    candidate_count = _nonnegative_int(evidence.get("candidate_count"))
    complete_trial_count = _nonnegative_int(evidence.get("complete_trial_count"))
    decision_value = evidence.get("decision")
    decision: Mapping[str, object] = decision_value if isinstance(decision_value, Mapping) else {}
    selected_candidate_id = _nonempty_string(decision.get("selected_candidate_id"))
    selected_strategy_fingerprint = _nonempty_string(decision.get("selected_strategy_fingerprint"))
    selected_deploy_config = _nonempty_string(decision.get("selected_deploy_config"))

    if evidence.get("gate_version") == "2.0":
        return _assess_v2(
            evidence,
            decision,
            candidate_count=candidate_count,
            complete_trial_count=complete_trial_count,
            selected_candidate_id=selected_candidate_id,
            selected_strategy_fingerprint=selected_strategy_fingerprint,
            selected_deploy_config=selected_deploy_config,
        )
    return _assess_legacy(
        decision,
        candidate_count=candidate_count,
        complete_trial_count=complete_trial_count,
        selected_candidate_id=selected_candidate_id,
        selected_strategy_fingerprint=selected_strategy_fingerprint,
        selected_deploy_config=selected_deploy_config,
    )
