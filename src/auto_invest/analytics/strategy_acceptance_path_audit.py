"""Read-only audit of the actual strategy acceptance path.

This module separates historical promise, research-gate approval, calibration coverage,
and live-capital eligibility. It never imports broker, order, capital, or live modules.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "strategy-acceptance-path-audit-v1"
PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
FULL_COVERAGE = "FULL_COVERAGE"

EXPECTED_GATES = (
    "family_pbo",
    "holdout_active_psr",
    "holdout_cagr",
    "holdout_sharpe",
    "holdout_drawdown",
    "recent_segment_wins",
    "latest_60_month_sharpe",
    "annual_turnover",
)
DIRECTLY_CALIBRATED_GATES = ("family_pbo", "holdout_active_psr")
SAFETY = {
    "promotion_allowed": False,
    "orders_submitted": 0,
    "capital_changed": False,
    "live_strategy_changed": False,
}


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def audit_strategy_acceptance_path(
    regime_result: Mapping[str, Any],
    edge_calibration: Mapping[str, Any],
    forward_calibration: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a fail-closed evidence report without changing any strategy state."""

    gates = _mapping(regime_result.get("gates"), "regime gate set")
    if set(gates) != set(EXPECTED_GATES) or not all(
        isinstance(value, bool) for value in gates.values()
    ):
        raise ValueError("regime gate set mismatch")
    safety = _mapping(regime_result.get("safety"), "regime safety")
    if safety != {
        "promotion_allowed": False,
        "orders_submitted": 0,
        "capital_changed": False,
    }:
        raise ValueError("regime safety boundary mismatch")
    if edge_calibration.get("verdict") != "CALIBRATED":
        raise ValueError("statistical core calibration is not calibrated")

    family_calibrations = _mapping(
        edge_calibration.get("family_calibrations"), "family calibrations"
    )
    family_16 = _mapping(family_calibrations.get("16"), "16-candidate calibration")
    null_admission = _number(
        family_16.get("null_research_entry_acceptance_rate"), "null admission"
    )
    planted_detection = _number(
        family_16.get("target_research_entry_detection_rate"), "planted detection"
    )

    scenario = _mapping(forward_calibration.get("scenario"), "forward scenario")
    required = _mapping(forward_calibration.get("required"), "forward requirements")
    planted = _mapping(forward_calibration.get("planted_edge"), "forward planted edge")
    paired = _mapping(planted.get("paired_active_return"), "paired planted edge")
    forward_verdict = str(forward_calibration.get("verdict") or "")
    if forward_verdict not in {"CALIBRATED", "UNDERPOWERED", "CALIBRATION_FAILED"}:
        raise ValueError("forward calibration verdict mismatch")

    passed = [name for name in EXPECTED_GATES if gates[name]]
    failed = [name for name in EXPECTED_GATES if not gates[name]]
    uncovered = [name for name in EXPECTED_GATES if name not in DIRECTLY_CALIBRATED_GATES]
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": regime_result.get("selected_candidate_id"),
        "incumbent_id": regime_result.get("incumbent_id"),
        "historical_gate_summary": {
            "verdict": regime_result.get("verdict"),
            "passed_count": len(passed),
            "total_count": len(EXPECTED_GATES),
            "passed_gates": passed,
            "failed_gates": failed,
        },
        "calibration_coverage": {
            "status": FULL_COVERAGE if not uncovered else PARTIAL_COVERAGE,
            "directly_calibrated_gates": list(DIRECTLY_CALIBRATED_GATES),
            "uncalibrated_full_path_gates": uncovered,
            "family_16_null_research_entry_acceptance_rate": null_admission,
            "family_16_planted_research_entry_detection_rate": planted_detection,
            "claim_limit": (
                "The calibration covers the statistical core, not simultaneous passage "
                "of all eight historical gates."
            ),
        },
        "forward_power": {
            "verdict": forward_verdict,
            "observations": int(_number(scenario.get("observations"), "observations")),
            "planted_active_sharpe_annual": _number(
                scenario.get("planted_active_sharpe_annual"), "planted sharpe"
            ),
            "minimum_detection_rate": _number(
                required.get("minimum_detection_rate"), "minimum detection rate"
            ),
            "paper_detection_rate": _number(
                paired.get("paper_acceptance_rate"), "paper detection rate"
            ),
            "live_detection_rate": _number(
                paired.get("live_acceptance_rate"), "live detection rate"
            ),
        },
        "conclusion": {
            "historical_signal": "PROMISING_NOT_APPROVED" if passed else "NO_SIGNAL",
            "research_gate_approved": not failed,
            "full_path_power_calibrated": not uncovered and forward_verdict == "CALIBRATED",
            "live_capital_eligible": False,
        },
        "safety": dict(SAFETY),
    }


def report_markdown(payload: Mapping[str, Any]) -> str:
    history = _mapping(payload["historical_gate_summary"], "history")
    coverage = _mapping(payload["calibration_coverage"], "coverage")
    forward = _mapping(payload["forward_power"], "forward")
    return "\n".join(
        [
            "# 전략 합격 경로 감사",
            "",
            f"- 후보: `{payload['candidate_id']}`",
            f"- 역사 관문: {history['passed_count']}/{history['total_count']} 통과",
            f"- 실패 관문: {', '.join(history['failed_gates']) or '없음'}",
            f"- 전체 교정 범위: `{coverage['status']}`",
            (
                f"- 전진 검출력: `{forward['verdict']}` — "
                f"paper {forward['paper_detection_rate']:.2%}, "
                f"live {forward['live_detection_rate']:.2%}, "
                f"요구 {forward['minimum_detection_rate']:.0%}"
            ),
            "- 결론: 역사적으로 유망하지만 연구 합격·실자본 적격 후보는 아니다.",
            "- 안전: 주문 0건, 자본 변경 없음, 라이브 전략 변경 없음.",
        ]
    )


__all__ = [
    "FULL_COVERAGE",
    "PARTIAL_COVERAGE",
    "SCHEMA_VERSION",
    "audit_strategy_acceptance_path",
    "report_markdown",
]
