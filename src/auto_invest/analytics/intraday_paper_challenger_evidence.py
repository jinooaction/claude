"""Independent consumer for spec 177 diagnostic evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from auto_invest.analytics.intraday_paper_challenger import (
    EXPECTED_SAFETY,
    EXPECTED_UNIVERSE,
    FAMILY_ID,
    GATE_VERSION,
    SCHEMA_VERSION,
    VERDICTS,
    build_candidate_registry,
)


@dataclass(frozen=True)
class IntradayEvidenceAssessment:
    valid: bool
    verdict: str | None
    capital_eligible: bool
    candidate_count: int
    ledger_row_count: int
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _reason(reasons: list[str], value: str) -> None:
    if value not in reasons:
        reasons.append(value)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _ledger_rows(data: bytes, candidate_ids: set[str]) -> tuple[list[Mapping[str, Any]], list[str]]:
    rows: list[Mapping[str, Any]] = []
    reasons: list[str] = []
    for raw in data.splitlines():
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _reason(reasons, "ledger_json_invalid")
            continue
        if not isinstance(parsed, Mapping):
            _reason(reasons, "ledger_row_not_object")
            continue
        rows.append(parsed)
        try:
            requested = int(parsed["requested_qty"])
            filled = int(parsed["filled_qty"])
            unfilled = int(parsed["unfilled_qty"])
            status = str(parsed["fill_status"])
            signal_at = datetime.fromisoformat(str(parsed["signal_at_utc"]).replace("Z", "+00:00"))
            eligible_at = datetime.fromisoformat(
                str(parsed["eligible_at_utc"]).replace("Z", "+00:00")
            )
            filled_at = (
                datetime.fromisoformat(str(parsed["filled_at_utc"]).replace("Z", "+00:00"))
                if parsed.get("filled_at_utc") is not None
                else None
            )
            expected_status = (
                "UNFILLED" if filled == 0 else "FULL" if filled == requested else "PARTIAL"
            )
            if (
                parsed.get("candidate_id") not in candidate_ids
                or parsed.get("cost_model") not in {"base", "stress"}
                or parsed.get("symbol") not in EXPECTED_UNIVERSE
                or parsed.get("side") not in {"BUY", "SELL"}
                or requested < 0
                or filled < 0
                or filled > requested
                or unfilled != requested - filled
                or status != expected_status
                or eligible_at < signal_at
                or (filled > 0 and (filled_at is None or filled_at <= signal_at))
                or (filled == 0 and filled_at is not None)
                or any(
                    float(parsed[name]) < 0
                    for name in ("commission_usd", "spread_usd", "slippage_usd")
                )
                or (
                    parsed.get("side") == "SELL"
                    and filled > 0
                    and (
                        parsed.get("gross_pnl_usd") is None
                        or parsed.get("net_pnl_usd") is None
                        or int(parsed.get("holding_minutes", 0)) <= 0
                    )
                )
            ):
                _reason(reasons, "ledger_row_contract_mismatch")
        except (KeyError, TypeError, ValueError):
            _reason(reasons, "ledger_row_contract_mismatch")
    return rows, reasons


def _recompute_gates(
    selected: Mapping[str, Any],
    selection: Mapping[str, Any],
    preregistration: Mapping[str, Any],
) -> dict[str, bool]:
    acceptance = preregistration["acceptance"]
    block = selected["base"]["block"]
    confirmation = selected["base"]["confirmation"]
    stress = selected["stress"]["confirmation"]
    pbo = selection.get("development_pbo")
    dsr = selection.get("selected_dsr")
    return {
        "block_net_positive": float(block["net_return_pct"])
        > float(acceptance["block_net_return_gt"]),
        "confirmation_net_positive": float(confirmation["net_return_pct"])
        > float(acceptance["confirmation_net_return_gt"]),
        "confirmation_sharpe": float(confirmation["annualized_sharpe"])
        >= float(acceptance["confirmation_annualized_sharpe_min"]),
        "confirmation_psr": confirmation["psr"] is not None
        and float(confirmation["psr"]) >= float(acceptance["confirmation_psr_min"]),
        "selected_dsr": dsr is not None and float(dsr) >= float(acceptance["selected_dsr_min"]),
        "development_pbo": pbo is not None
        and float(pbo) <= float(acceptance["development_pbo_max"]),
        "max_drawdown": float(confirmation["max_drawdown_pct"])
        <= float(acceptance["confirmation_max_drawdown_pct_max"]),
        "profit_factor": confirmation["profit_factor"] is not None
        and float(confirmation["profit_factor"])
        >= float(acceptance["confirmation_profit_factor_min"]),
        "positive_quarters": float(confirmation["positive_quarter_fraction"])
        >= float(acceptance["confirmation_positive_quarter_fraction_min"]),
        "symbol_concentration": float(
            confirmation["max_single_symbol_positive_contribution_fraction"]
        )
        <= float(acceptance["max_single_symbol_positive_contribution_fraction"]),
        "trade_concentration": float(confirmation["top_five_trade_positive_contribution_fraction"])
        <= float(acceptance["max_top_five_trade_positive_contribution_fraction"]),
        "stress_net_positive": float(stress["net_return_pct"])
        > float(acceptance["stress_confirmation_net_return_gt"]),
        "base_positions_closed": int(selected["base"]["unclosed_quantity"]) == 0,
        "stress_positions_closed": int(selected["stress"]["unclosed_quantity"]) == 0,
    }


def assess_intraday_evidence(
    evidence: object,
    preregistration: Mapping[str, Any],
    *,
    preregistration_bytes: bytes,
    ledger_bytes: bytes,
) -> IntradayEvidenceAssessment:
    reasons: list[str] = []
    selected_evaluation: Mapping[str, Any] | None = None
    if not isinstance(evidence, Mapping):
        return IntradayEvidenceAssessment(False, None, False, 0, 0, ("root_not_object",))
    if (
        evidence.get("schema_version") != SCHEMA_VERSION
        or evidence.get("gate_version") != GATE_VERSION
        or evidence.get("family_id") != FAMILY_ID
    ):
        _reason(reasons, "identity_contract_mismatch")
    if evidence.get("preregistration_sha256") != _sha256(preregistration_bytes):
        _reason(reasons, "preregistration_digest_mismatch")

    expected_registry = [
        candidate.as_dict() for candidate in build_candidate_registry(preregistration)
    ]
    expected_candidate_ids = {str(row["candidate_id"]) for row in expected_registry}
    expected_registry_by_id = {str(row["candidate_id"]): row for row in expected_registry}
    registry = evidence.get("candidate_registry")
    candidate_count = len(registry) if isinstance(registry, list) else 0
    if registry != expected_registry:
        _reason(reasons, "candidate_registry_mismatch")
    if candidate_count != 18:
        _reason(reasons, "candidate_count_mismatch")
    elif (
        len(
            {
                row.get("candidate_id")
                for row in registry
                if isinstance(row, Mapping) and isinstance(row.get("candidate_id"), str)
            }
        )
        != 18
    ):
        _reason(reasons, "candidate_identity_not_unique")

    if evidence.get("safety") != EXPECTED_SAFETY:
        _reason(reasons, "safety_contract_mismatch")

    audit = evidence.get("audit")
    ledger_rows, ledger_reasons = _ledger_rows(ledger_bytes, expected_candidate_ids)
    actual_rows = len(ledger_rows)
    for reason in ledger_reasons:
        _reason(reasons, reason)
    if not isinstance(audit, Mapping):
        _reason(reasons, "audit_contract_missing")
    else:
        if audit.get("ledger_sha256") != _sha256(ledger_bytes):
            _reason(reasons, "ledger_digest_mismatch")
        if audit.get("ledger_row_count") != actual_rows:
            _reason(reasons, "ledger_row_count_mismatch")

    selection = evidence.get("selection")
    if not isinstance(selection, Mapping):
        _reason(reasons, "selection_missing")
    elif selection.get("development_only") is not True or selection.get("candidate_count") != 18:
        _reason(reasons, "selection_contract_mismatch")
    else:
        selected_id = selection.get("selected_candidate_id")
        evaluations = evidence.get("evaluations")
        if not isinstance(evaluations, list):
            _reason(reasons, "evaluations_missing")
        elif evaluations:
            if len(evaluations) != 18:
                _reason(reasons, "evaluation_count_mismatch")
            evaluation_ids = {
                row.get("candidate_id")
                for row in evaluations
                if isinstance(row, Mapping) and isinstance(row.get("candidate_id"), str)
            }
            if len(evaluation_ids) != len(evaluations):
                _reason(reasons, "evaluation_identity_mismatch")
            for row in evaluations:
                if not isinstance(row, Mapping):
                    _reason(reasons, "evaluation_shape_invalid")
                    continue
                expected_identity = expected_registry_by_id.get(str(row.get("candidate_id")))
                if expected_identity is None or any(
                    row.get(name) != expected_identity[name]
                    for name in (
                        "candidate_id",
                        "family",
                        "timeframe_minutes",
                        "variant",
                        "parameters",
                        "strategy_fingerprint",
                    )
                ):
                    _reason(reasons, "evaluation_identity_mismatch")
            if selected_id not in evaluation_ids:
                _reason(reasons, "selected_candidate_missing")
            else:
                try:
                    recomputed = min(
                        evaluations,
                        key=lambda row: (
                            -float(row["base"]["development"]["annualized_sharpe"]),
                            float(row["base"]["development"]["max_drawdown_pct"]),
                            float(row["base"]["turnover_usd"]),
                            str(row["candidate_id"]),
                        ),
                    )["candidate_id"]
                    if recomputed != selected_id:
                        _reason(reasons, "development_selection_mismatch")
                    selected_evaluation = next(
                        row
                        for row in evaluations
                        if isinstance(row, Mapping) and row.get("candidate_id") == selected_id
                    )
                except (KeyError, TypeError, ValueError):
                    _reason(reasons, "evaluation_shape_invalid")
        elif selected_id is not None:
            _reason(reasons, "selected_candidate_without_evaluations")

    decision = evidence.get("decision")
    verdict: str | None = None
    if not isinstance(decision, Mapping):
        _reason(reasons, "decision_missing")
    else:
        raw_verdict = decision.get("verdict")
        verdict = raw_verdict if isinstance(raw_verdict, str) else None
        if verdict not in VERDICTS:
            _reason(reasons, "verdict_invalid")

        data_quality = evidence.get("data_quality")
        expected_gates: dict[str, bool] | None = None
        expected_verdict: str | None = None
        if not isinstance(data_quality, Mapping):
            _reason(reasons, "data_quality_missing")
        else:
            try:
                minimum = preregistration["minimum_evidence"]
                data_ready = (
                    data_quality.get("complete") is True
                    and data_quality.get("synthetic") is False
                    and int(data_quality["session_count"]) >= int(minimum["minimum_total_sessions"])
                )
                if not data_ready:
                    expected_gates = {"data_complete": False}
                    expected_verdict = "INSUFFICIENT_EVIDENCE"
                elif selected_evaluation is None or not isinstance(selection, Mapping):
                    _reason(reasons, "complete_data_evaluation_missing")
                else:
                    total_trades = sum(
                        int(selected_evaluation["base"][window]["closed_trade_count"])
                        for window in ("development", "block", "confirmation")
                    )
                    enough_trades = total_trades >= int(minimum["minimum_base_cost_closed_trades"])
                    if not enough_trades:
                        expected_gates = {
                            "data_complete": True,
                            "minimum_base_cost_closed_trades": False,
                        }
                        expected_verdict = "INSUFFICIENT_EVIDENCE"
                    else:
                        expected_gates = _recompute_gates(
                            selected_evaluation,
                            selection,
                            preregistration,
                        )
                        expected_verdict = (
                            "PAPER_CHALLENGER"
                            if all(expected_gates.values())
                            else "NO_INTRADAY_EDGE"
                        )
            except (KeyError, TypeError, ValueError):
                _reason(reasons, "decision_inputs_invalid")

        if expected_gates is not None and decision.get("gates") != expected_gates:
            _reason(reasons, "decision_gate_recalculation_mismatch")
        if expected_verdict is None or verdict != expected_verdict:
            _reason(reasons, "verdict_recalculation_mismatch")
        if decision.get("passed") is not (verdict == "PAPER_CHALLENGER"):
            _reason(reasons, "passed_flag_mismatch")

    return IntradayEvidenceAssessment(
        valid=not reasons,
        verdict=verdict,
        capital_eligible=False,
        candidate_count=candidate_count,
        ledger_row_count=actual_rows,
        reasons=tuple(reasons),
    )


__all__ = ["IntradayEvidenceAssessment", "assess_intraday_evidence"]
