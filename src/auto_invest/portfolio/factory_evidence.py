"""Fail-closed, consumer-recomputed strategy-factory evidence contract."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probability_of_backtest_overfitting,
)

MIN_V3_CANDIDATES = 16
PROGRAM_FWER_MAX = Decimal("0.05")
MIN_DSR = Decimal("0.95")
MAX_PBO = Decimal("0.20")
COMPLETE_AUDIT_STATUSES = frozenset({"complete", "EXPLORATORY_REJECTED"})
REQUIRED_AUDIT_GATES = (
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
    global_audit_trial_count: int | None
    selected_candidate_id: str | None
    selected_strategy_fingerprint: str | None
    program_multiplicity: dict[str, Any]
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


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _rows(container: Mapping[str, object], key: str) -> list[Mapping[str, object]] | None:
    value = container.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if not value or not all(isinstance(row, Mapping) for row in value):
        return None
    return list(value)


def _gate_rows(decision: Mapping[str, object]) -> list[Mapping[str, object]] | None:
    return _rows(decision, "gates")


def _row_identity(row: Mapping[str, object]) -> tuple[str, str] | None:
    candidate_id = _nonempty_string(row.get("candidate_id"))
    fingerprint = _nonempty_string(row.get("strategy_fingerprint"))
    if candidate_id is None or fingerprint is None:
        return None
    return candidate_id, fingerprint


def _float_matrix(value: object, *, expected_rows: int | None) -> list[list[float]] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if expected_rows is None or len(value) != expected_rows:
        return None
    rows: list[list[float]] = []
    width: int | None = None
    for raw_row in value:
        if not isinstance(raw_row, Sequence) or isinstance(raw_row, (str, bytes)):
            return None
        try:
            row = [float(item) for item in raw_row]
        except (TypeError, ValueError):
            return None
        if len(row) < 2 or not all(math.isfinite(item) for item in row):
            return None
        if width is None:
            width = len(row)
        if len(row) != width:
            return None
        rows.append(row)
    return rows


def _assessment(
    *,
    contract_version: str,
    candidate_count: int | None,
    complete_trial_count: int | None,
    global_audit_trial_count: int | None,
    selected_candidate_id: str | None,
    selected_strategy_fingerprint: str | None,
    program_multiplicity: dict[str, Any] | None,
    checks: dict[str, bool],
) -> FactoryEvidenceAssessment:
    reasons = tuple(name for name, passed in checks.items() if not passed)
    return FactoryEvidenceAssessment(
        eligible=not reasons,
        contract_version=contract_version,
        candidate_count=candidate_count,
        complete_trial_count=complete_trial_count,
        global_audit_trial_count=global_audit_trial_count,
        selected_candidate_id=selected_candidate_id,
        selected_strategy_fingerprint=selected_strategy_fingerprint,
        program_multiplicity=program_multiplicity or {},
        checks=checks,
        reasons=reasons,
    )


def _assess_v3(
    evidence: Mapping[str, object],
    decision: Mapping[str, object],
    *,
    candidate_count: int | None,
    complete_trial_count: int | None,
    global_count: int | None,
    selected_candidate_id: str | None,
    selected_strategy_fingerprint: str | None,
    selected_deploy_config: str | None,
) -> FactoryEvidenceAssessment:
    gates = _gate_rows(decision)
    gate_by_id = {
        gate_id: gate
        for gate in gates or ()
        if (gate_id := _nonempty_string(gate.get("gate_id"))) is not None
    }
    required_gates = [gate_by_id.get(gate_id) for gate_id in REQUIRED_AUDIT_GATES]

    audit_rows = _rows(evidence, "audit_records")
    trial_rows = _rows(evidence, "trial_records")
    audit_identities = [_row_identity(row) for row in audit_rows or ()]
    trial_identities = [_row_identity(row) for row in trial_rows or ()]
    unique_count_claim = _nonnegative_int(evidence.get("unique_trial_fingerprint_count"))
    prior_count = _nonnegative_int(evidence.get("prior_trial_count"))

    audit_identity_complete = bool(audit_rows) and all(
        identity is not None for identity in audit_identities
    )
    trial_identity_complete = bool(trial_rows) and all(
        identity is not None for identity in trial_identities
    )
    audit_pairs = [identity for identity in audit_identities if identity is not None]
    trial_pairs = [identity for identity in trial_identities if identity is not None]
    audit_ids = [candidate_id for candidate_id, _ in audit_pairs]
    audit_fingerprints = [fingerprint for _, fingerprint in audit_pairs]
    trial_ids = [candidate_id for candidate_id, _ in trial_pairs]
    trial_fingerprints = [fingerprint for _, fingerprint in trial_pairs]

    selected_rows = [
        row
        for row in trial_rows or ()
        if row.get("candidate_id") == selected_candidate_id
        and row.get("strategy_fingerprint") == selected_strategy_fingerprint
    ]
    selected_index = next(
        (
            index
            for index, row in enumerate(trial_rows or ())
            if row.get("candidate_id") == selected_candidate_id
            and row.get("strategy_fingerprint") == selected_strategy_fingerprint
        ),
        None,
    )

    criterion = evidence.get("criterion_audit")
    criterion = criterion if isinstance(criterion, Mapping) else {}
    live_parity = evidence.get("research_live_parity")
    live_parity = live_parity if isinstance(live_parity, Mapping) else {}

    selected_psr = _decimal(decision.get("psr"))
    selected_record_psr = (
        _decimal(selected_rows[0].get("holdout_psr")) if len(selected_rows) == 1 else None
    )
    claimed_dsr = _decimal(decision.get("dsr"))
    claimed_pbo = _decimal(decision.get("pbo"))
    development_returns = _float_matrix(
        evidence.get("development_returns"), expected_rows=candidate_count
    )
    development_segments = _float_matrix(
        evidence.get("development_segment_sharpes"), expected_rows=candidate_count
    )
    recomputed_dsr: Decimal | None = None
    recomputed_pbo: Decimal | None = None
    if (
        development_returns is not None
        and development_segments is not None
        and selected_index is not None
    ):
        try:
            trial_sharpes = [annualized_sharpe(row) for row in development_returns]
            effective_trials = effective_independent_trials(development_returns)
            recomputed_dsr = deflated_sharpe_from_trials(
                development_returns[selected_index],
                trial_sharpes,
                effective_trial_count=effective_trials,
            )
            recomputed_pbo = probability_of_backtest_overfitting(development_segments)
        except (ArithmeticError, ValueError):
            recomputed_dsr = None
            recomputed_pbo = None
    raw_p = None if selected_psr is None else Decimal("1") - selected_psr
    adjusted_p = (
        None
        if raw_p is None or global_count is None
        else min(Decimal("1"), raw_p * Decimal(global_count))
    )
    required_psr = (
        None
        if global_count is None or global_count <= 0
        else Decimal("1") - PROGRAM_FWER_MAX / Decimal(global_count)
    )
    multiplicity = {
        "method": "bonferroni-global-fwer-v1",
        "selected_psr": None if selected_psr is None else str(selected_psr),
        "raw_one_sided_p": None if raw_p is None else str(raw_p),
        "global_trial_count": global_count,
        "adjusted_p": None if adjusted_p is None else str(adjusted_p),
        "threshold": str(PROGRAM_FWER_MAX),
        "required_psr": None if required_psr is None else str(required_psr),
        "recomputed_dsr": None if recomputed_dsr is None else str(recomputed_dsr),
        "recomputed_pbo": None if recomputed_pbo is None else str(recomputed_pbo),
        "claimed_dsr": None if claimed_dsr is None else str(claimed_dsr),
        "claimed_pbo": None if claimed_pbo is None else str(claimed_pbo),
    }
    expected_gate_counts = {
        "complete_family_trials": candidate_count,
        "prior_audit_complete": prior_count,
        "global_audit_trials": global_count,
        "unique_audit_fingerprints": global_count,
    }
    audit_gate_counts_match = all(
        gate is not None
        and _nonnegative_int(gate.get("actual")) == expected_gate_counts[gate_id]
        and _nonnegative_int(gate.get("required")) == expected_gate_counts[gate_id]
        for gate_id, gate in zip(REQUIRED_AUDIT_GATES, required_gates, strict=True)
    )

    checks = {
        "candidate_count_minimum": bool(
            candidate_count is not None and candidate_count >= MIN_V3_CANDIDATES
        ),
        "all_candidates_complete": bool(
            candidate_count is not None
            and complete_trial_count is not None
            and complete_trial_count == candidate_count
        ),
        "audit_rows_present": audit_rows is not None,
        "audit_count_recomputed": bool(
            audit_rows is not None
            and global_count is not None
            and len(audit_rows) == global_count
        ),
        "audit_rows_complete": bool(
            audit_rows is not None
            and all(row.get("status") in COMPLETE_AUDIT_STATUSES for row in audit_rows)
        ),
        "audit_identity_complete": audit_identity_complete,
        "audit_candidate_ids_unique": bool(
            audit_identity_complete and len(set(audit_ids)) == len(audit_ids)
        ),
        "audit_fingerprints_unique": bool(
            audit_identity_complete
            and len(set(audit_fingerprints)) == len(audit_fingerprints)
            and unique_count_claim == len(audit_fingerprints)
            and global_count == len(audit_fingerprints)
        ),
        "prior_count_recomputed": bool(
            prior_count is not None
            and candidate_count is not None
            and global_count is not None
            and prior_count + candidate_count == global_count
        ),
        "trial_rows_present": trial_rows is not None,
        "trial_count_recomputed": bool(
            trial_rows is not None
            and candidate_count is not None
            and len(trial_rows) == candidate_count
        ),
        "trial_rows_complete": bool(
            trial_rows is not None and all(row.get("status") == "complete" for row in trial_rows)
        ),
        "trial_identities_unique": bool(
            trial_identity_complete
            and len(set(trial_ids)) == len(trial_ids)
            and len(set(trial_fingerprints)) == len(trial_fingerprints)
        ),
        "current_family_is_audit_tail": bool(
            audit_rows is not None
            and trial_rows is not None
            and candidate_count is not None
            and len(audit_pairs) >= candidate_count
            and audit_pairs[-candidate_count:] == trial_pairs
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
        "selected_output_complete": all(
            (selected_candidate_id, selected_strategy_fingerprint, selected_deploy_config)
        ),
        "selected_record_match": len(selected_rows) == 1,
        "selected_psr_matches_record": bool(
            selected_psr is not None
            and selected_record_psr is not None
            and selected_psr == selected_record_psr
        ),
        "point_in_time_data": criterion.get("public_history_point_in_time") is True,
        "historical_data_not_reused": criterion.get("historical_reuse") is False,
        "benchmark_execution_parity": criterion.get("benchmark_execution_parity") is True,
        "thresholds_frozen_before_results": (
            criterion.get("threshold_change_after_results") is False
            and criterion.get("prior_candidate_reclassification") is False
        ),
        "research_live_parity": bool(
            live_parity.get("passed") is True
            and live_parity.get("candidate_id") == selected_candidate_id
            and live_parity.get("strategy_fingerprint") == selected_strategy_fingerprint
        ),
        "family_statistics_inputs": bool(
            development_returns is not None
            and development_segments is not None
            and development_segments
            and len(development_segments[0]) >= 4
            and len(development_segments[0]) % 2 == 0
        ),
        "family_dsr_recomputed": bool(
            recomputed_dsr is not None and claimed_dsr == recomputed_dsr
        ),
        "family_pbo_recomputed": bool(
            recomputed_pbo is not None and claimed_pbo == recomputed_pbo
        ),
        "standardized_statistics": bool(
            selected_psr is not None
            and Decimal("0") <= selected_psr <= Decimal("1")
            and recomputed_dsr is not None
            and Decimal("0") <= recomputed_dsr <= Decimal("1")
            and recomputed_pbo is not None
            and Decimal("0") <= recomputed_pbo <= Decimal("1")
        ),
        "family_dsr": bool(recomputed_dsr is not None and recomputed_dsr >= MIN_DSR),
        "family_pbo": bool(recomputed_pbo is not None and recomputed_pbo <= MAX_PBO),
        "program_wide_multiplicity": bool(
            adjusted_p is not None and Decimal("0") <= adjusted_p <= PROGRAM_FWER_MAX
        ),
    }
    return _assessment(
        contract_version="family-complete-v3",
        candidate_count=candidate_count,
        complete_trial_count=complete_trial_count,
        global_audit_trial_count=global_count,
        selected_candidate_id=selected_candidate_id,
        selected_strategy_fingerprint=selected_strategy_fingerprint,
        program_multiplicity=multiplicity,
        checks=checks,
    )


def _diagnostic_assessment(
    *,
    version: str,
    candidate_count: int | None,
    complete_trial_count: int | None,
    global_count: int | None,
    selected_candidate_id: str | None,
    selected_strategy_fingerprint: str | None,
) -> FactoryEvidenceAssessment:
    return _assessment(
        contract_version=version,
        candidate_count=candidate_count,
        complete_trial_count=complete_trial_count,
        global_audit_trial_count=global_count,
        selected_candidate_id=selected_candidate_id,
        selected_strategy_fingerprint=selected_strategy_fingerprint,
        program_multiplicity={},
        checks={"family_complete_v3_required": False},
    )


def assess_factory_evidence(evidence: object) -> FactoryEvidenceAssessment:
    """Validate factory evidence without freshness or live-state assumptions."""

    if not isinstance(evidence, Mapping):
        return _assessment(
            contract_version="unknown",
            candidate_count=None,
            complete_trial_count=None,
            global_audit_trial_count=None,
            selected_candidate_id=None,
            selected_strategy_fingerprint=None,
            program_multiplicity={},
            checks={"evidence_mapping": False},
        )

    candidate_count = _nonnegative_int(evidence.get("candidate_count"))
    complete_trial_count = _nonnegative_int(evidence.get("complete_trial_count"))
    global_count = _nonnegative_int(evidence.get("global_audit_trial_count"))
    decision_value = evidence.get("decision")
    decision: Mapping[str, object] = decision_value if isinstance(decision_value, Mapping) else {}
    selected_candidate_id = _nonempty_string(decision.get("selected_candidate_id"))
    selected_strategy_fingerprint = _nonempty_string(decision.get("selected_strategy_fingerprint"))
    selected_deploy_config = _nonempty_string(decision.get("selected_deploy_config"))

    if evidence.get("gate_version") == "3.0":
        return _assess_v3(
            evidence,
            decision,
            candidate_count=candidate_count,
            complete_trial_count=complete_trial_count,
            global_count=global_count,
            selected_candidate_id=selected_candidate_id,
            selected_strategy_fingerprint=selected_strategy_fingerprint,
            selected_deploy_config=selected_deploy_config,
        )
    version = (
        "family-complete-v2-diagnostic"
        if evidence.get("gate_version") == "2.0"
        else "legacy-64-diagnostic"
    )
    return _diagnostic_assessment(
        version=version,
        candidate_count=candidate_count,
        complete_trial_count=complete_trial_count,
        global_count=global_count,
        selected_candidate_id=selected_candidate_id,
        selected_strategy_fingerprint=selected_strategy_fingerprint,
    )
