from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_invest.analytics.strategy_acceptance_path_audit import (
    PARTIAL_COVERAGE,
    audit_strategy_acceptance_path,
)

ROOT = Path(__file__).resolve().parents[2]


def _regime_result() -> dict:
    return json.loads(
        (ROOT / "specs/171-parallel-regime-edge-challenger/production-result.json").read_text(
            encoding="utf-8"
        )
    )


def _edge_calibration() -> dict:
    return {
        "verdict": "CALIBRATED",
        "family_calibrations": {
            "16": {
                "null_research_entry_acceptance_rate": 0.01,
                "target_research_entry_detection_rate": 0.84,
            }
        },
    }


def _forward_calibration() -> dict:
    return {
        "verdict": "UNDERPOWERED",
        "scenario": {"observations": 48, "planted_active_sharpe_annual": 1.5},
        "required": {"minimum_detection_rate": 0.8},
        "planted_edge": {
            "paired_active_return": {
                "paper_acceptance_rate": 0.424,
                "live_acceptance_rate": 0.1545,
            }
        },
    }


def test_audit_separates_promising_history_from_partial_gate_calibration() -> None:
    report = audit_strategy_acceptance_path(
        _regime_result(), _edge_calibration(), _forward_calibration()
    )

    assert report["historical_gate_summary"]["passed_count"] == 7
    assert report["historical_gate_summary"]["total_count"] == 8
    assert report["historical_gate_summary"]["failed_gates"] == ["recent_segment_wins"]
    assert report["calibration_coverage"]["status"] == PARTIAL_COVERAGE
    assert report["calibration_coverage"]["directly_calibrated_gates"] == [
        "family_pbo",
        "holdout_active_psr",
    ]
    assert len(report["calibration_coverage"]["uncalibrated_full_path_gates"]) == 6
    assert report["forward_power"]["verdict"] == "UNDERPOWERED"
    assert report["conclusion"]["historical_signal"] == "PROMISING_NOT_APPROVED"
    assert report["conclusion"]["live_capital_eligible"] is False
    assert report["safety"]["orders_submitted"] == 0


def test_audit_rejects_missing_or_mutated_gate_set() -> None:
    result = _regime_result()
    result["gates"].pop("annual_turnover")

    with pytest.raises(ValueError, match="gate set"):
        audit_strategy_acceptance_path(result, _edge_calibration(), _forward_calibration())


def test_audit_rejects_uncalibrated_statistical_core() -> None:
    calibration = _edge_calibration()
    calibration["verdict"] = "CALIBRATION_FAILED"

    with pytest.raises(ValueError, match="statistical core"):
        audit_strategy_acceptance_path(
            _regime_result(), calibration, _forward_calibration()
        )
