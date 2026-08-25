"""Daily cross-asset machine-learning challenger (spec 146).

The module is deliberately research-only: it accepts immutable close series and
returns evidence. It does not know about brokers, orders, live configuration, or
capital state.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date
from statistics import NormalDist
from typing import Any

import numpy as np
import sklearn
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

UNIVERSE = ("SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ", "UUP")
EXPERIMENT_ID = "daily-cross-asset-ml-v1"
PERIODS_PER_YEAR = 52
FEATURE_NAMES = (
    "momentum_1w",
    "momentum_4w",
    "momentum_13w",
    "momentum_26w",
    "momentum_52w",
    "volatility_4w",
    "volatility_13w",
    "volatility_26w",
    "downside_volatility_13w",
    "drawdown_26w",
    "trend_distance_13w",
    "trend_distance_26w",
    "rank_momentum_13w",
    "rank_momentum_26w",
    "spy_correlation_26w",
    "market_breadth_13w",
    "spy_momentum_13w",
    "spy_volatility_13w",
    *tuple(f"asset_{symbol}" for symbol in UNIVERSE),
)


class DailyMLEdgeDataError(ValueError):
    """Input data cannot support a leakage-free experiment."""


@dataclass(frozen=True)
class DailyClose:
    session_date: str
    close: float
    volume: int = 0


@dataclass(frozen=True)
class DailyMLConfig:
    min_daily_bars: int = 1_200
    feature_lookback_weeks: int = 52
    min_train_weeks: int = 104
    validation_weeks: int = 26
    test_weeks: int = 8
    purge_weeks: int = 1
    ridge_alpha: float = 12.0
    boosting_estimators: int = 80
    boosting_learning_rate: float = 0.03
    boosting_max_depth: int = 2
    boosting_min_samples_leaf: int = 24
    uncertainty_quantile: float = 0.70
    uncertainty_scale: float = 0.25
    top_n: int = 4
    max_asset_weight: float = 0.25
    max_total_weight: float = 0.99
    cost_scenarios_bps: tuple[int, ...] = (10, 25, 50)
    minimum_hold_weeks: int = 0
    trade_threshold: float = 0.0
    estimated_trade_cost_bps: int = 0


@dataclass(frozen=True)
class PanelRow:
    feature_index: int
    target_index: int
    date: str
    target_date: str
    asset: str
    features: tuple[float, ...]
    target_return: float
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
    chronology_ok: bool


@dataclass(frozen=True)
class Prediction:
    feature_index: int
    date: str
    asset: str
    realized_return: float
    ridge_return: float
    boosting_return: float
    predicted_return: float
    uncertainty: float
    trailing_volatility: float


@dataclass(frozen=True)
class Decision:
    feature_index: int
    date: str
    weights: dict[str, float]
    cash_weight: float
    turnover: float
    gross_return: float
    suppressed_trades: int = 0


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    passed: bool
    actual: float | int | None
    required: str


@dataclass(frozen=True)
class DailyMLReport:
    schema_version: str
    experiment_id: str
    verdict: str
    reason: str
    data: dict[str, Any]
    folds: tuple[FoldResult, ...]
    model_metrics: dict[str, Any]
    cost_scenarios: tuple[dict[str, Any], ...]
    benchmarks: dict[str, Any]
    significance: dict[str, Any]
    gates: tuple[GateResult, ...]
    latest_allocation: dict[str, Any]
    candidate_package: dict[str, Any]
    fingerprints: dict[str, str]
    safety: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "verdict": self.verdict,
            "reason": self.reason,
            "data": self.data,
            "folds": [asdict(row) for row in self.folds],
            "model_metrics": self.model_metrics,
            "cost_scenarios": list(self.cost_scenarios),
            "benchmarks": self.benchmarks,
            "significance": self.significance,
            "gates": [asdict(row) for row in self.gates],
            "latest_allocation": self.latest_allocation,
            "candidate_package": self.candidate_package,
            "fingerprints": self.fingerprints,
            "safety": self.safety,
        }


def _fingerprint(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _ret(levels: Sequence[float], index: int, weeks: int) -> float:
    return levels[index] / levels[index - weeks] - 1.0


def _vol(values: Sequence[float]) -> float:
    return float(np.std(np.asarray(values, dtype=float), ddof=1)) if len(values) >= 2 else 0.0


def _corr(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) < 3 or len(left) != len(right) or _vol(left) == 0 or _vol(right) == 0:
        return 0.0
    value = float(np.corrcoef(np.asarray(left), np.asarray(right))[0, 1])
    return value if math.isfinite(value) else 0.0


def _rank(values: Mapping[str, float], asset: str) -> float:
    ordered = sorted(values, key=lambda key: (values[key], key))
    return ordered.index(asset) / (len(ordered) - 1)


def _weekly_levels(
    daily: Mapping[str, Sequence[DailyClose]], config: DailyMLConfig
) -> tuple[list[str], dict[str, list[float]]]:
    if set(daily) != set(UNIVERSE):
        missing = sorted(set(UNIVERSE) - set(daily))
        extra = sorted(set(daily) - set(UNIVERSE))
        raise DailyMLEdgeDataError(f"universe mismatch missing={missing} extra={extra}")
    maps: dict[str, dict[str, float]] = {}
    for symbol in UNIVERSE:
        rows = list(daily[symbol])
        if len(rows) < config.min_daily_bars:
            raise DailyMLEdgeDataError(
                f"{symbol} needs at least {config.min_daily_bars} daily bars, got {len(rows)}"
            )
        dates = [row.session_date for row in rows]
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise DailyMLEdgeDataError(f"{symbol} dates must be unique and increasing")
        if any(not math.isfinite(row.close) or row.close <= 0 for row in rows):
            raise DailyMLEdgeDataError(f"{symbol} contains invalid close")
        maps[symbol] = {row.session_date: float(row.close) for row in rows}
    common = set.intersection(*(set(values) for values in maps.values()))
    if len(common) < config.min_daily_bars:
        raise DailyMLEdgeDataError(f"common daily coverage is only {len(common)} bars")
    week_ends: dict[tuple[int, int], str] = {}
    for raw in sorted(common):
        parsed = date.fromisoformat(raw[:10])
        iso = parsed.isocalendar()
        week_ends[(iso.year, iso.week)] = raw
    dates = [week_ends[key] for key in sorted(week_ends)]
    minimum = config.feature_lookback_weeks + config.min_train_weeks + config.purge_weeks + 2
    if len(dates) < minimum:
        raise DailyMLEdgeDataError(f"need at least {minimum} aligned weeks, got {len(dates)}")
    return dates, {symbol: [maps[symbol][raw] for raw in dates] for symbol in UNIVERSE}


def build_panel(
    daily: Mapping[str, Sequence[DailyClose]], config: DailyMLConfig | None = None
) -> tuple[list[str], dict[str, list[float]], dict[str, list[float]], list[PanelRow]]:
    """Build a weekly pooled panel where every feature predates its target."""

    config = config or DailyMLConfig()
    dates, levels = _weekly_levels(daily, config)
    returns = {
        symbol: [levels[symbol][i] / levels[symbol][i - 1] - 1.0 for i in range(1, len(dates))]
        for symbol in UNIVERSE
    }
    panel: list[PanelRow] = []
    for index in range(config.feature_lookback_weeks, len(dates) - 1):
        mom13 = {symbol: _ret(levels[symbol], index, 13) for symbol in UNIVERSE}
        mom26 = {symbol: _ret(levels[symbol], index, 26) for symbol in UNIVERSE}
        breadth = sum(value > 0 for value in mom13.values()) / len(UNIVERSE)
        spy_returns = returns["SPY"][index - 26 : index]
        for asset_index, symbol in enumerate(UNIVERSE):
            asset_returns = returns[symbol]
            window13 = asset_returns[index - 13 : index]
            window26 = asset_returns[index - 26 : index]
            peak = max(levels[symbol][index - 26 : index + 1])
            average13 = sum(levels[symbol][index - 12 : index + 1]) / 13
            average26 = sum(levels[symbol][index - 25 : index + 1]) / 26
            one_hot = tuple(float(i == asset_index) for i in range(len(UNIVERSE)))
            features = (
                _ret(levels[symbol], index, 1),
                _ret(levels[symbol], index, 4),
                mom13[symbol],
                mom26[symbol],
                _ret(levels[symbol], index, 52),
                _vol(asset_returns[index - 4 : index]),
                _vol(window13),
                _vol(window26),
                _vol([min(value, 0.0) for value in window13]),
                levels[symbol][index] / peak - 1.0,
                levels[symbol][index] / average13 - 1.0,
                levels[symbol][index] / average26 - 1.0,
                _rank(mom13, symbol),
                _rank(mom26, symbol),
                _corr(window26, spy_returns),
                breadth,
                mom13["SPY"],
                _vol(returns["SPY"][index - 13 : index]),
                *one_hot,
            )
            if len(features) != len(FEATURE_NAMES) or not all(math.isfinite(v) for v in features):
                raise DailyMLEdgeDataError(f"non-finite feature at {dates[index]}/{symbol}")
            panel.append(
                PanelRow(
                    feature_index=index,
                    target_index=index + 1,
                    date=dates[index],
                    target_date=dates[index + 1],
                    asset=symbol,
                    features=features,
                    target_return=asset_returns[index],
                    trailing_volatility=max(_vol(window13), 1e-6),
                )
            )
    return dates, levels, returns, panel


def _models(config: DailyMLConfig) -> tuple[Any, Any]:
    return (
        make_pipeline(StandardScaler(), Ridge(alpha=config.ridge_alpha)),
        GradientBoostingRegressor(
            n_estimators=config.boosting_estimators,
            learning_rate=config.boosting_learning_rate,
            max_depth=config.boosting_max_depth,
            min_samples_leaf=config.boosting_min_samples_leaf,
            loss="huber",
            random_state=0,
        ),
    )


def _xy(rows: Sequence[PanelRow]) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray([row.features for row in rows]),
        np.asarray([row.target_return for row in rows]),
    )


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def _walk_forward(
    dates: Sequence[str], panel: Sequence[PanelRow], config: DailyMLConfig
) -> tuple[tuple[FoldResult, ...], tuple[Prediction, ...]]:
    first_test = config.feature_lookback_weeks + config.min_train_weeks + config.purge_weeks
    last_test = max(row.feature_index for row in panel)
    folds: list[FoldResult] = []
    predictions: list[Prediction] = []
    for fold_id, test_start in enumerate(
        range(first_test, last_test + 1, config.test_weeks), start=1
    ):
        test_end = min(test_start + config.test_weeks - 1, last_test)
        max_train_target = test_start - config.purge_weeks
        train = [row for row in panel if row.target_index <= max_train_target]
        test = [row for row in panel if test_start <= row.feature_index <= test_end]
        validation_start = max_train_target - config.validation_weeks + 1
        core = [row for row in train if row.target_index < validation_start]
        validation = [row for row in train if row.target_index >= validation_start]
        if len({row.feature_index for row in train}) < config.min_train_weeks or not test:
            continue
        if len(validation) < len(UNIVERSE) * 8 or not core:
            continue
        ridge, boosting = _models(config)
        core_x, core_y = _xy(core)
        val_x, val_y = _xy(validation)
        ridge.fit(core_x, core_y)
        boosting.fit(core_x, core_y)
        ridge_val = ridge.predict(val_x)
        boost_val = boosting.predict(val_x)
        ridge_rmse = _rmse(val_y, ridge_val)
        boost_rmse = _rmse(val_y, boost_val)
        inverse = np.asarray([1 / max(ridge_rmse, 1e-9), 1 / max(boost_rmse, 1e-9)])
        blend_weights = inverse / inverse.sum()
        blend_val = blend_weights[0] * ridge_val + blend_weights[1] * boost_val
        error_quantile = float(np.quantile(np.abs(val_y - blend_val), config.uncertainty_quantile))
        train_x, train_y = _xy(train)
        test_x, _ = _xy(test)
        ridge.fit(train_x, train_y)
        boosting.fit(train_x, train_y)
        ridge_test = ridge.predict(test_x)
        boost_test = boosting.predict(test_x)
        chronology_ok = max(row.target_index for row in train) < min(
            row.feature_index for row in test
        )
        if not chronology_ok:
            raise DailyMLEdgeDataError("walk-forward chronology violation")
        for row, ridge_pred, boost_pred in zip(test, ridge_test, boost_test, strict=True):
            prediction = float(blend_weights[0] * ridge_pred + blend_weights[1] * boost_pred)
            uncertainty = error_quantile + abs(float(ridge_pred) - float(boost_pred)) / 2
            predictions.append(
                Prediction(
                    row.feature_index,
                    row.date,
                    row.asset,
                    row.target_return,
                    float(ridge_pred),
                    float(boost_pred),
                    prediction,
                    uncertainty,
                    row.trailing_volatility,
                )
            )
        folds.append(
            FoldResult(
                fold_id,
                train[0].date,
                dates[max_train_target],
                dates[test_start],
                dates[test_end],
                len(train),
                len(test),
                ridge_rmse,
                boost_rmse,
                error_quantile,
                chronology_ok,
            )
        )
    if not folds:
        raise DailyMLEdgeDataError("no valid walk-forward folds")
    return tuple(folds), tuple(predictions)


def _capped_weights(scores: Mapping[str, float], config: DailyMLConfig) -> dict[str, float]:
    selected = sorted(
        ((symbol, max(0.0, score)) for symbol, score in scores.items()),
        key=lambda item: (-item[1], item[0]),
    )[: config.top_n]
    selected = [(symbol, score) for symbol, score in selected if score > 0]
    weights = {symbol: 0.0 for symbol in UNIVERSE}
    active = {symbol for symbol, _ in selected}
    raw = dict(selected)
    remaining = config.max_total_weight
    while active and remaining > 1e-12:
        total = sum(raw[symbol] for symbol in active)
        capped: set[str] = set()
        for symbol in sorted(active):
            proposed = remaining * raw[symbol] / total
            room = config.max_asset_weight - weights[symbol]
            if proposed >= room - 1e-12:
                weights[symbol] += max(0.0, room)
                remaining -= max(0.0, room)
                capped.add(symbol)
        if not capped:
            for symbol in active:
                weights[symbol] += remaining * raw[symbol] / total
            remaining = 0.0
        active -= capped
    return {symbol: round(value, 12) for symbol, value in weights.items()}


def _ml_decisions(
    predictions: Sequence[Prediction],
    config: DailyMLConfig,
    *,
    prediction_field: str = "predicted_return",
) -> tuple[Decision, ...]:
    grouped: dict[int, list[Prediction]] = {}
    for row in predictions:
        grouped.setdefault(row.feature_index, []).append(row)
    previous = {symbol: 0.0 for symbol in UNIVERSE}
    holding_age = {symbol: 0 for symbol in UNIVERSE}
    out: list[Decision] = []
    for index in sorted(grouped):
        group = {row.asset: row for row in grouped[index]}
        if set(group) != set(UNIVERSE):
            raise DailyMLEdgeDataError(f"incomplete predictions at index {index}")
        cost_floor = config.estimated_trade_cost_bps / 10_000
        scores = {
            symbol: max(
                0.0,
                float(getattr(row, prediction_field))
                - config.uncertainty_scale * row.uncertainty
                - cost_floor,
            )
            / row.trailing_volatility
            for symbol, row in group.items()
        }
        raw_weights = _capped_weights(scores, config)
        weights = dict(raw_weights)
        suppressed = 0
        for symbol in UNIVERSE:
            delta = raw_weights[symbol] - previous[symbol]
            still_locked = (
                previous[symbol] > 0
                and raw_weights[symbol] < previous[symbol]
                and holding_age[symbol] < config.minimum_hold_weeks
            )
            below_threshold = abs(delta) < config.trade_threshold
            if delta != 0 and (still_locked or below_threshold):
                weights[symbol] = previous[symbol]
                suppressed += 1
        total_weight = sum(weights.values())
        if total_weight > config.max_total_weight:
            scale = config.max_total_weight / total_weight
            weights = {symbol: weight * scale for symbol, weight in weights.items()}
        cash = max(0.0, 1.0 - sum(weights.values()))
        turnover = sum(abs(weights[symbol] - previous[symbol]) for symbol in UNIVERSE)
        gross = sum(weights[symbol] * group[symbol].realized_return for symbol in UNIVERSE)
        out.append(
            Decision(
                index,
                next(iter(group.values())).date,
                weights,
                cash,
                turnover,
                gross,
                suppressed,
            )
        )
        holding_age = {
            symbol: (
                holding_age[symbol] + 1
                if weights[symbol] > 0 and previous[symbol] > 0
                else (1 if weights[symbol] > 0 else 0)
            )
            for symbol in UNIVERSE
        }
        previous = weights
    return tuple(out)


def _benchmark_decisions(
    indices: Sequence[int],
    dates: Sequence[str],
    levels: Mapping[str, Sequence[float]],
    returns: Mapping[str, Sequence[float]],
    *,
    trend: bool,
) -> tuple[Decision, ...]:
    previous = {symbol: 0.0 for symbol in UNIVERSE}
    out: list[Decision] = []
    for index, raw_date in zip(indices, dates, strict=True):
        if trend:
            inv_vol = {
                symbol: 1 / max(_vol(returns[symbol][index - 13 : index]), 1e-6)
                for symbol in UNIVERSE
            }
            inv_total = sum(inv_vol.values())
            base = {symbol: 0.99 * inv_vol[symbol] / inv_total for symbol in UNIVERSE}
            weights = {
                symbol: base[symbol]
                * sum(
                    levels[symbol][index]
                    > sum(levels[symbol][index - window + 1 : index + 1]) / window
                    for window in (13, 26, 39, 52)
                )
                / 4
                for symbol in UNIVERSE
            }
        else:
            weights = {symbol: 0.99 / len(UNIVERSE) for symbol in UNIVERSE}
        cash = 1 - sum(weights.values())
        turnover = sum(abs(weights[symbol] - previous[symbol]) for symbol in UNIVERSE)
        gross = sum(weights[symbol] * returns[symbol][index] for symbol in UNIVERSE)
        out.append(Decision(index, raw_date, weights, cash, turnover, gross))
        previous = weights
    return tuple(out)


def _net_returns(decisions: Sequence[Decision], cost_bps: int) -> list[float]:
    return [row.gross_return - row.turnover * cost_bps / 10_000 for row in decisions]


def _stats(values: Sequence[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    factors = np.maximum(1e-9, 1 + arr)
    wealth = np.cumprod(factors)
    years = len(arr) / PERIODS_PER_YEAR
    cagr = float(wealth[-1] ** (1 / years) - 1) if years > 0 else 0.0
    volatility = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    sharpe = float(np.mean(arr) / volatility * math.sqrt(PERIODS_PER_YEAR)) if volatility else 0.0
    peaks = np.maximum.accumulate(np.concatenate(([1.0], wealth)))
    drawdowns = 1 - np.concatenate(([1.0], wealth)) / peaks
    return {
        "total_return_pct": round((float(wealth[-1]) - 1) * 100, 6),
        "cagr_pct": round(cagr * 100, 6),
        "sharpe": round(sharpe, 6),
        "max_dd_pct": round(float(np.max(drawdowns)) * 100, 6),
    }


def _psr(values: Sequence[float], benchmark_sharpe: float) -> float | None:
    arr = np.asarray(values, dtype=float)
    std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    if std <= 0:
        return None
    sr = float(np.mean(arr) / std)
    centered = arr - float(np.mean(arr))
    variance = float(np.mean(centered**2))
    skew = float(np.mean(centered**3) / variance**1.5) if variance else 0.0
    kurt = float(np.mean(centered**4) / variance**2) if variance else 3.0
    estimator_var = max(1e-9, 1 - skew * sr + (kurt - 1) * sr * sr / 4)
    target = benchmark_sharpe / math.sqrt(PERIODS_PER_YEAR)
    return NormalDist().cdf((sr - target) * math.sqrt(len(arr) - 1) / math.sqrt(estimator_var))


def _dsr(values: Sequence[float], trial_sharpes: Sequence[float]) -> float | None:
    if len(trial_sharpes) < 2:
        return _psr(values, 0.0)
    trial_std = float(np.std(np.asarray(trial_sharpes), ddof=1))
    n = float(len(trial_sharpes))
    normal = NormalDist()
    benchmark = trial_std * (
        (1 - 0.5772156649) * normal.inv_cdf(1 - 1 / n)
        + 0.5772156649 * normal.inv_cdf(1 - 1 / (n * math.e))
    )
    return _psr(values, benchmark)


def run_daily_cross_asset_ml(
    daily: Mapping[str, Sequence[DailyClose]], config: DailyMLConfig | None = None
) -> DailyMLReport:
    """Run the complete no-live experiment and produce a fail-closed verdict."""

    config = config or DailyMLConfig()
    dates, levels, returns, panel = build_panel(daily, config)
    folds, predictions = _walk_forward(dates, panel, config)
    baseline_candidate = _ml_decisions(
        predictions,
        replace(
            config,
            minimum_hold_weeks=0,
            trade_threshold=0.0,
            estimated_trade_cost_bps=0,
        ),
    )
    candidate = _ml_decisions(predictions, config)
    ridge_candidate = _ml_decisions(predictions, config, prediction_field="ridge_return")
    boosting_candidate = _ml_decisions(predictions, config, prediction_field="boosting_return")
    indices = [row.feature_index for row in candidate]
    decision_dates = [row.date for row in candidate]
    passive = _benchmark_decisions(indices, decision_dates, levels, returns, trend=False)
    trend = _benchmark_decisions(indices, decision_dates, levels, returns, trend=True)
    cost_rows = tuple(
        {
            "cost_bps": cost,
            "metrics": _stats(_net_returns(candidate, cost)),
            "turnover": round(sum(row.turnover for row in candidate), 6),
        }
        for cost in config.cost_scenarios_bps
    )
    primary_returns = _net_returns(candidate, 25)
    primary = _stats(primary_returns)
    passive_stats = _stats(_net_returns(passive, 25))
    trend_stats = _stats(_net_returns(trend, 25))
    better_sharpe = max(passive_stats["sharpe"], trend_stats["sharpe"])
    psr = _psr(primary_returns, better_sharpe)
    trial_sharpes = [
        _stats(_net_returns(rows, 25))["sharpe"]
        for rows in (ridge_candidate, boosting_candidate, candidate)
    ]
    dsr = _dsr(primary_returns, trial_sharpes)
    wins = 0
    for fold in folds:
        candidate_fold = [row for row in candidate if fold.test_start <= row.date <= fold.test_end]
        passive_fold = [row for row in passive if fold.test_start <= row.date <= fold.test_end]
        trend_fold = [row for row in trend if fold.test_start <= row.date <= fold.test_end]
        candidate_total = math.prod(1 + value for value in _net_returns(candidate_fold, 25))
        passive_total = math.prod(1 + value for value in _net_returns(passive_fold, 25))
        trend_total = math.prod(1 + value for value in _net_returns(trend_fold, 25))
        wins += int(candidate_total > max(passive_total, trend_total))
    win_rate = wins / len(folds)
    better_drawdown = min(passive_stats["max_dd_pct"], trend_stats["max_dd_pct"])
    fifty = next(row for row in cost_rows if row["cost_bps"] == 50)["metrics"]
    baseline_turnover = sum(row.turnover for row in baseline_candidate)
    candidate_turnover = sum(row.turnover for row in candidate)
    suppressed_trades = sum(row.suppressed_trades for row in candidate)
    gates = (
        GateResult("fold_count", len(folds) >= 10, len(folds), ">= 10"),
        GateResult("positive_25bp_cagr", primary["cagr_pct"] > 0, primary["cagr_pct"], "> 0"),
        GateResult(
            "sharpe_margin",
            primary["sharpe"] >= better_sharpe + 0.20,
            primary["sharpe"] - better_sharpe,
            ">= 0.20 over both benchmarks",
        ),
        GateResult("psr", psr is not None and psr >= 0.95, psr, ">= 0.95"),
        GateResult("dsr", dsr is not None and dsr >= 0.95, dsr, ">= 0.95"),
        GateResult("fold_win_rate", win_rate >= 0.60, win_rate, ">= 0.60"),
        GateResult(
            "max_drawdown",
            primary["max_dd_pct"] <= better_drawdown,
            primary["max_dd_pct"],
            f"<= {better_drawdown}",
        ),
        GateResult(
            "positive_50bp_return", fifty["total_return_pct"] > 0, fifty["total_return_pct"], "> 0"
        ),
        GateResult(
            "turnover_not_increased",
            candidate_turnover <= baseline_turnover + 1e-12,
            candidate_turnover,
            f"<= baseline {baseline_turnover:.6f}",
        ),
    )
    ready = all(gate.passed for gate in gates)
    verdict = "DAILY_ML_EDGE_CANDIDATE_READY" if ready else "NO_EDGE"
    failed = [gate.gate_id for gate in gates if not gate.passed]
    reason = "all pre-registered gates passed" if ready else "failed gates: " + ", ".join(failed)
    data_payload = {
        symbol: [(row.session_date, row.close, row.volume) for row in daily[symbol]]
        for symbol in UNIVERSE
    }
    fingerprints = {
        "data": _fingerprint(data_payload),
        "model": _fingerprint({"config": asdict(config), "sklearn": sklearn.__version__}),
        "features": _fingerprint(FEATURE_NAMES),
    }
    low_turnover_enabled = (
        config.minimum_hold_weeks > 0
        or config.trade_threshold > 0
        or config.estimated_trade_cost_bps > 0
    )
    experiment_id = (
        "low-turnover-daily-cross-asset-ml-v2" if low_turnover_enabled else EXPERIMENT_ID
    )
    latest = candidate[-1]
    package = {
        "eligible": ready,
        "candidate_id": (
            "candidate-low-turnover-daily-cross-asset-ml-v2"
            if low_turnover_enabled
            else "candidate-daily-cross-asset-ml-v1"
        ),
        "title_ko": (
            "저회전 일봉 교차자산 AI 상대수익 후보"
            if low_turnover_enabled
            else "일봉 교차자산 AI 상대수익 후보 재현 검증"
        ),
        "domain_key": "investment_edge",
        "status": "new" if ready else "rejected",
        "risk_grade": 2,
        "priority_score": 760,
        "kind": "strategy_backtest",
        "verdict": verdict,
        "reason_ko": reason,
        "next_action_ko": "독립 no-live 재현 뒤 기존 Canary 승격 관문을 적용한다.",
        "replay_command": (
            "uv run python scripts/daily_cross_asset_ml_probe.py "
            "--db data/forward_v2_wide.db --json"
        ),
        "evidence_refs": ["daily-cross-asset-ml", "kis-price-bars", "global-trend-wide"],
        **fingerprints,
        "live_promotion_authorized": False,
    }
    return DailyMLReport(
        "1.1",
        experiment_id,
        verdict,
        reason,
        {
            "symbols": list(UNIVERSE),
            "daily_counts": {s: len(daily[s]) for s in UNIVERSE},
            "common_week_start": dates[0],
            "common_week_end": dates[-1],
            "common_weeks": len(dates),
        },
        folds,
        {
            "prediction_weeks": len(candidate),
            "fold_wins": wins,
            "fold_win_rate": win_rate,
            "baseline_turnover": round(baseline_turnover, 6),
            "candidate_turnover": round(candidate_turnover, 6),
            "turnover_reduction_pct": round((1 - candidate_turnover / baseline_turnover) * 100, 6)
            if baseline_turnover > 0
            else 0.0,
            "suppressed_trades": suppressed_trades,
            "minimum_hold_weeks": config.minimum_hold_weeks,
            "trade_threshold": config.trade_threshold,
            "estimated_trade_cost_bps": config.estimated_trade_cost_bps,
            "ridge_mean_validation_rmse": float(np.mean([f.ridge_rmse for f in folds])),
            "boosting_mean_validation_rmse": float(np.mean([f.boosting_rmse for f in folds])),
            "trial_sharpes_annual": trial_sharpes,
        },
        cost_rows,
        {"passive_equal_weight_25bp": passive_stats, "incumbent_wide_trend_25bp": trend_stats},
        {"psr_vs_better_benchmark": psr, "dsr_model_trials": dsr},
        gates,
        {"date": latest.date, "weights": latest.weights, "cash_weight": latest.cash_weight},
        package,
        fingerprints,
        {
            "orders_submitted": 0,
            "orders_cancelled": 0,
            "live_strategy_changed": False,
            "capital_changed": False,
            "whitelist_changed": False,
            "caps_changed": False,
        },
    )


def run_low_turnover_daily_cross_asset_ml(
    daily: Mapping[str, Sequence[DailyClose]],
    config: DailyMLConfig | None = None,
) -> DailyMLReport:
    """Run the separately identified low-turnover challenger (spec 147)."""
    low_turnover = config or DailyMLConfig(
        minimum_hold_weeks=4,
        trade_threshold=0.08,
        estimated_trade_cost_bps=25,
    )
    return run_daily_cross_asset_ml(daily, low_turnover)


def render_markdown(report: DailyMLReport) -> str:
    lines = [
        "# 일봉 교차자산 AI 후보",
        "",
        "| 항목 | 값 |",
        "|------|----|",
        f"| 판정 | {report.verdict} |",
        f"| 이유 | {report.reason} |",
        f"| 공통 주 | {report.data['common_weeks']} |",
        f"| 미래 구간 | {len(report.folds)} |",
        f"| PSR | {report.significance['psr_vs_better_benchmark']} |",
        f"| DSR | {report.significance['dsr_model_trials']} |",
        f"| 기준 회전율 | {report.model_metrics['baseline_turnover']} |",
        f"| 후보 회전율 | {report.model_metrics['candidate_turnover']} |",
        f"| 회전율 감소 | {report.model_metrics['turnover_reduction_pct']}% |",
        f"| 억제 거래 | {report.model_metrics['suppressed_trades']} |",
        "",
        "## 비용 차감 결과",
        "",
        "| 비용(bp) | CAGR% | 샤프 | 최대낙폭% | 총수익% |",
        "|---------:|------:|-----:|-----------:|--------:|",
    ]
    for row in report.cost_scenarios:
        metric = row["metrics"]
        lines.append(
            f"| {row['cost_bps']} | {metric['cagr_pct']} | {metric['sharpe']} | "
            f"{metric['max_dd_pct']} | {metric['total_return_pct']} |"
        )
    lines.extend(
        [
            "",
            "## 승격 관문",
            "",
            "| 관문 | 통과 | 실제 | 요구 |",
            "|------|------|------|------|",
        ]
    )
    for gate in report.gates:
        lines.append(f"| {gate.gate_id} | {gate.passed} | {gate.actual} | {gate.required} |")
    return "\n".join(lines) + "\n"
