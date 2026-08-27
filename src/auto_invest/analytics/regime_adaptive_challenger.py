"""Preregistered correlation-aware challenger for the global trend incumbent.

The module is deterministic research code. It does not import broker, order, worker, or
live-configuration modules and can never promote a strategy or move capital.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probabilistic_sharpe,
    probability_of_backtest_overfitting,
)
from auto_invest.analytics.global_trend import _cum_levels, gold_total_return_factors
from auto_invest.analytics.multi_asset_trend import bond_total_return_factors
from auto_invest.analytics.risk_managed_beta import (
    LegStats,
    MonthlyRow,
    cash_factors,
    market_total_return_factors,
    summarize,
)
from auto_invest.analytics.trend_ensemble import ensemble_in_fraction

SCHEMA_VERSION = "regime-edge-result-v1"
PREREGISTRATION_SCHEMA_VERSION = "regime-edge-preregistration-v1"
FAMILY_ID = "regime-adaptive-stock-bond-joint-weakness-v1"
INCUMBENT_ID = "globalfixed-ensemble-3-6-9-12"
COMPLETED_CANDIDATE_ID = "candidate-parallel-edge-challenger-0520a80c0525"
ENSEMBLE_WINDOWS = (3, 6, 9, 12)
CORRELATION_WINDOWS = (12, 24)
CORRELATION_THRESHOLDS = (0.0, 0.2)
WEAKNESS_LOOKBACKS = (3, 6)
DEFENSIVE_ACTIONS = ("cash", "gold")
EXPECTED_SAFETY = {
    "promotion_allowed": False,
    "orders_submitted": 0,
    "capital_changed": False,
}


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _threshold_slug(value: float) -> str:
    return f"{value:.1f}".replace("-", "m").replace(".", "p")


@dataclass(frozen=True)
class CandidateSpec:
    correlation_window_months: int
    correlation_threshold: float
    joint_weakness_lookback_months: int
    defensive_action: str

    def __post_init__(self) -> None:
        if self.correlation_window_months < 2:
            raise ValueError("correlation window must be at least two months")
        if self.joint_weakness_lookback_months < 1:
            raise ValueError("joint weakness lookback must be positive")
        if self.defensive_action not in DEFENSIVE_ACTIONS:
            raise ValueError("defensive action must be cash or gold")

    @property
    def candidate_id(self) -> str:
        return (
            f"regime-corr{self.correlation_window_months}"
            f"-thr{_threshold_slug(self.correlation_threshold)}"
            f"-weak{self.joint_weakness_lookback_months}"
            f"-{self.defensive_action}"
        )

    @property
    def fingerprint(self) -> str:
        return _canonical_digest(self.as_dict(include_identity=False))

    def as_dict(self, *, include_identity: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "correlation_window_months": self.correlation_window_months,
            "correlation_threshold": self.correlation_threshold,
            "joint_weakness_lookback_months": self.joint_weakness_lookback_months,
            "defensive_action": self.defensive_action,
        }
        if include_identity:
            payload = {
                "candidate_id": self.candidate_id,
                "candidate_fingerprint": self.fingerprint,
                **payload,
            }
        return payload


@dataclass(frozen=True)
class StrategyPath:
    dates: tuple[str, ...]
    weights: tuple[tuple[float, float, float, float], ...]
    incumbent_weights: tuple[tuple[float, float, float, float], ...]
    gross_factors: tuple[float, ...]
    incumbent_gross_factors: tuple[float, ...]
    one_way_turnover: tuple[float, ...]
    incumbent_one_way_turnover: tuple[float, ...]
    stress_active: tuple[bool, ...]


def registered_candidates() -> tuple[CandidateSpec, ...]:
    return tuple(
        CandidateSpec(window, threshold, weakness, action)
        for window, threshold, weakness, action in product(
            CORRELATION_WINDOWS,
            CORRELATION_THRESHOLDS,
            WEAKNESS_LOOKBACKS,
            DEFENSIVE_ACTIONS,
        )
    )


def _correlation(values_a: Sequence[float], values_b: Sequence[float]) -> float | None:
    if len(values_a) != len(values_b) or len(values_a) < 2:
        return None
    a = np.asarray(values_a, dtype=np.float64)
    b = np.asarray(values_b, dtype=np.float64)
    if float(np.std(a)) <= 0.0 or float(np.std(b)) <= 0.0:
        return None
    value = float(np.corrcoef(a, b)[0, 1])
    return value if math.isfinite(value) else None


def _one_way_turnover(
    weights: Sequence[tuple[float, float, float, float]],
) -> tuple[float, ...]:
    previous = (0.0, 0.0, 0.0, 1.0)
    output: list[float] = []
    for current in weights:
        output.append(0.5 * sum(abs(a - b) for a, b in zip(current, previous, strict=True)))
        previous = current
    return tuple(output)


def build_strategy_path(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    candidate: CandidateSpec,
) -> StrategyPath:
    if len(rows) != len(gold_levels):
        raise ValueError("gold_levels must align 1:1 with rows")
    if len(rows) < max(ENSEMBLE_WINDOWS) + 2:
        raise ValueError("insufficient monthly observations")

    equity = market_total_return_factors(rows)
    bond = bond_total_return_factors(rows)
    gold = gold_total_return_factors(gold_levels)
    cash = cash_factors(rows)
    if not (len(equity) == len(bond) == len(gold) == len(cash)):
        raise ValueError("asset factor length mismatch")

    equity_signal = ensemble_in_fraction([row.price for row in rows], ENSEMBLE_WINDOWS)
    bond_levels = _cum_levels(bond)
    bond_signal = ensemble_in_fraction(bond_levels, ENSEMBLE_WINDOWS)
    gold_signal = ensemble_in_fraction(gold_levels, ENSEMBLE_WINDOWS)
    equity_total_levels = _cum_levels(equity)

    equity_returns = [factor - 1.0 for factor in equity]
    bond_returns = [factor - 1.0 for factor in bond]
    incumbent_weights: list[tuple[float, float, float, float]] = []
    challenger_weights: list[tuple[float, float, float, float]] = []
    stress_flags: list[bool] = []

    for index in range(len(equity)):
        stock_weight = equity_signal[index] / 3.0
        bond_weight = bond_signal[index] / 3.0
        gold_weight = gold_signal[index] / 3.0
        base = (
            stock_weight,
            bond_weight,
            gold_weight,
            1.0 - stock_weight - bond_weight - gold_weight,
        )
        incumbent_weights.append(base)

        correlation = None
        if index >= candidate.correlation_window_months:
            correlation = _correlation(
                equity_returns[index - candidate.correlation_window_months : index],
                bond_returns[index - candidate.correlation_window_months : index],
            )
        lookback = candidate.joint_weakness_lookback_months
        jointly_weak = index >= lookback and (
            equity_total_levels[index] / equity_total_levels[index - lookback] - 1.0 <= 0.0
            and bond_levels[index] / bond_levels[index - lookback] - 1.0 <= 0.0
        )
        stress = (
            correlation is not None
            and correlation >= candidate.correlation_threshold
            and jointly_weak
        )
        stress_flags.append(stress)
        if not stress:
            challenger_weights.append(base)
            continue

        removed = stock_weight + bond_weight
        if (
            candidate.defensive_action == "gold"
            and index >= lookback
            and gold_levels[index] / gold_levels[index - lookback] - 1.0 > 0.0
        ):
            challenger_weights.append((0.0, 0.0, gold_weight + removed, base[3]))
        else:
            challenger_weights.append((0.0, 0.0, gold_weight, base[3] + removed))

    challenger_gross = []
    incumbent_gross = []
    for index, (challenger, incumbent) in enumerate(
        zip(challenger_weights, incumbent_weights, strict=True)
    ):
        period_factors = (equity[index], bond[index], gold[index], cash[index])
        challenger_gross.append(
            sum(weight * factor for weight, factor in zip(challenger, period_factors, strict=True))
        )
        incumbent_gross.append(
            sum(weight * factor for weight, factor in zip(incumbent, period_factors, strict=True))
        )

    return StrategyPath(
        dates=tuple(row.date[:7] for row in rows[1:]),
        weights=tuple(challenger_weights),
        incumbent_weights=tuple(incumbent_weights),
        gross_factors=tuple(challenger_gross),
        incumbent_gross_factors=tuple(incumbent_gross),
        one_way_turnover=_one_way_turnover(challenger_weights),
        incumbent_one_way_turnover=_one_way_turnover(incumbent_weights),
        stress_active=tuple(stress_flags),
    )


def apply_cost_model(
    gross_factors: Sequence[float],
    one_way_turnover: Sequence[float],
    *,
    annual_fixed_bps: int,
    turnover_bps: int,
) -> tuple[float, ...]:
    if len(gross_factors) != len(one_way_turnover):
        raise ValueError("gross factor and turnover length mismatch")
    if annual_fixed_bps < 0 or turnover_bps < 0:
        raise ValueError("costs must be nonnegative")
    monthly_fixed = annual_fixed_bps / 10_000.0 / 12.0
    return tuple(
        factor * max(0.0, 1.0 - monthly_fixed - turnover * turnover_bps / 10_000.0)
        for factor, turnover in zip(gross_factors, one_way_turnover, strict=True)
    )


def _stats(factors: Sequence[float]) -> dict[str, Any]:
    result: LegStats = summarize(list(factors))
    return {
        "n_months": result.n_months,
        "cagr_pct": round(result.cagr_pct, 6),
        "vol_pct": round(result.vol_pct, 6),
        "sharpe": round(result.sharpe, 6),
        "max_drawdown_pct": round(result.max_dd_pct, 6),
        "calmar": None if result.calmar is None else round(result.calmar, 6),
    }


def _segments(values: Sequence[float], count: int) -> list[list[float]]:
    if len(values) < count * 2:
        raise ValueError(f"at least {count * 2} observations required for {count} segments")
    return [list(segment) for segment in np.array_split(np.asarray(values), count)]


def _segment_sharpes(values: Sequence[float], count: int) -> list[float]:
    return [annualized_sharpe(segment) for segment in _segments(values, count)]


def _float_or_none(value: Any) -> float | None:
    return None if value is None else round(float(value), 6)


def _validate_preregistration(contract: Mapping[str, Any]) -> None:
    expected_grid = {
        "correlation_window_months": [12, 24],
        "correlation_threshold": [0.0, 0.2],
        "joint_weakness_lookback_months": [3, 6],
        "defensive_action": ["cash", "gold"],
    }
    exact = {
        "schema_version": PREREGISTRATION_SCHEMA_VERSION,
        "family_id": FAMILY_ID,
        "incumbent_id": INCUMBENT_ID,
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "candidate_count": 16,
    }
    for key, expected in exact.items():
        if contract.get(key) != expected:
            raise ValueError(f"preregistration {key} mismatch")
    if contract.get("candidate_grid") != expected_grid:
        raise ValueError("preregistration candidate_grid mismatch")
    if contract.get("split") != {
        "development_end": "2006-12",
        "embargo_month": "2007-01",
        "holdout_start": "2007-02",
    }:
        raise ValueError("preregistration split mismatch")
    if contract.get("safety") != EXPECTED_SAFETY:
        raise ValueError("preregistration safety mismatch")


def _split_indexes(
    dates: Sequence[str], contract: Mapping[str, Any]
) -> tuple[list[int], list[int]]:
    split = contract["split"]
    development = [index for index, date in enumerate(dates) if date <= split["development_end"]]
    holdout = [index for index, date in enumerate(dates) if date >= split["holdout_start"]]
    embargo = [date for date in dates if date == split["embargo_month"]]
    if not development or len(holdout) < 60 or not embargo:
        raise ValueError("insufficient data for frozen development, embargo, and holdout split")
    if set(development) & set(holdout):
        raise ValueError("development and holdout overlap")
    return development, holdout


def _take(values: Sequence[float], indexes: Sequence[int]) -> list[float]:
    return [values[index] for index in indexes]


def _delayed_holdout_factors(
    path: StrategyPath,
    holdout_indexes: Sequence[int],
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    annual_fixed_bps: int,
    turnover_bps: int,
) -> tuple[float, ...]:
    equity = market_total_return_factors(rows)
    bond = bond_total_return_factors(rows)
    gold = gold_total_return_factors(gold_levels)
    cash = cash_factors(rows)
    delayed = ((0.0, 0.0, 0.0, 1.0), *path.weights[:-1])
    gross = tuple(
        sum(
            weight * factor
            for weight, factor in zip(
                weights,
                (equity[index], bond[index], gold[index], cash[index]),
                strict=True,
            )
        )
        for index, weights in enumerate(delayed)
    )
    net = apply_cost_model(
        gross,
        _one_way_turnover(delayed),
        annual_fixed_bps=annual_fixed_bps,
        turnover_bps=turnover_bps,
    )
    return tuple(_take(net, holdout_indexes))


def evaluate_regime_challenger(
    rows: list[MonthlyRow], gold_levels: list[float], contract: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_preregistration(contract)
    candidates = registered_candidates()
    paths = {
        candidate.candidate_id: build_strategy_path(rows, gold_levels, candidate)
        for candidate in candidates
    }
    dates = next(iter(paths.values())).dates
    development_indexes, holdout_indexes = _split_indexes(dates, contract)
    costs = contract["cost_model"]
    annual_fixed_bps = int(costs["annual_fixed_bps"])
    principal_bps = int(costs["principal_one_way_turnover_bps"])

    development_rows: list[dict[str, Any]] = []
    development_returns: list[list[float]] = []
    development_segment_scores: list[list[float]] = []
    net_by_candidate: dict[str, tuple[float, ...]] = {}
    for candidate in candidates:
        path = paths[candidate.candidate_id]
        net = apply_cost_model(
            path.gross_factors,
            path.one_way_turnover,
            annual_fixed_bps=annual_fixed_bps,
            turnover_bps=principal_bps,
        )
        net_by_candidate[candidate.candidate_id] = net
        factors = _take(net, development_indexes)
        returns = [factor - 1.0 for factor in factors]
        stats = _stats(factors)
        development_returns.append(returns)
        development_segment_scores.append(_segment_sharpes(returns, 8))
        development_rows.append({**candidate.as_dict(), "metrics": stats})

    development_rows.sort(
        key=lambda row: (
            -float(row["metrics"]["sharpe"]),
            -float(row["metrics"]["cagr_pct"]),
            float(row["metrics"]["max_drawdown_pct"]),
            str(row["candidate_id"]),
        )
    )
    selected_id = str(development_rows[0]["candidate_id"])
    selected_index = next(
        index for index, item in enumerate(candidates) if item.candidate_id == selected_id
    )
    selected = candidates[selected_index]
    selected_path = paths[selected_id]
    candidate_holdout = _take(net_by_candidate[selected_id], holdout_indexes)
    incumbent_full = apply_cost_model(
        selected_path.incumbent_gross_factors,
        selected_path.incumbent_one_way_turnover,
        annual_fixed_bps=annual_fixed_bps,
        turnover_bps=principal_bps,
    )
    incumbent_holdout = _take(incumbent_full, holdout_indexes)
    active_returns = [
        candidate / incumbent - 1.0
        for candidate, incumbent in zip(candidate_holdout, incumbent_holdout, strict=True)
    ]
    family_pbo = probability_of_backtest_overfitting(development_segment_scores)
    holdout_psr = probabilistic_sharpe(active_returns)
    trial_sharpes = [annualized_sharpe(returns) for returns in development_returns]
    effective_trials = effective_independent_trials(development_returns)
    selected_dsr = deflated_sharpe_from_trials(
        development_returns[selected_index],
        trial_sharpes,
        effective_trial_count=effective_trials,
    )
    selected_dev_psr = probabilistic_sharpe(development_returns[selected_index])
    bonferroni_p = (
        None
        if selected_dev_psr is None
        else min(1.0, (1.0 - float(selected_dev_psr)) * len(candidates))
    )

    candidate_stats = _stats(candidate_holdout)
    incumbent_stats = _stats(incumbent_holdout)
    recent_segments = []
    for number, segment in enumerate(np.array_split(np.arange(len(holdout_indexes)), 3), start=1):
        indexes = [int(index) for index in segment]
        challenger_segment = [candidate_holdout[index] for index in indexes]
        incumbent_segment = [incumbent_holdout[index] for index in indexes]
        challenger_stats = _stats(challenger_segment)
        incumbent_segment_stats = _stats(incumbent_segment)
        recent_segments.append(
            {
                "segment": number,
                "start": dates[holdout_indexes[indexes[0]]],
                "end": dates[holdout_indexes[indexes[-1]]],
                "candidate_sharpe": challenger_stats["sharpe"],
                "incumbent_sharpe": incumbent_segment_stats["sharpe"],
                "candidate_won": challenger_stats["sharpe"] > incumbent_segment_stats["sharpe"],
            }
        )
    recent_wins = sum(bool(item["candidate_won"]) for item in recent_segments)
    latest_candidate = _stats(candidate_holdout[-60:])
    latest_incumbent = _stats(incumbent_holdout[-60:])
    annual_turnover = round(
        float(np.mean(_take(selected_path.one_way_turnover, holdout_indexes))) * 12.0,
        6,
    )

    cost_diagnostics: dict[str, Any] = {}
    for turnover_bps in (principal_bps, *costs["diagnostic_one_way_turnover_bps"]):
        candidate_net = apply_cost_model(
            selected_path.gross_factors,
            selected_path.one_way_turnover,
            annual_fixed_bps=annual_fixed_bps,
            turnover_bps=int(turnover_bps),
        )
        incumbent_net = apply_cost_model(
            selected_path.incumbent_gross_factors,
            selected_path.incumbent_one_way_turnover,
            annual_fixed_bps=annual_fixed_bps,
            turnover_bps=int(turnover_bps),
        )
        cost_diagnostics[f"turnover_{int(turnover_bps)}bps"] = {
            "candidate": _stats(_take(candidate_net, holdout_indexes)),
            "incumbent": _stats(_take(incumbent_net, holdout_indexes)),
        }

    thresholds = contract["gates"]
    gates = {
        "family_pbo": family_pbo is not None
        and float(family_pbo) <= float(thresholds["maximum_family_pbo"]),
        "holdout_active_psr": holdout_psr is not None
        and float(holdout_psr) >= float(thresholds["minimum_holdout_active_psr"]),
        "holdout_cagr": candidate_stats["cagr_pct"] > incumbent_stats["cagr_pct"],
        "holdout_sharpe": candidate_stats["sharpe"] > incumbent_stats["sharpe"],
        "holdout_drawdown": candidate_stats["max_drawdown_pct"]
        <= incumbent_stats["max_drawdown_pct"],
        "recent_segment_wins": recent_wins >= int(thresholds["minimum_recent_segment_sharpe_wins"]),
        "latest_60_month_sharpe": latest_candidate["sharpe"] > latest_incumbent["sharpe"],
        "annual_turnover": annual_turnover <= float(thresholds["maximum_annual_one_way_turnover"]),
    }
    verdict = "RESEARCH_EDGE" if all(gates.values()) else "NO_RESEARCH_EDGE"

    positive_control = [0.002 + 0.0001 * ((index % 5) - 2) for index in range(len(active_returns))]
    delayed = _delayed_holdout_factors(
        selected_path,
        holdout_indexes,
        rows,
        gold_levels,
        annual_fixed_bps=annual_fixed_bps,
        turnover_bps=principal_bps,
    )
    fingerprint_payload = {
        "dates": dates,
        "equity": market_total_return_factors(rows),
        "bond": bond_total_return_factors(rows),
        "gold": gold_total_return_factors(gold_levels),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "family_id": FAMILY_ID,
        "incumbent_id": INCUMBENT_ID,
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "contract_digest": _canonical_digest(contract),
        "input_digest": _canonical_digest(fingerprint_payload),
        "candidate_count": len(candidates),
        "candidate_registry": [candidate.as_dict() for candidate in candidates],
        "selected_candidate_id": selected_id,
        "selected_candidate": selected.as_dict(),
        "selection_rule": list(contract["selection_order"]),
        "split": {
            **dict(contract["split"]),
            "development_start": dates[development_indexes[0]],
            "holdout_end": dates[holdout_indexes[-1]],
            "development_months": len(development_indexes),
            "holdout_months": len(holdout_indexes),
            "overlap_months": 0,
        },
        "development": {
            "family_pbo": _float_or_none(family_pbo),
            "selected_dsr_diagnostic": _float_or_none(selected_dsr),
            "selected_raw_bonferroni_adjusted_p_diagnostic": _float_or_none(bonferroni_p),
            "effective_trial_count": _float_or_none(effective_trials),
            "candidates_by_selection_order": development_rows,
        },
        "holdout": {
            "active_return_psr": _float_or_none(holdout_psr),
            "candidate": candidate_stats,
            "incumbent": incumbent_stats,
            "annual_one_way_turnover": annual_turnover,
            "stress_months": sum(selected_path.stress_active[index] for index in holdout_indexes),
        },
        "recent_three_segments": {
            "wins": recent_wins,
            "required_wins": int(thresholds["minimum_recent_segment_sharpe_wins"]),
            "segments": recent_segments,
        },
        "latest_60_months": {
            "candidate": latest_candidate,
            "incumbent": latest_incumbent,
        },
        "cost_model": dict(costs),
        "cost_diagnostics": cost_diagnostics,
        "diagnostic_controls": {
            "negative_control_incumbent_vs_itself_psr": None,
            "negative_control_passed": False,
            "planted_positive_active_psr": _float_or_none(probabilistic_sharpe(positive_control)),
            "planted_positive_detected": bool(
                probabilistic_sharpe(positive_control) is not None
                and float(probabilistic_sharpe(positive_control)) >= 0.95
            ),
            "one_month_delayed_holdout": _stats(delayed),
        },
        "gates": gates,
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "verdict": verdict,
        "multiplicity": dict(contract["multiplicity"]),
        "safety": dict(EXPECTED_SAFETY),
    }


def validate_report_payload(payload: Mapping[str, Any], contract: Mapping[str, Any]) -> bool:
    _validate_preregistration(contract)
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("family_id") != FAMILY_ID:
        raise ValueError("result identity mismatch")
    if payload.get("candidate_count") != 16:
        raise ValueError("candidate_count mismatch")
    expected_registry = [candidate.as_dict() for candidate in registered_candidates()]
    if payload.get("candidate_registry") != expected_registry:
        raise ValueError("candidate registry mismatch")
    if payload.get("contract_digest") != _canonical_digest(contract):
        raise ValueError("contract digest mismatch")
    if payload.get("safety") != EXPECTED_SAFETY:
        raise ValueError("safety boundary mismatch")
    if payload.get("multiplicity") != contract.get("multiplicity"):
        raise ValueError("multiplicity mismatch")
    selected = payload.get("selected_candidate_id")
    if selected not in {candidate.candidate_id for candidate in registered_candidates()}:
        raise ValueError("selected candidate mismatch")
    gates = payload.get("gates")
    if (
        not isinstance(gates, Mapping)
        or set(gates)
        != {
            "family_pbo",
            "holdout_active_psr",
            "holdout_cagr",
            "holdout_sharpe",
            "holdout_drawdown",
            "recent_segment_wins",
            "latest_60_month_sharpe",
            "annual_turnover",
        }
        or not all(isinstance(value, bool) for value in gates.values())
    ):
        raise ValueError("gate set mismatch")
    expected_verdict = "RESEARCH_EDGE" if all(gates.values()) else "NO_RESEARCH_EDGE"
    if payload.get("verdict") != expected_verdict:
        raise ValueError("verdict does not match gates")
    split = payload.get("split")
    if not isinstance(split, Mapping) or split.get("overlap_months") != 0:
        raise ValueError("split overlap mismatch")
    return True


def report_markdown(payload: Mapping[str, Any]) -> str:
    holdout = payload["holdout"]
    candidate = holdout["candidate"]
    incumbent = holdout["incumbent"]
    recent = payload["recent_three_segments"]
    latest = payload["latest_60_months"]
    split = payload["split"]
    period_summary = (
        f"{split['development_start']}~{split['development_end']} / "
        f"{split['embargo_month']} / {split['holdout_start']}~{split['holdout_end']}"
    )
    candidate_summary = (
        f"{candidate['cagr_pct']:.3f}% / {candidate['sharpe']:.3f} / "
        f"{candidate['max_drawdown_pct']:.3f}%"
    )
    incumbent_summary = (
        f"{incumbent['cagr_pct']:.3f}% / {incumbent['sharpe']:.3f} / "
        f"{incumbent['max_drawdown_pct']:.3f}%"
    )
    latest_summary = (
        f"후보 {latest['candidate']['sharpe']:.3f} / 기존 {latest['incumbent']['sharpe']:.3f}"
    )
    lines = [
        "# 국면 대응 전략군 최신 결과",
        "",
        f"> 연구 판정: **{payload['verdict']}**",
        "",
        "## 사전등록과 선택",
        "",
        f"- 전략군: `{payload['family_id']}`",
        f"- 고정 후보 수: {payload['candidate_count']}개",
        f"- 개발기간 선택 후보: `{payload['selected_candidate_id']}`",
        f"- 개발/엠바고/최종검증: {period_summary}",
        "",
        "## 최종 검증",
        "",
        f"- 가족 PBO: {payload['development']['family_pbo']}",
        f"- 기준 대비 능동수익 PSR: {holdout['active_return_psr']}",
        f"- 후보 CAGR/샤프/최대낙폭: {candidate_summary}",
        f"- 기존 전략 CAGR/샤프/최대낙폭: {incumbent_summary}",
        f"- 최근 3구간 샤프 승리: {recent['wins']}/{len(recent['segments'])}",
        f"- 최근 60개월 샤프: {latest_summary}",
        f"- 연 편도 회전율: {holdout['annual_one_way_turnover']:.3f}배",
        f"- 실패 관문: {', '.join(payload['failed_gates']) if payload['failed_gates'] else '없음'}",
        "",
        "## 안전 경계",
        "",
        "- 실제 주문: 0건",
        "- 자본 변경: 없음",
        "- 라이브 승격: 금지",
        "- 통과하더라도 다음 단계는 별도 종이거래 전진 검증",
    ]
    return "\n".join(lines)


__all__ = [
    "CandidateSpec",
    "StrategyPath",
    "apply_cost_model",
    "build_strategy_path",
    "evaluate_regime_challenger",
    "registered_candidates",
    "report_markdown",
    "validate_report_payload",
]
