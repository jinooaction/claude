"""Deterministic calibration for paired forward benchmark inference."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from auto_invest.backtest.significance import (
    probabilistic_sharpe_ratio,
    significance_summary,
)

PAIRED_ACTIVE_RETURN_PSR_METHOD = "paired_active_return_psr_v1"
CALIBRATED = "CALIBRATED"
UNDERPOWERED = "UNDERPOWERED"
CALIBRATION_FAILED = "CALIBRATION_FAILED"
OBSERVATIONS = 48
PAPER_THRESHOLD = 0.80
LIVE_THRESHOLD = 0.95
BENCHMARK_DAILY_MEAN = 0.0003
BENCHMARK_DAILY_STD = 0.01
ACTIVE_DAILY_STD = 0.003
PLANTED_ACTIVE_SHARPE_ANNUAL = 1.50
MIN_REPETITIONS = 2_000
MINIMUM_DETECTION_RATE = 0.80


def _acceptance_rates(
    *,
    seed: int,
    repetitions: int,
    active_sharpe_annual: float,
) -> dict[str, dict[str, float]]:
    rng = np.random.default_rng(seed)
    counts = {
        "legacy_fixed_benchmark_sharpe": {"paper": 0, "live": 0},
        "paired_active_return": {"paper": 0, "live": 0},
    }
    active_daily_mean = (
        active_sharpe_annual * ACTIVE_DAILY_STD / math.sqrt(252.0)
    )

    for _ in range(repetitions):
        benchmark = rng.normal(
            BENCHMARK_DAILY_MEAN, BENCHMARK_DAILY_STD, OBSERVATIONS
        )
        active = rng.normal(active_daily_mean, ACTIVE_DAILY_STD, OBSERVATIONS)
        strategy = benchmark + active
        benchmark_summary = significance_summary(benchmark)
        if benchmark_summary is None:  # practically impossible, kept fail-closed
            continue
        legacy_psr = probabilistic_sharpe_ratio(
            strategy,
            benchmark_sharpe_annual=benchmark_summary.sharpe_annual,
        )
        paired_psr = probabilistic_sharpe_ratio(active)
        for key, psr in (
            ("legacy_fixed_benchmark_sharpe", legacy_psr),
            ("paired_active_return", paired_psr),
        ):
            if psr is None:
                continue
            probability = float(psr)
            counts[key]["paper"] += probability >= PAPER_THRESHOLD
            counts[key]["live"] += probability >= LIVE_THRESHOLD

    return {
        key: {
            "paper_acceptance_rate": round(value["paper"] / repetitions, 6),
            "live_acceptance_rate": round(value["live"] / repetitions, 6),
        }
        for key, value in counts.items()
    }


def run_forward_gate_calibration(
    *,
    seed: int = 159_001,
    repetitions: int = 5_000,
    code_commit: str = "unknown",
) -> dict[str, Any]:
    """Compare legacy and paired inference on preregistered null/edge controls."""
    if repetitions < MIN_REPETITIONS:
        raise ValueError(
            f"forward gate calibration requires at least {MIN_REPETITIONS} repetitions"
        )

    null = _acceptance_rates(
        seed=seed,
        repetitions=repetitions,
        active_sharpe_annual=0.0,
    )
    planted = _acceptance_rates(
        seed=seed + 1_000_000,
        repetitions=repetitions,
        active_sharpe_annual=PLANTED_ACTIVE_SHARPE_ANNUAL,
    )
    paired_null = null["paired_active_return"]
    checks = {
        "paper_null_rate_within_17_to_23_pct": (
            0.17 <= paired_null["paper_acceptance_rate"] <= 0.23
        ),
        "live_null_rate_at_most_6_pct": (
            paired_null["live_acceptance_rate"] <= 0.06
        ),
        "paired_planted_power_exceeds_legacy": (
            planted["paired_active_return"]["paper_acceptance_rate"]
            > planted["legacy_fixed_benchmark_sharpe"]["paper_acceptance_rate"]
        ),
        "paper_planted_detection_at_least_80pct": (
            planted["paired_active_return"]["paper_acceptance_rate"]
            >= MINIMUM_DETECTION_RATE
        ),
        "live_planted_detection_at_least_80pct": (
            planted["paired_active_return"]["live_acceptance_rate"]
            >= MINIMUM_DETECTION_RATE
        ),
    }
    calibration_checks = (
        "paper_null_rate_within_17_to_23_pct",
        "live_null_rate_at_most_6_pct",
        "paired_planted_power_exceeds_legacy",
    )
    base_calibrated = all(checks[key] for key in calibration_checks)
    verdict = (
        CALIBRATED
        if all(checks.values())
        else UNDERPOWERED
        if base_calibrated
        else CALIBRATION_FAILED
    )
    return {
        "schema_version": "1.0",
        "significance_method": PAIRED_ACTIVE_RETURN_PSR_METHOD,
        "code_commit": code_commit,
        "verdict": verdict,
        "scenario": {
            "seed_null": seed,
            "seed_planted": seed + 1_000_000,
            "repetitions": repetitions,
            "observations": OBSERVATIONS,
            "benchmark_daily_mean": BENCHMARK_DAILY_MEAN,
            "benchmark_daily_std": BENCHMARK_DAILY_STD,
            "active_daily_std": ACTIVE_DAILY_STD,
            "planted_active_sharpe_annual": PLANTED_ACTIVE_SHARPE_ANNUAL,
        },
        "thresholds": {
            "paper_psr": PAPER_THRESHOLD,
            "live_psr": LIVE_THRESHOLD,
        },
        "required": {"minimum_detection_rate": MINIMUM_DETECTION_RATE},
        "null": null,
        "planted_edge": planted,
        "checks": checks,
        "safety": [
            "simulation only",
            "no broker API",
            "no orders",
            "no capital change",
        ],
    }


__all__ = [
    "CALIBRATED",
    "CALIBRATION_FAILED",
    "MINIMUM_DETECTION_RATE",
    "PAIRED_ACTIVE_RETURN_PSR_METHOD",
    "UNDERPOWERED",
    "run_forward_gate_calibration",
]
