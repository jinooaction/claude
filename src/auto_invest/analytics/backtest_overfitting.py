"""Search-wide overfitting statistics for the autonomous strategy factory."""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from decimal import Decimal

import numpy as np

from auto_invest.backtest.data_model import canonicalise_decimal


def _decimal(value: float) -> Decimal:
    return Decimal(canonicalise_decimal(value))


def annualized_sharpe(returns: Sequence[float], *, periods_per_year: int = 12) -> float:
    values = np.asarray(returns, dtype=np.float64)
    if values.size < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    if std <= 0.0:
        return 0.0
    return float(np.mean(values)) / std * math.sqrt(periods_per_year)


def probabilistic_sharpe(
    returns: Sequence[float],
    *,
    benchmark_sharpe_annual: float = 0.0,
    periods_per_year: int = 12,
) -> Decimal | None:
    values = np.asarray(returns, dtype=np.float64)
    if values.size < 2:
        return None
    std = float(np.std(values, ddof=1))
    if std <= 0.0:
        return None
    mean = float(np.mean(values))
    centered = values - mean
    m2 = float(np.mean(centered**2))
    if m2 <= 0.0:
        return None
    skew = float(np.mean(centered**3)) / (m2**1.5)
    kurt = float(np.mean(centered**4)) / (m2**2)
    observed = mean / std
    benchmark = benchmark_sharpe_annual / math.sqrt(periods_per_year)
    variance = 1.0 - skew * observed + ((kurt - 1.0) / 4.0) * observed**2
    if variance <= 0.0:
        variance = 1.0 + 0.5 * observed**2
    z = (observed - benchmark) * math.sqrt(values.size - 1) / math.sqrt(variance)
    return _decimal(0.5 * math.erfc(-z / math.sqrt(2.0)))


def expected_max_sharpe_from_trials(trial_sharpes: Sequence[float]) -> float:
    values = np.asarray(trial_sharpes, dtype=np.float64)
    if values.size < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    if std <= 0.0:
        return 0.0
    n = float(values.size)
    # Stable normal quantiles through Python's NormalDist.
    from statistics import NormalDist

    normal = NormalDist()
    gamma = 0.5772156649015329
    return std * (
        (1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / n)
        + gamma * normal.inv_cdf(1.0 - 1.0 / (n * math.e))
    )


def deflated_sharpe_from_trials(
    selected_returns: Sequence[float],
    trial_sharpes: Sequence[float],
    *,
    periods_per_year: int = 12,
) -> Decimal | None:
    return probabilistic_sharpe(
        selected_returns,
        benchmark_sharpe_annual=expected_max_sharpe_from_trials(trial_sharpes),
        periods_per_year=periods_per_year,
    )


def probability_of_backtest_overfitting(
    segment_scores_by_trial: Sequence[Sequence[float]],
) -> Decimal | None:
    """Combinatorially symmetric cross-validation PBO.

    Rows are trials and columns are chronological, non-overlapping OOS segments.
    For every symmetric half split, the IS winner is ranked on the complement.
    PBO is the share of splits where that winner lands in the OOS lower half.
    """

    matrix = np.asarray(segment_scores_by_trial, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 4:
        return None
    trials, segments = matrix.shape
    if segments % 2:
        return None
    half = segments // 2
    lower_half = 0
    evaluated = 0
    all_indexes = tuple(range(segments))
    for is_indexes in itertools.combinations(all_indexes, half):
        # A/B and B/A are equivalent for the aggregate probability; retain one.
        if 0 not in is_indexes:
            continue
        oos_indexes = tuple(index for index in all_indexes if index not in is_indexes)
        is_means = np.mean(matrix[:, is_indexes], axis=1)
        winner = int(np.argmax(is_means))
        oos_means = np.mean(matrix[:, oos_indexes], axis=1)
        winner_score = float(oos_means[winner])
        better = int(np.sum(oos_means > winner_score))
        tied_before = int(np.sum((oos_means == winner_score) & (np.arange(trials) < winner)))
        rank_from_top = better + tied_before + 1
        percentile_from_bottom = (trials - rank_from_top + 0.5) / trials
        if percentile_from_bottom <= 0.5:
            lower_half += 1
        evaluated += 1
    if evaluated == 0:
        return None
    return _decimal(lower_half / evaluated)


__all__ = [
    "annualized_sharpe",
    "deflated_sharpe_from_trials",
    "expected_max_sharpe_from_trials",
    "probabilistic_sharpe",
    "probability_of_backtest_overfitting",
]
