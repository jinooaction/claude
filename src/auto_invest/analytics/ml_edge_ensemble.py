"""Uncertainty-aware machine-learning allocation experiment (spec 145).

This module is research-only. It has no broker, order, live configuration, or
sentinel dependency. Every prediction is produced by an expanding, purged
walk-forward fit and every allocation is long-only with explicit cash.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from statistics import NormalDist
from typing import Any

import numpy as np
import sklearn
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from auto_invest.analytics.global_trend import gold_total_return_factors
from auto_invest.analytics.multi_asset_trend import bond_total_return_factors
from auto_invest.analytics.risk_managed_beta import (
    LegStats,
    MonthlyRow,
    cash_factors,
    market_total_return_factors,
    summarize,
)

ASSETS = ("equity", "bond", "gold")
PERIODS_PER_YEAR = 12
EXPERIMENT_ID = "ml-edge-ensemble-v1"
FEATURE_NAMES = (
    "momentum_1",
    "momentum_3",
    "momentum_6",
    "momentum_12",
    "volatility_3",
    "volatility_6",
    "volatility_12",
    "downside_volatility_12",
    "drawdown_12",
    "trend_distance_3",
    "trend_distance_6",
    "trend_distance_12",
    "rank_momentum_12",
    "equity_bond_corr_12",
    "equity_gold_corr_12",
    "inflation_12",
    "long_rate",
    "long_rate_change_12",
    "earnings_yield",
    "dividend_yield",
    "asset_equity",
    "asset_bond",
    "asset_gold",
    "inflation_x_equity",
    "inflation_x_bond",
    "inflation_x_gold",
    "long_rate_x_equity",
    "long_rate_x_bond",
    "long_rate_x_gold",
)


class MLEdgeDataError(ValueError):
    """Input data cannot support a leakage-free experiment."""


@dataclass(frozen=True)
class MLEdgeConfig:
    min_train_months: int = 120
    validation_months: int = 24
    test_months: int = 12
    purge_months: int = 1
    feature_lookback_months: int = 36
    ridge_alpha: float = 10.0
    boosting_estimators: int = 80
    boosting_learning_rate: float = 0.03
    boosting_max_depth: int = 2
    boosting_min_samples_leaf: int = 12
    uncertainty_quantile: float = 0.70
    uncertainty_scale: float = 0.25
    max_asset_weight: float = 0.40
    max_total_weight: float = 0.99
    cost_scenarios_bps: tuple[int, ...] = (10, 25, 50)


@dataclass(frozen=True)
class PanelRow:
    feature_index: int
    target_index: int
    date: str
    target_date: str
    asset: str
    features: tuple[float, ...]
    target_return: float


@dataclass(frozen=True)
class Prediction:
    feature_index: int
    date: str
    asset: str
    realized_return: float
    ridge: float
    boosting: float
    blended: float
    ridge_uncertainty: float
    boosting_uncertainty: float
    blended_uncertainty: float
    trailing_volatility: float


@dataclass(frozen=True)
class FoldResult:
    fold_id: int
    train_start: str
    train_label_end: str
    test_start: str
    test_end: str
    train_rows: int
    test_rows: int
    ridge_rmse: float
    boosting_rmse: float
    blended_error_quantile: float
    ridge_weight: float
    boosting_weight: float
    chronology_ok: bool


@dataclass(frozen=True)
class AllocationDecision:
    feature_index: int
    date: str
    weights: dict[str, float]
    cash_weight: float
    turnover: float
    gross_return: float


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    passed: bool
    actual: float | int | str | None
    required: str


@dataclass(frozen=True)
class MLEdgeReport:
    schema_version: str
    experiment_id: str
    verdict: str
    reason: str
    data_fingerprint: str
    model_fingerprint: str
    feature_fingerprint: str
    folds: tuple[FoldResult, ...]
    model_metrics: dict[str, Any]
    cost_scenarios: tuple[dict[str, Any], ...]
    benchmarks: dict[str, Any]
    regime_slices: tuple[dict[str, Any], ...]
    significance: dict[str, Any]
    gates: tuple[GateResult, ...]
    candidate_package: dict[str, Any]
    safety: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "verdict": self.verdict,
            "reason": self.reason,
            "data_fingerprint": self.data_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "feature_fingerprint": self.feature_fingerprint,
            "folds": [asdict(row) for row in self.folds],
            "model_metrics": self.model_metrics,
            "cost_scenarios": list(self.cost_scenarios),
            "benchmarks": self.benchmarks,
            "regime_slices": list(self.regime_slices),
            "significance": self.significance,
            "gates": [asdict(row) for row in self.gates],
            "candidate_package": self.candidate_package,
            "safety": self.safety,
        }


def _finite(value: float) -> float:
    return float(value) if math.isfinite(value) else 0.0


def _returns_to_levels(returns: list[float]) -> list[float]:
    levels = [1.0]
    for value in returns:
        levels.append(levels[-1] * (1.0 + value))
    return levels


def _trailing_return(levels: list[float], index: int, months: int) -> float:
    start = levels[index - months]
    return levels[index] / start - 1.0 if start > 0 else 0.0


def _volatility(values: list[float]) -> float:
    return float(np.std(np.asarray(values, dtype=float), ddof=1)) if len(values) >= 2 else 0.0


def _downside_volatility(values: list[float]) -> float:
    downside = [min(value, 0.0) for value in values]
    return _volatility(downside)


def _drawdown(levels: list[float], index: int, months: int) -> float:
    window = levels[index - months : index + 1]
    peak = max(window)
    return levels[index] / peak - 1.0 if peak > 0 else 0.0


def _trend_distance(levels: list[float], index: int, months: int) -> float:
    window = levels[index - months + 1 : index + 1]
    average = sum(window) / len(window)
    return levels[index] / average - 1.0 if average > 0 else 0.0


def _correlation(left: list[float], right: list[float]) -> float:
    if len(left) < 3 or len(right) != len(left):
        return 0.0
    left_arr = np.asarray(left, dtype=float)
    right_arr = np.asarray(right, dtype=float)
    if float(np.std(left_arr)) == 0.0 or float(np.std(right_arr)) == 0.0:
        return 0.0
    return _finite(float(np.corrcoef(left_arr, right_arr)[0, 1]))


def _rank(values: dict[str, float], asset: str) -> float:
    ordered = sorted(values, key=lambda key: (values[key], key))
    return ordered.index(asset) / max(1, len(ordered) - 1)


def _validate_inputs(
    rows: list[MonthlyRow], gold_levels: list[float], config: MLEdgeConfig
) -> None:
    minimum = config.feature_lookback_months + config.min_train_months + config.test_months + 2
    if len(rows) != len(gold_levels):
        raise MLEdgeDataError("gold levels must align 1:1 with monthly rows")
    if len(rows) < minimum:
        raise MLEdgeDataError(f"need at least {minimum} aligned months, got {len(rows)}")
    dates = [row.date for row in rows]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise MLEdgeDataError("monthly dates must be unique and strictly increasing")
    if any(row.price <= 0 for row in rows) or any(level <= 0 for level in gold_levels):
        raise MLEdgeDataError("asset levels must be positive")
    if not 0 < config.uncertainty_quantile < 1:
        raise MLEdgeDataError("uncertainty_quantile must be between zero and one")


def build_panel(
    rows: list[MonthlyRow], gold_levels: list[float], config: MLEdgeConfig | None = None
) -> tuple[list[PanelRow], dict[str, list[float]], dict[str, list[float]], list[float]]:
    """Create pooled, lag-only asset rows and aligned return/level streams."""

    config = config or MLEdgeConfig()
    _validate_inputs(rows, gold_levels, config)
    returns = {
        "equity": [factor - 1.0 for factor in market_total_return_factors(rows)],
        "bond": [factor - 1.0 for factor in bond_total_return_factors(rows)],
        "gold": [factor - 1.0 for factor in gold_total_return_factors(gold_levels)],
    }
    levels = {asset: _returns_to_levels(values) for asset, values in returns.items()}
    cash_returns = [factor - 1.0 for factor in cash_factors(rows)]
    panel: list[PanelRow] = []
    start = config.feature_lookback_months
    for index in range(start, len(rows) - 1):
        momentum_12 = {
            asset: _trailing_return(levels[asset], index, 12) for asset in ASSETS
        }
        eq_bond_corr = _correlation(
            returns["equity"][index - 12 : index], returns["bond"][index - 12 : index]
        )
        eq_gold_corr = _correlation(
            returns["equity"][index - 12 : index], returns["gold"][index - 12 : index]
        )
        cpi_now = rows[index].cpi
        cpi_then = rows[index - 12].cpi
        inflation = cpi_now / cpi_then - 1.0 if cpi_now > 0 and cpi_then > 0 else 0.0
        rate_change = rows[index].long_rate - rows[index - 12].long_rate
        earnings_yield = (
            rows[index].earnings / rows[index].price if rows[index].earnings > 0 else 0.0
        )
        dividend_yield = (
            rows[index].dividend / rows[index].price if rows[index].dividend > 0 else 0.0
        )
        for asset in ASSETS:
            asset_returns = returns[asset]
            asset_levels = levels[asset]
            is_equity = 1.0 if asset == "equity" else 0.0
            is_bond = 1.0 if asset == "bond" else 0.0
            is_gold = 1.0 if asset == "gold" else 0.0
            long_rate = rows[index].long_rate / 100.0
            features = (
                _trailing_return(asset_levels, index, 1),
                _trailing_return(asset_levels, index, 3),
                _trailing_return(asset_levels, index, 6),
                momentum_12[asset],
                _volatility(asset_returns[index - 3 : index]),
                _volatility(asset_returns[index - 6 : index]),
                _volatility(asset_returns[index - 12 : index]),
                _downside_volatility(asset_returns[index - 12 : index]),
                _drawdown(asset_levels, index, 12),
                _trend_distance(asset_levels, index, 3),
                _trend_distance(asset_levels, index, 6),
                _trend_distance(asset_levels, index, 12),
                _rank(momentum_12, asset),
                eq_bond_corr,
                eq_gold_corr,
                inflation,
                long_rate,
                rate_change / 100.0,
                earnings_yield,
                dividend_yield,
                is_equity,
                is_bond,
                is_gold,
                inflation * is_equity,
                inflation * is_bond,
                inflation * is_gold,
                long_rate * is_equity,
                long_rate * is_bond,
                long_rate * is_gold,
            )
            if len(features) != len(FEATURE_NAMES) or not all(math.isfinite(v) for v in features):
                raise MLEdgeDataError(f"non-finite feature at {rows[index].date}/{asset}")
            panel.append(
                PanelRow(
                    feature_index=index,
                    target_index=index + 1,
                    date=rows[index].date,
                    target_date=rows[index + 1].date,
                    asset=asset,
                    features=features,
                    target_return=asset_returns[index],
                )
            )
    return panel, returns, levels, cash_returns


def constrained_weights(
    scores: dict[str, float], *, total_weight: float, max_asset_weight: float
) -> dict[str, float]:
    """Proportionally allocate positive scores with deterministic cap redistribution."""

    positive = {asset: max(0.0, float(scores.get(asset, 0.0))) for asset in ASSETS}
    total_weight = max(0.0, min(float(total_weight), 1.0))
    if sum(positive.values()) <= 0 or total_weight <= 0:
        return {asset: 0.0 for asset in ASSETS}
    weights = {asset: 0.0 for asset in ASSETS}
    active = {asset for asset, score in positive.items() if score > 0}
    remaining = total_weight
    while active and remaining > 1e-12:
        score_total = sum(positive[asset] for asset in active)
        capped: set[str] = set()
        for asset in sorted(active):
            proposed = remaining * positive[asset] / score_total
            room = max_asset_weight - weights[asset]
            if proposed >= room - 1e-12:
                weights[asset] += max(0.0, room)
                remaining -= max(0.0, room)
                capped.add(asset)
        if not capped:
            for asset in active:
                weights[asset] += remaining * positive[asset] / score_total
            remaining = 0.0
        active -= capped
    return {asset: round(min(max_asset_weight, weights[asset]), 12) for asset in ASSETS}


def _models(config: MLEdgeConfig) -> tuple[Any, Any]:
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=config.ridge_alpha))
    boosting = GradientBoostingRegressor(
        n_estimators=config.boosting_estimators,
        learning_rate=config.boosting_learning_rate,
        max_depth=config.boosting_max_depth,
        min_samples_leaf=config.boosting_min_samples_leaf,
        loss="huber",
        random_state=0,
    )
    return ridge, boosting


def _xy(rows: list[PanelRow]) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray([row.features for row in rows], dtype=float),
        np.asarray([row.target_return for row in rows], dtype=float),
    )


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def _walk_forward(
    rows: list[MonthlyRow], panel: list[PanelRow], config: MLEdgeConfig
) -> tuple[tuple[FoldResult, ...], tuple[Prediction, ...]]:
    first_test = config.feature_lookback_months + config.min_train_months + config.purge_months
    final_feature_index = len(rows) - 2
    folds: list[FoldResult] = []
    predictions: list[Prediction] = []
    fold_id = 0
    for test_start in range(first_test, final_feature_index + 1, config.test_months):
        test_end = min(test_start + config.test_months - 1, final_feature_index)
        max_train_target = test_start - config.purge_months
        train = [row for row in panel if row.target_index <= max_train_target]
        test = [row for row in panel if test_start <= row.feature_index <= test_end]
        train_months = len({row.feature_index for row in train})
        if train_months < config.min_train_months or not test:
            continue
        validation_start = max_train_target - config.validation_months + 1
        core = [row for row in train if row.target_index < validation_start]
        validation = [row for row in train if row.target_index >= validation_start]
        if len(core) < 30 or len(validation) < len(ASSETS) * 6:
            continue
        ridge, boosting = _models(config)
        core_x, core_y = _xy(core)
        val_x, val_y = _xy(validation)
        ridge.fit(core_x, core_y)
        boosting.fit(core_x, core_y)
        ridge_val = ridge.predict(val_x)
        boosting_val = boosting.predict(val_x)
        ridge_rmse = _rmse(val_y, ridge_val)
        boosting_rmse = _rmse(val_y, boosting_val)
        inverse = np.asarray(
            [1.0 / max(ridge_rmse, 1e-9), 1.0 / max(boosting_rmse, 1e-9)]
        )
        blend_weights = inverse / inverse.sum()
        blended_val = blend_weights[0] * ridge_val + blend_weights[1] * boosting_val
        blend_errors = np.abs(val_y - blended_val)
        blended_quantile = float(np.quantile(blend_errors, config.uncertainty_quantile))
        train_x, train_y = _xy(train)
        ridge.fit(train_x, train_y)
        boosting.fit(train_x, train_y)
        test_x, _ = _xy(test)
        ridge_test = ridge.predict(test_x)
        boosting_test = boosting.predict(test_x)
        chronology_ok = max(row.target_index for row in train) < min(
            row.feature_index for row in test
        )
        if not chronology_ok:
            raise MLEdgeDataError("walk-forward chronology violation")
        for row, ridge_pred, boost_pred in zip(test, ridge_test, boosting_test, strict=True):
            blended = float(blend_weights[0] * ridge_pred + blend_weights[1] * boost_pred)
            disagreement = abs(float(ridge_pred) - float(boost_pred)) / 2.0
            predictions.append(
                Prediction(
                    feature_index=row.feature_index,
                    date=row.date,
                    asset=row.asset,
                    realized_return=row.target_return,
                    ridge=float(ridge_pred),
                    boosting=float(boost_pred),
                    blended=blended,
                    ridge_uncertainty=ridge_rmse,
                    boosting_uncertainty=boosting_rmse,
                    blended_uncertainty=blended_quantile + disagreement,
                    trailing_volatility=max(row.features[6], 1e-6),
                )
            )
        fold_id += 1
        folds.append(
            FoldResult(
                fold_id=fold_id,
                train_start=train[0].date,
                train_label_end=rows[max_train_target].date,
                test_start=rows[test_start].date,
                test_end=rows[test_end].date,
                train_rows=len(train),
                test_rows=len(test),
                ridge_rmse=ridge_rmse,
                boosting_rmse=boosting_rmse,
                blended_error_quantile=blended_quantile,
                ridge_weight=float(blend_weights[0]),
                boosting_weight=float(blend_weights[1]),
                chronology_ok=True,
            )
        )
    if not folds:
        raise MLEdgeDataError("no valid walk-forward folds")
    return tuple(folds), tuple(predictions)


def _allocation_decisions(
    predictions: tuple[Prediction, ...],
    cash_returns: list[float],
    levels: dict[str, list[float]],
    config: MLEdgeConfig,
    *,
    variant: str,
) -> tuple[AllocationDecision, ...]:
    by_index: dict[int, list[Prediction]] = {}
    for prediction in predictions:
        by_index.setdefault(prediction.feature_index, []).append(prediction)
    previous = {asset: 0.0 for asset in ASSETS}
    decisions: list[AllocationDecision] = []
    for index in sorted(by_index):
        group = {row.asset: row for row in by_index[index]}
        if set(group) != set(ASSETS):
            raise MLEdgeDataError(f"prediction assets incomplete at index {index}")
        lower: dict[str, float] = {}
        for asset, row in group.items():
            prediction = float(getattr(row, variant))
            uncertainty = float(getattr(row, f"{variant}_uncertainty"))
            lower[asset] = max(0.0, prediction - config.uncertainty_scale * uncertainty)
        lower_total = sum(lower.values())
        total_weight = config.max_total_weight if lower_total > 0 else 0.0
        risk_scores = {
            asset: lower[asset] / group[asset].trailing_volatility for asset in ASSETS
        }
        ml_weights = constrained_weights(
            risk_scores,
            total_weight=total_weight,
            max_asset_weight=config.max_asset_weight,
        )
        trend_weights = _trend_weights(index, levels)
        uncertainty_total = sum(
            float(getattr(group[asset], f"{variant}_uncertainty")) for asset in ASSETS
        )
        confidence = (
            lower_total / (lower_total + config.uncertainty_scale * uncertainty_total)
            if lower_total > 0
            else 0.0
        )
        # Keep the incumbent trend allocation as the default and permit the
        # model to tilt it only in proportion to measured forecast confidence.
        weights = {
            asset: (1.0 - confidence) * trend_weights[asset]
            + confidence * ml_weights[asset]
            for asset in ASSETS
        }
        cash_weight = max(0.0, 1.0 - sum(weights.values()))
        turnover = sum(abs(weights[asset] - previous[asset]) for asset in ASSETS)
        gross_return = cash_weight * cash_returns[index] + sum(
            weights[asset] * group[asset].realized_return for asset in ASSETS
        )
        decisions.append(
            AllocationDecision(
                feature_index=index,
                date=group[ASSETS[0]].date,
                weights=weights,
                cash_weight=cash_weight,
                turnover=turnover,
                gross_return=gross_return,
            )
        )
        previous = weights
    return tuple(decisions)


def _trend_weights(index: int, levels: dict[str, list[float]]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for asset in ASSETS:
        passes = 0
        for window in (3, 6, 9, 12):
            average = sum(levels[asset][index - window + 1 : index + 1]) / window
            passes += int(levels[asset][index] > average)
        weights[asset] = 0.33 * passes / 4.0
    return weights


def _factors(decisions: tuple[AllocationDecision, ...], cost_bps: int) -> list[float]:
    return [
        max(1e-9, 1.0 + row.gross_return - row.turnover * cost_bps / 10_000.0)
        for row in decisions
    ]


def _trend_decisions(
    indices: list[int],
    dates: list[str],
    returns: dict[str, list[float]],
    levels: dict[str, list[float]],
    cash_returns: list[float],
) -> tuple[AllocationDecision, ...]:
    previous = {asset: 0.0 for asset in ASSETS}
    out: list[AllocationDecision] = []
    for index, date in zip(indices, dates, strict=True):
        weights = _trend_weights(index, levels)
        cash_weight = 1.0 - sum(weights.values())
        turnover = sum(abs(weights[asset] - previous[asset]) for asset in ASSETS)
        gross_return = cash_weight * cash_returns[index] + sum(
            weights[asset] * returns[asset][index] for asset in ASSETS
        )
        out.append(
            AllocationDecision(index, date, weights, cash_weight, turnover, gross_return)
        )
        previous = weights
    return tuple(out)


def _passive_decisions(
    indices: list[int],
    dates: list[str],
    returns: dict[str, list[float]],
    cash_returns: list[float],
) -> tuple[AllocationDecision, ...]:
    weights = {asset: 0.33 for asset in ASSETS}
    out: list[AllocationDecision] = []
    for offset, (index, date) in enumerate(zip(indices, dates, strict=True)):
        gross_return = 0.01 * cash_returns[index] + sum(
            weights[asset] * returns[asset][index] for asset in ASSETS
        )
        out.append(
            AllocationDecision(
                index,
                date,
                dict(weights),
                0.01,
                0.99 if offset == 0 else 0.0,
                gross_return,
            )
        )
    return tuple(out)


def _stats_dict(stats: LegStats) -> dict[str, Any]:
    return stats.as_dict()


def _periodic_psr(returns: list[float], benchmark_sharpe_annual: float) -> float | None:
    values = np.asarray(returns, dtype=float)
    if values.size < 2 or float(np.std(values, ddof=1)) <= 0:
        return None
    sr = float(np.mean(values) / np.std(values, ddof=1))
    centered = values - float(np.mean(values))
    variance = float(np.mean(centered**2))
    skew = float(np.mean(centered**3) / variance**1.5) if variance > 0 else 0.0
    kurt = float(np.mean(centered**4) / variance**2) if variance > 0 else 3.0
    estimator_var = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    estimator_var = estimator_var if estimator_var > 0 else 1.0 + 0.5 * sr * sr
    benchmark = benchmark_sharpe_annual / math.sqrt(PERIODS_PER_YEAR)
    z = (sr - benchmark) * math.sqrt(values.size - 1) / math.sqrt(estimator_var)
    return NormalDist().cdf(z)


def _periodic_dsr(returns: list[float], trial_sharpes: list[float]) -> float | None:
    if not trial_sharpes:
        return None
    if len(trial_sharpes) == 1:
        benchmark = 0.0
    else:
        trial_std = float(np.std(np.asarray(trial_sharpes), ddof=1))
        n = float(len(trial_sharpes))
        euler = 0.5772156649015329
        normal = NormalDist()
        benchmark = trial_std * (
            (1.0 - euler) * normal.inv_cdf(1.0 - 1.0 / n)
            + euler * normal.inv_cdf(1.0 - 1.0 / (n * math.e))
        )
    return _periodic_psr(returns, benchmark)


def _fold_win_rate(
    decisions: tuple[AllocationDecision, ...],
    passive: tuple[AllocationDecision, ...],
    trend: tuple[AllocationDecision, ...],
    folds: tuple[FoldResult, ...],
) -> tuple[int, float]:
    wins = 0
    for fold in folds:
        candidate_factors = _factors(
            tuple(row for row in decisions if fold.test_start <= row.date <= fold.test_end), 25
        )
        passive_factors = _factors(
            tuple(row for row in passive if fold.test_start <= row.date <= fold.test_end), 25
        )
        trend_factors = _factors(
            tuple(row for row in trend if fold.test_start <= row.date <= fold.test_end), 25
        )
        if not candidate_factors:
            continue
        candidate_return = math.prod(candidate_factors) - 1.0
        benchmark_return = max(math.prod(passive_factors), math.prod(trend_factors)) - 1.0
        wins += int(candidate_return > benchmark_return)
    return wins, wins / len(folds) if folds else 0.0


def _regime_slices(
    rows: list[MonthlyRow], decisions: tuple[AllocationDecision, ...]
) -> tuple[dict[str, Any], ...]:
    inflation_values = []
    for decision in decisions:
        index = decision.feature_index
        now = rows[index].cpi
        before = rows[index - 12].cpi
        inflation_values.append(now / before - 1.0 if now > 0 and before > 0 else 0.0)
    inflation_median = float(np.median(np.asarray(inflation_values)))
    groups: dict[str, list[float]] = {}
    for decision, inflation in zip(decisions, inflation_values, strict=True):
        stock_return = (
            rows[decision.feature_index].price
            / rows[decision.feature_index - 12].price
            - 1.0
        )
        label = ("high_inflation" if inflation >= inflation_median else "low_inflation") + (
            "_risk_on" if stock_return >= 0 else "_risk_off"
        )
        groups.setdefault(label, []).append(1.0 + decision.gross_return)
    return tuple(
        {
            "regime": label,
            "n_months": len(factors),
            "metrics": _stats_dict(summarize(factors)),
        }
        for label, factors in sorted(groups.items())
    )


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def run_ml_edge_ensemble(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    config: MLEdgeConfig | None = None,
) -> MLEdgeReport:
    """Run the complete no-live ML experiment and return a fail-closed report."""

    config = config or MLEdgeConfig()
    panel, returns, levels, cash_returns = build_panel(rows, gold_levels, config)
    folds, predictions = _walk_forward(rows, panel, config)
    ensemble = _allocation_decisions(
        predictions, cash_returns, levels, config, variant="blended"
    )
    ridge = _allocation_decisions(predictions, cash_returns, levels, config, variant="ridge")
    boosting = _allocation_decisions(
        predictions, cash_returns, levels, config, variant="boosting"
    )
    indices = [row.feature_index for row in ensemble]
    dates = [row.date for row in ensemble]
    passive = _passive_decisions(indices, dates, returns, cash_returns)
    trend = _trend_decisions(indices, dates, returns, levels, cash_returns)
    cost_rows: list[dict[str, Any]] = []
    factors_by_cost: dict[int, list[float]] = {}
    for cost in config.cost_scenarios_bps:
        factors = _factors(ensemble, cost)
        factors_by_cost[cost] = factors
        cost_rows.append(
            {
                "cost_bps": cost,
                "metrics": _stats_dict(summarize(factors)),
                "total_return_pct": (math.prod(factors) - 1.0) * 100.0,
                "turnover": round(sum(row.turnover for row in ensemble), 6),
            }
        )
    primary_factors = factors_by_cost[25]
    primary_stats = summarize(primary_factors)
    passive_stats = summarize(_factors(passive, 25))
    trend_stats = summarize(_factors(trend, 25))
    better_benchmark_sharpe = max(passive_stats.sharpe, trend_stats.sharpe)
    psr = _periodic_psr([factor - 1.0 for factor in primary_factors], better_benchmark_sharpe)
    trial_sharpes = [
        summarize(_factors(decisions, 25)).sharpe for decisions in (ridge, boosting, ensemble)
    ]
    dsr = _periodic_dsr([factor - 1.0 for factor in primary_factors], trial_sharpes)
    fold_wins, fold_win_rate = _fold_win_rate(ensemble, passive, trend, folds)
    fifty_total_return_pct = (math.prod(factors_by_cost[50]) - 1.0) * 100.0
    better_drawdown = min(passive_stats.max_dd_pct, trend_stats.max_dd_pct)
    gates = (
        GateResult("fold_count", len(folds) >= 20, len(folds), ">= 20"),
        GateResult("positive_25bp_cagr", primary_stats.cagr_pct > 0, primary_stats.cagr_pct, "> 0"),
        GateResult(
            "sharpe_margin",
            primary_stats.sharpe >= better_benchmark_sharpe + 0.20,
            primary_stats.sharpe - better_benchmark_sharpe,
            ">= 0.20 over both benchmarks",
        ),
        GateResult("psr", psr is not None and psr >= 0.95, psr, ">= 0.95"),
        GateResult("dsr", dsr is not None and dsr >= 0.95, dsr, ">= 0.95"),
        GateResult("fold_win_rate", fold_win_rate >= 0.60, fold_win_rate, ">= 0.60"),
        GateResult(
            "max_drawdown",
            primary_stats.max_dd_pct <= better_drawdown,
            primary_stats.max_dd_pct,
            f"<= {better_drawdown:.6f}",
        ),
        GateResult(
            "positive_50bp_return",
            fifty_total_return_pct > 0,
            fifty_total_return_pct,
            "> 0",
        ),
    )
    ready = all(gate.passed for gate in gates)
    verdict = "ML_EDGE_CANDIDATE_READY" if ready else "NO_EDGE"
    failed = [gate.gate_id for gate in gates if not gate.passed]
    reason = "all pre-registered gates passed" if ready else "failed gates: " + ", ".join(failed)
    data_fingerprint = _fingerprint(
        {
            "rows": [asdict(row) for row in rows],
            "gold_levels": gold_levels,
        }
    )
    model_fingerprint = _fingerprint(
        {"config": asdict(config), "sklearn": sklearn.__version__, "models": ["ridge", "gbrt"]}
    )
    feature_fingerprint = _fingerprint(FEATURE_NAMES)
    candidate_package = {
        "eligible": ready,
        "candidate_id": "candidate-ml-edge-ensemble-v1",
        "title_ko": "AI 확신도 기반 추세 앙상블 재현 검증",
        "domain_key": "investment_edge",
        "status": "new" if ready else "rejected",
        "risk_grade": 2,
        "priority_score": 700,
        "kind": "strategy_backtest",
        "verdict": verdict,
        "reason_ko": reason,
        "next_action_ko": "독립 no-live 재현 후 Canary 승격 여부를 판단한다.",
        "replay_command": "uv run python scripts/ml_edge_ensemble_probe.py --json",
        "evidence_refs": ["ml-edge-ensemble", "public-data", "regime-stratify"],
        "data_fingerprint": data_fingerprint,
        "model_fingerprint": model_fingerprint,
        "feature_fingerprint": feature_fingerprint,
        "live_promotion_authorized": False,
    }
    return MLEdgeReport(
        schema_version="1.0",
        experiment_id=EXPERIMENT_ID,
        verdict=verdict,
        reason=reason,
        data_fingerprint=data_fingerprint,
        model_fingerprint=model_fingerprint,
        feature_fingerprint=feature_fingerprint,
        folds=folds,
        model_metrics={
            "ridge_mean_validation_rmse": float(np.mean([fold.ridge_rmse for fold in folds])),
            "boosting_mean_validation_rmse": float(
                np.mean([fold.boosting_rmse for fold in folds])
            ),
            "prediction_months": len(ensemble),
            "trial_sharpes_annual": trial_sharpes,
            "fold_wins": fold_wins,
            "fold_win_rate": fold_win_rate,
        },
        cost_scenarios=tuple(cost_rows),
        benchmarks={
            "passive_equal_weight_25bp": _stats_dict(passive_stats),
            "incumbent_trend_ensemble_25bp": _stats_dict(trend_stats),
        },
        regime_slices=_regime_slices(rows, ensemble),
        significance={"psr_vs_better_benchmark": psr, "dsr_three_model_trials": dsr},
        gates=gates,
        candidate_package=candidate_package,
        safety={
            "orders_submitted": 0,
            "orders_cancelled": 0,
            "live_strategy_changed": False,
            "capital_changed": False,
            "whitelist_changed": False,
            "caps_changed": False,
        },
    )


def render_markdown(report: MLEdgeReport) -> str:
    """Render a compact operator-readable report."""

    lines = [
        "# 불확실성 인식 AI 엣지 앙상블",
        "",
        "| 항목 | 값 |",
        "|------|----|",
        f"| 판정 | {report.verdict} |",
        f"| 이유 | {report.reason} |",
        f"| 워크포워드 구간 | {len(report.folds)} |",
        f"| 예측 월 | {report.model_metrics['prediction_months']} |",
        f"| PSR | {report.significance['psr_vs_better_benchmark']} |",
        f"| DSR | {report.significance['dsr_three_model_trials']} |",
        "",
        "## 비용 차감 결과",
        "",
        "| 비용(bp) | CAGR% | 샤프 | 최대낙폭% | 회전율 |",
        "|---------:|------:|-----:|-----------:|-------:|",
    ]
    for row in report.cost_scenarios:
        metrics = row["metrics"]
        lines.append(
            f"| {row['cost_bps']} | {metrics['cagr_pct']} | {metrics['sharpe']} | "
            f"{metrics['max_dd_pct']} | {row['turnover']} |"
        )
    lines.extend(
        [
            "",
            "## 승격 관문",
            "",
            "| 관문 | 통과 | 현재 | 기준 |",
            "|------|------|------|------|",
        ]
    )
    for gate in report.gates:
        lines.append(
            f"| {gate.gate_id} | {'PASS' if gate.passed else 'FAIL'} | "
            f"{gate.actual} | {gate.required} |"
        )
    lines.extend(
        [
            "",
            "> 연구 전용: 주문·취소·live 전략 교체·자본 변경 0건.",
            f"> data `{report.data_fingerprint}`",
            f"> model `{report.model_fingerprint}`",
            f"> feature `{report.feature_fingerprint}`",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "AllocationDecision",
    "FEATURE_NAMES",
    "FoldResult",
    "GateResult",
    "MLEdgeConfig",
    "MLEdgeDataError",
    "MLEdgeReport",
    "PanelRow",
    "Prediction",
    "build_panel",
    "constrained_weights",
    "render_markdown",
    "run_ml_edge_ensemble",
]
