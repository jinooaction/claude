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
DEVELOPMENT_DSR_DIAGNOSTIC_MIN = 0.95
PBO_DIAGNOSTIC_MAX = 0.10
HOLDOUT_PSR_MIN = 0.95
FALSE_ACCEPTANCE_MAX = 0.05
DETECTION_MIN = 0.80


def _segments(returns: np.ndarray, count: int = 10) -> list[float]:
    return [annualized_sharpe(segment) for segment in np.array_split(returns, count)]


def _simulate_once(rng: np.random.Generator, planted_sharpe: float) -> dict[str, Any]:
    common_development = rng.normal(size=DEVELOPMENT_OBSERVATIONS)
    common_holdout = rng.normal(size=HOLDOUT_OBSERVATIONS)
    idiosyncratic_development = rng.normal(size=(FAMILY_SIZE, DEVELOPMENT_OBSERVATIONS))
    idiosyncratic_holdout = rng.normal(size=(FAMILY_SIZE, HOLDOUT_OBSERVATIONS))
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
        "legacy_passed": legacy_passed,
        "dsr": None if development_dsr is None else float(development_dsr),
        "pbo": None if development_pbo is None else float(development_pbo),
        "winner_is_planted": winner_index == 0 if planted_sharpe > 0.0 else None,
    }


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(bool(row[key]) for row in rows) / len(rows), 6)


def run_edge_gate_calibration(
    *,
    seed: int = 60_000,
    repetitions: int = 500,
    timestamp_utc: str | None = None,
    code_commit: str = "unknown",
) -> dict[str, Any]:
    if repetitions < 200:
        raise ValueError("calibration requires at least 200 repetitions")
    null_rng = np.random.default_rng(seed)
    edge_rng = np.random.default_rng(seed + 1_000_000)
    null_rows = [_simulate_once(null_rng, 0.0) for _ in range(repetitions)]
    edge_rows = [_simulate_once(edge_rng, PLANTED_SHARPE_ANNUAL) for _ in range(repetitions)]
    revised_false_acceptance = _rate(null_rows, "revised_passed")
    revised_detection = _rate(edge_rows, "revised_passed")
    legacy_false_acceptance = _rate(null_rows, "legacy_passed")
    legacy_detection = _rate(edge_rows, "legacy_passed")
    calibrated = (
        revised_false_acceptance <= FALSE_ACCEPTANCE_MAX and revised_detection >= DETECTION_MIN
    )
    return {
        "schema_version": "1.0",
        "gate_version": GATE_VERSION,
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
        },
        "thresholds": {
            "development_dsr_diagnostic_min": DEVELOPMENT_DSR_DIAGNOSTIC_MIN,
            "development_pbo_diagnostic_max": PBO_DIAGNOSTIC_MAX,
            "holdout_psr_min": HOLDOUT_PSR_MIN,
        },
        "required": {
            "false_acceptance_max": FALSE_ACCEPTANCE_MAX,
            "detection_min": DETECTION_MIN,
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
        "safety": ["simulation only", "no broker API", "no orders", "no capital change"],
    }


__all__ = [
    "CALIBRATED",
    "CALIBRATION_FAILED",
    "DEVELOPMENT_DSR_DIAGNOSTIC_MIN",
    "GATE_VERSION",
    "HOLDOUT_PSR_MIN",
    "PBO_DIAGNOSTIC_MAX",
    "run_edge_gate_calibration",
]
