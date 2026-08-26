"""Deterministic type-I/type-II calibration for the hierarchical edge gate."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import numpy as np

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probabilistic_sharpe,
    probability_of_backtest_overfitting,
)

GATE_VERSION = "2.0"
CALIBRATED = "CALIBRATED"
CALIBRATION_FAILED = "CALIBRATION_FAILED"
FAMILY_SIZE = 64
DEVELOPMENT_OBSERVATIONS = 204
HOLDOUT_OBSERVATIONS = 235
CANDIDATE_CORRELATION = 0.80
PLANTED_SHARPE_ANNUAL = 0.60
POWER_SHARPES_ANNUAL = (0.20, 0.30, 0.40, 0.50, 0.60, 0.80)
DEVELOPMENT_DSR_DIAGNOSTIC_MIN = 0.95
PBO_DIAGNOSTIC_MAX = 0.10
RESEARCH_ENTRY_PBO_MAX = 0.25
HOLDOUT_PSR_MIN = 0.95
PAPER_PSR_MIN = 0.80
FALSE_ACCEPTANCE_MAX = 0.05
FAMILY_FALSE_ACCEPTANCE_MAX = 0.01
PROGRAM_FALSE_ACCEPTANCE_BUDGET = 0.20
MAXIMUM_RESEARCH_FAMILIES = 20
DETECTION_MIN = 0.80
CALIBRATION_SEED = 60_000
CALIBRATION_MIN_REPETITIONS = 500
RESEARCH_ENTRY_GATE_VERSION = "3.1"


def _segments(returns: np.ndarray, count: int = 10) -> list[float]:
    return [annualized_sharpe(segment) for segment in np.array_split(returns, count)]


def _simulate_once(
    rng: np.random.Generator,
    planted_sharpe: float,
    *,
    family_size: int = FAMILY_SIZE,
) -> dict[str, Any]:
    common_development = rng.normal(size=DEVELOPMENT_OBSERVATIONS)
    common_holdout = rng.normal(size=HOLDOUT_OBSERVATIONS)
    idiosyncratic_development = rng.normal(size=(family_size, DEVELOPMENT_OBSERVATIONS))
    idiosyncratic_holdout = rng.normal(size=(family_size, HOLDOUT_OBSERVATIONS))
    common_weight = math.sqrt(CANDIDATE_CORRELATION)
    residual_weight = math.sqrt(1.0 - CANDIDATE_CORRELATION)
    development = common_weight * common_development + residual_weight * idiosyncratic_development
    holdout = common_weight * common_holdout + residual_weight * idiosyncratic_holdout
    if planted_sharpe > 0.0:
        monthly_mean = planted_sharpe / math.sqrt(12.0)
        development[0] += monthly_mean
        holdout[0] += monthly_mean

    trial_sharpes = [annualized_sharpe(row) for row in development]
    winner_index = int(np.argmax(trial_sharpes))
    effective_trials = effective_independent_trials(development)
    development_dsr = deflated_sharpe_from_trials(
        development[winner_index],
        trial_sharpes,
        effective_trial_count=effective_trials,
    )
    segment_scores = [_segments(row) for row in development]
    development_pbo = probability_of_backtest_overfitting(segment_scores)
    holdout_psr = probabilistic_sharpe(holdout[winner_index])

    prior_sharpes = rng.normal(
        loc=0.0,
        scale=max(float(np.std(trial_sharpes, ddof=1)), 0.01),
        size=512,
    )
    legacy_dsr = deflated_sharpe_from_trials(
        development[winner_index],
        [*prior_sharpes.tolist(), *trial_sharpes],
    )
    revised_passed = holdout_psr is not None and holdout_psr >= HOLDOUT_PSR_MIN
    research_entry_passed = (
        revised_passed
        and development_pbo is not None
        and development_pbo <= RESEARCH_ENTRY_PBO_MAX
    )
    legacy_passed = (
        legacy_dsr is not None
        and legacy_dsr >= 0.95
        and development_pbo is not None
        and development_pbo <= PBO_DIAGNOSTIC_MAX
        and holdout_psr is not None
        and holdout_psr >= HOLDOUT_PSR_MIN
    )
    return {
        "revised_passed": revised_passed,
        "research_entry_passed": research_entry_passed,
        "paper_admitted": holdout_psr is not None and holdout_psr >= PAPER_PSR_MIN,
        "legacy_passed": legacy_passed,
        "dsr": None if development_dsr is None else float(development_dsr),
        "pbo": None if development_pbo is None else float(development_pbo),
        "winner_is_planted": winner_index == 0 if planted_sharpe > 0.0 else None,
        "holdout_psr": None if holdout_psr is None else float(holdout_psr),
    }


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(bool(row[key]) for row in rows) / len(rows), 6)


def _power_seed(seed: int, family_size: int, planted_sharpe: float) -> int:
    if planted_sharpe == PLANTED_SHARPE_ANNUAL:
        return seed + 1_000_000
    return seed + 2_000_000 + family_size * 10_000 + int(planted_sharpe * 10_000)


def _family_calibration(
    *, seed: int, repetitions: int, family_size: int
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[float, list[dict[str, Any]]]]:
    null_rng = np.random.default_rng(seed)
    null_rows = [
        _simulate_once(null_rng, 0.0, family_size=family_size) for _ in range(repetitions)
    ]
    power_rows: dict[float, list[dict[str, Any]]] = {}
    power_curve: dict[str, Any] = {}
    for planted_sharpe in POWER_SHARPES_ANNUAL:
        rng = np.random.default_rng(_power_seed(seed, family_size, planted_sharpe))
        rows = [
            _simulate_once(rng, planted_sharpe, family_size=family_size)
            for _ in range(repetitions)
        ]
        power_rows[planted_sharpe] = rows
        power_curve[f"{planted_sharpe:.2f}"] = {
            "live_detection_rate": _rate(rows, "revised_passed"),
            "research_entry_detection_rate": _rate(rows, "research_entry_passed"),
            "paper_admission_rate": _rate(rows, "paper_admitted"),
            "planted_candidate_selection_rate": _rate(rows, "winner_is_planted"),
        }
    false_acceptance = _rate(null_rows, "revised_passed")
    target_detection = power_curve[f"{PLANTED_SHARPE_ANNUAL:.2f}"]["live_detection_rate"]
    research_false_acceptance = _rate(null_rows, "research_entry_passed")
    research_target_detection = power_curve[f"{PLANTED_SHARPE_ANNUAL:.2f}"][
        "research_entry_detection_rate"
    ]
    minimum_detectable = next(
        (
            key
            for key, value in power_curve.items()
            if value["live_detection_rate"] >= DETECTION_MIN
        ),
        None,
    )
    report = {
        "family_size": family_size,
        "null_false_acceptance_rate": false_acceptance,
        "null_paper_admission_rate": _rate(null_rows, "paper_admitted"),
        "target_planted_sharpe_annual": PLANTED_SHARPE_ANNUAL,
        "target_live_detection_rate": target_detection,
        "minimum_80pct_detectable_sharpe": minimum_detectable,
        "live_calibrated": (
            false_acceptance <= FALSE_ACCEPTANCE_MAX and target_detection >= DETECTION_MIN
        ),
        "null_research_entry_acceptance_rate": research_false_acceptance,
        "target_research_entry_detection_rate": research_target_detection,
        "research_entry_calibrated": (
            research_false_acceptance <= FAMILY_FALSE_ACCEPTANCE_MAX
            and research_target_detection >= DETECTION_MIN
        ),
        "power_curve": power_curve,
    }
    return report, null_rows, power_rows


def run_edge_gate_calibration(
    *,
    seed: int = 60_000,
    repetitions: int = 500,
    timestamp_utc: str | None = None,
    code_commit: str = "unknown",
) -> dict[str, Any]:
    if repetitions < 200:
        raise ValueError("calibration requires at least 200 repetitions")
    family_calibrations: dict[str, Any] = {}
    raw_rows: dict[int, tuple[list[dict[str, Any]], dict[float, list[dict[str, Any]]]]] = {}
    for family_size in (16, 64):
        family_report, null, power = _family_calibration(
            seed=seed, repetitions=repetitions, family_size=family_size
        )
        family_calibrations[str(family_size)] = family_report
        raw_rows[family_size] = (null, power)
    null_rows, family_64_power = raw_rows[64]
    edge_rows = family_64_power[PLANTED_SHARPE_ANNUAL]
    revised_false_acceptance = _rate(null_rows, "revised_passed")
    revised_detection = _rate(edge_rows, "revised_passed")
    legacy_false_acceptance = _rate(null_rows, "legacy_passed")
    legacy_detection = _rate(edge_rows, "legacy_passed")
    research_entry_calibrated = all(
        report["research_entry_calibrated"] is True
        for report in family_calibrations.values()
    )
    calibrated = all(
        report["live_calibrated"] is True for report in family_calibrations.values()
    ) and research_entry_calibrated
    return {
        "schema_version": "1.0",
        "gate_version": GATE_VERSION,
        "research_entry_gate_version": RESEARCH_ENTRY_GATE_VERSION,
        "timestamp_utc": timestamp_utc or datetime.now(UTC).isoformat(),
        "code_commit": code_commit,
        "verdict": CALIBRATED if calibrated else CALIBRATION_FAILED,
        "scenario": {
            "seed": seed,
            "repetitions": repetitions,
            "family_size": FAMILY_SIZE,
            "development_observations": DEVELOPMENT_OBSERVATIONS,
            "holdout_observations": HOLDOUT_OBSERVATIONS,
            "candidate_correlation": CANDIDATE_CORRELATION,
            "planted_sharpe_annual": PLANTED_SHARPE_ANNUAL,
            "power_sharpes_annual": list(POWER_SHARPES_ANNUAL),
            "calibrated_family_sizes": [16, 64],
        },
        "thresholds": {
            "development_dsr_diagnostic_min": DEVELOPMENT_DSR_DIAGNOSTIC_MIN,
            "development_pbo_diagnostic_max": PBO_DIAGNOSTIC_MAX,
            "research_entry_pbo_max": RESEARCH_ENTRY_PBO_MAX,
            "holdout_psr_min": HOLDOUT_PSR_MIN,
            "paper_psr_min": PAPER_PSR_MIN,
        },
        "required": {
            "false_acceptance_max": FALSE_ACCEPTANCE_MAX,
            "family_false_acceptance_max": FAMILY_FALSE_ACCEPTANCE_MAX,
            "detection_min": DETECTION_MIN,
            "program_false_acceptance_budget": PROGRAM_FALSE_ACCEPTANCE_BUDGET,
            "maximum_research_families": MAXIMUM_RESEARCH_FAMILIES,
        },
        "research_entry": {
            "method": "holdout-psr-plus-family-pbo-v1",
            "calibrated": research_entry_calibrated,
            "calibration_seed": seed,
            "minimum_repetitions": CALIBRATION_MIN_REPETITIONS,
            "family_false_acceptance_max": FAMILY_FALSE_ACCEPTANCE_MAX,
            "program_false_acceptance_budget": PROGRAM_FALSE_ACCEPTANCE_BUDGET,
            "maximum_research_families": MAXIMUM_RESEARCH_FAMILIES,
        },
        "revised": {
            "false_acceptance_rate": revised_false_acceptance,
            "detection_rate": revised_detection,
            "planted_candidate_selection_rate": _rate(edge_rows, "winner_is_planted"),
            "median_pbo_null": round(
                float(np.median([row["pbo"] for row in null_rows if row["pbo"] is not None])),
                6,
            ),
            "median_pbo_planted": round(
                float(np.median([row["pbo"] for row in edge_rows if row["pbo"] is not None])),
                6,
            ),
        },
        "legacy": {
            "false_acceptance_rate": legacy_false_acceptance,
            "detection_rate": legacy_detection,
            "description": "raw 576-trial DSR 0.95 plus PBO 0.10 plus holdout PSR 0.95",
        },
        "family_calibrations": family_calibrations,
        "safety": ["simulation only", "no broker API", "no orders", "no capital change"],
    }


__all__ = [
    "CALIBRATED",
    "CALIBRATION_FAILED",
    "CALIBRATION_MIN_REPETITIONS",
    "CALIBRATION_SEED",
    "DETECTION_MIN",
    "DEVELOPMENT_DSR_DIAGNOSTIC_MIN",
    "FAMILY_FALSE_ACCEPTANCE_MAX",
    "GATE_VERSION",
    "HOLDOUT_PSR_MIN",
    "MAXIMUM_RESEARCH_FAMILIES",
    "PAPER_PSR_MIN",
    "PBO_DIAGNOSTIC_MAX",
    "PROGRAM_FALSE_ACCEPTANCE_BUDGET",
    "RESEARCH_ENTRY_GATE_VERSION",
    "RESEARCH_ENTRY_PBO_MAX",
    "run_edge_gate_calibration",
]
