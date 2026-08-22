"""Deterministic 64-trial strategy search over live-expressible portfolios."""

from __future__ import annotations

import hashlib
import json
import math
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    probabilistic_sharpe,
    probability_of_backtest_overfitting,
)
from auto_invest.analytics.global_trend import gold_total_return_factors
from auto_invest.analytics.multi_asset_trend import bond_total_return_factors
from auto_invest.analytics.risk_managed_beta import (
    MonthlyRow,
    market_total_return_factors,
    summarize,
)
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest

SCHEMA_VERSION = "1.0"
EXPECTED_CANDIDATES = 64
FACTORY_EDGE = "FACTORY_EDGE"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
_UNIVERSE = ("SPY", "IEF", "GLD")
_EXECUTION = ("SPYM", "IEF", "GLDM")
_ENSEMBLE_BATCHES = (
    (
        (3,),
        (6,),
        (9,),
        (12,),
        (15,),
        (3, 6),
        (6, 9),
        (9, 12),
        (12, 15),
        (3, 9),
        (6, 12),
        (3, 6, 9),
        (6, 9, 12),
        (3, 6, 9, 12),
        (6, 9, 12, 15),
        (3, 6, 9, 12, 15),
    ),
    (
        (2,),
        (4,),
        (8,),
        (10,),
        (22,),
        (2, 4),
        (4, 8),
        (8, 10),
        (10, 18),
        (2, 8),
        (4, 10),
        (2, 4, 8),
        (4, 8, 10),
        (2, 4, 8, 10),
        (4, 8, 10, 18),
        (2, 4, 8, 10, 18),
    ),
    (
        (5,),
        (7,),
        (11,),
        (13,),
        (17,),
        (5, 7),
        (7, 11),
        (11, 13),
        (13, 17),
        (5, 11),
        (7, 13),
        (5, 7, 11),
        (7, 11, 13),
        (5, 7, 11, 13),
        (7, 11, 13, 17),
        (5, 7, 11, 13, 17),
    ),
    (
        (14,),
        (16,),
        (18,),
        (20,),
        (24,),
        (14, 16),
        (16, 18),
        (18, 20),
        (20, 24),
        (14, 18),
        (16, 20),
        (14, 16, 18),
        (16, 18, 20),
        (14, 16, 18, 20),
        (16, 18, 20, 24),
        (14, 16, 18, 20, 24),
    ),
)
_MOMENTUM_BATCHES = (
    (3, 6, 9, 12),
    (2, 4, 8, 10),
    (5, 7, 11, 13),
    (14, 16, 18, 20),
)
MAX_BATCH_SEQUENCE = len(_ENSEMBLE_BATCHES) - 1


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class StrategyCandidate:
    candidate_id: str
    trial_index: int
    family: str
    weight_scheme: str
    top_n: int
    momentum_months: int
    rebalance_months: int
    trend_windows_months: tuple[int, ...]
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.family,
            "weight_scheme": self.weight_scheme,
            "top_n": self.top_n,
            "momentum_months": self.momentum_months,
            "rebalance_months": self.rebalance_months,
            "trend_windows_months": list(self.trend_windows_months),
            "strategy_fingerprint": self.strategy_fingerprint,
            "deploy_config_text": render_candidate_toml(self),
        }


def _candidate(index: int, family: str, *, batch_sequence: int, **params: Any) -> StrategyCandidate:
    body = {
        "family": family,
        "batch_sequence": batch_sequence,
        **params,
        "universe": _UNIVERSE,
    }
    digest = _fingerprint(body)
    provisional = StrategyCandidate(
        candidate_id=f"factory-{family}-{digest[7:19]}",
        trial_index=index,
        family=family,
        strategy_fingerprint="pending",
        **params,
    )
    config_payload = tomllib.loads(render_candidate_toml(provisional))
    config = PortfolioRebalanceConfig.model_validate(config_payload["portfolio"])
    return StrategyCandidate(
        **{
            **provisional.__dict__,
            "strategy_fingerprint": strategy_fingerprint_digest(config),
        }
    )


def generate_candidates(batch_sequence: int = 0) -> tuple[StrategyCandidate, ...]:
    if batch_sequence < 0 or batch_sequence > MAX_BATCH_SEQUENCE:
        raise ValueError(f"batch_sequence must be between 0 and {MAX_BATCH_SEQUENCE}")
    candidates: list[StrategyCandidate] = []
    ensembles = _ENSEMBLE_BATCHES[batch_sequence]
    momentum_grid = _MOMENTUM_BATCHES[batch_sequence]
    for windows in ensembles:
        candidates.append(
            _candidate(
                len(candidates) + 1,
                "trend_equal",
                batch_sequence=batch_sequence,
                weight_scheme="equal",
                top_n=3,
                momentum_months=6,
                rebalance_months=1,
                trend_windows_months=windows,
            )
        )
    for windows in ensembles:
        candidates.append(
            _candidate(
                len(candidates) + 1,
                "trend_inverse_vol",
                batch_sequence=batch_sequence,
                weight_scheme="inverse_vol",
                top_n=3,
                momentum_months=6,
                rebalance_months=1,
                trend_windows_months=windows,
            )
        )
    for lookback in momentum_grid:
        for top_n in (1, 2):
            for rebalance in (1, 3):
                candidates.append(
                    _candidate(
                        len(candidates) + 1,
                        "relative_momentum",
                        batch_sequence=batch_sequence,
                        weight_scheme="equal",
                        top_n=top_n,
                        momentum_months=lookback,
                        rebalance_months=rebalance,
                        trend_windows_months=(lookback,),
                    )
                )
    for lookback in momentum_grid:
        for top_n in (2, 3):
            for scheme in ("equal", "inverse_vol"):
                candidates.append(
                    _candidate(
                        len(candidates) + 1,
                        "defensive_low_turnover",
                        batch_sequence=batch_sequence,
                        weight_scheme=scheme,
                        top_n=top_n,
                        momentum_months=lookback,
                        rebalance_months=3,
                        trend_windows_months=ensembles[-3],
                    )
                )
    if (
        len(candidates) != EXPECTED_CANDIDATES
        or len({item.strategy_fingerprint for item in candidates}) != EXPECTED_CANDIDATES
    ):
        raise RuntimeError("strategy factory candidate contract violated")
    return tuple(candidates)


def render_candidate_toml(candidate: StrategyCandidate) -> str:
    ensemble = ", ".join(str(month * 21) for month in candidate.trend_windows_months)
    return f'''# Generated by autonomous strategy factory; no capital authorization.
[caps]
per_trade_pct = 50.0
per_symbol_pct = 60.0
global_exposure_pct = 100.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["SPYM", "IEF", "GLDM"]
accounts = ["${{KIS_ACCOUNT_NO}}"]
order_types = ["LIMIT"]
sessions = ["REGULAR"]

[account_rebalance]
enabled = true
liquidation_symbols = []
cash_buffer_pct = "0.01"

[execution]
symbol_map = {{ SPY = "SPYM", IEF = "IEF", GLD = "GLDM" }}
lot_rounding = "nearest"

[portfolio]
id = "{candidate.candidate_id}"
universe = ["SPY", "IEF", "GLD"]
weights = {{ momentum = "1.0" }}
weight_scheme = "{candidate.weight_scheme}"
top_n = {candidate.top_n}
rebalance_mode = "hold_replace"
invested_fraction = "0.99"
rebalance_every_n_sessions = {candidate.rebalance_months * 21}
lookback_bars = {max(252, candidate.momentum_months * 21, max(candidate.trend_windows_months) * 21)}
momentum_period = {candidate.momentum_months * 21}
rebalance_threshold_pct = "2.0"
min_notional_usd = "25"

[portfolio.trend_filter]
method = "sma"
lookback = {max(candidate.trend_windows_months) * 21}
on_insufficient = "cash"
ensemble_windows = [{ensemble}]
'''


def _levels(factors: list[float]) -> list[float]:
    out = [1.0]
    for factor in factors:
        out.append(out[-1] * factor)
    return out


def _candidate_factors(
    candidate: StrategyCandidate, asset_factors: list[list[float]], *, cost_bps: int
) -> list[float]:
    n = len(asset_factors[0])
    levels = [_levels(values) for values in asset_factors]
    returns = [[factor - 1.0 for factor in values] for values in asset_factors]
    weights = np.zeros(3, dtype=float)
    output: list[float] = []
    for t in range(n):
        if t % candidate.rebalance_months == 0:
            scores = []
            for index in range(3):
                lookback = candidate.momentum_months
                score = (
                    levels[index][t] / levels[index][t - lookback] - 1.0
                    if t >= lookback
                    else -math.inf
                )
                scores.append(score)
            selected = sorted(range(3), key=lambda i: (-scores[i], i))[: candidate.top_n]
            selected = [index for index in selected if scores[index] > 0.0]
            base = np.zeros(3, dtype=float)
            if selected:
                if candidate.weight_scheme == "inverse_vol":
                    inv = []
                    for index in selected:
                        history = returns[index][max(0, t - 6) : t]
                        vol = float(np.std(history, ddof=1)) if len(history) >= 2 else 0.0
                        inv.append(1.0 / vol if vol > 0.0 else 0.0)
                    total = sum(inv)
                    for index, value in zip(selected, inv, strict=True):
                        base[index] = value / total if total > 0.0 else 1.0 / len(selected)
                else:
                    for index in selected:
                        base[index] = 1.0 / len(selected)
            exposures = np.zeros(3, dtype=float)
            for index in range(3):
                signals = []
                for window in candidate.trend_windows_months:
                    signals.append(
                        t >= window
                        and levels[index][t] > float(np.mean(levels[index][t - window : t]))
                    )
                exposures[index] = sum(signals) / len(signals)
            new_weights = base * exposures
            turnover = float(np.sum(np.abs(new_weights - weights)))
            weights = new_weights
        else:
            turnover = 0.0
        gross = float(
            sum(weights[index] * asset_factors[index][t] for index in range(3))
            + (1.0 - float(np.sum(weights)))
        )
        output.append(gross * max(0.0, 1.0 - turnover * cost_bps / 10_000.0))
    return output


def _segments(returns: list[float], count: int = 10) -> list[list[float]]:
    size = len(returns) // count
    if size < 2:
        return []
    return [
        returns[index * size : (index + 1) * size if index < count - 1 else len(returns)]
        for index in range(count)
    ]


def run_strategy_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
    batch_sequence: int = 0,
    prior_trial_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if len(rows) != len(gold_levels):
        raise ValueError("rows and gold levels must align")
    candidates = generate_candidates(batch_sequence)
    dates = [row.date for row in rows[1:]]
    start = next((i for i, date in enumerate(dates) if int(date[:4]) >= 2007), len(dates))
    if start < 120 or len(dates) - start < 120:
        raise ValueError("development and holdout must each contain at least 120 months")
    assets = [
        market_total_return_factors(rows),
        bond_total_return_factors(rows),
        gold_total_return_factors(gold_levels),
    ]
    benchmark = [sum(values) / 3.0 for values in zip(*assets, strict=True)][start:]
    benchmark_stats = summarize(benchmark)
    benchmark_segment_sharpes = [
        annualized_sharpe(segment) for segment in _segments([factor - 1.0 for factor in benchmark])
    ]
    records: list[dict[str, Any]] = []
    primary_returns: list[list[float]] = []
    segment_scores: list[list[float]] = []
    for candidate in candidates:
        by_cost = {
            cost: _candidate_factors(candidate, assets, cost_bps=cost)[start:]
            for cost in (10, 25, 50)
        }
        returns25 = [factor - 1.0 for factor in by_cost[25]]
        primary_returns.append(returns25)
        segments = _segments(returns25)
        segment_sharpes = [annualized_sharpe(segment) for segment in segments]
        segment_scores.append(segment_sharpes)
        stats25 = summarize(by_cost[25])
        records.append(
            {
                "candidate_id": candidate.candidate_id,
                "strategy_fingerprint": candidate.strategy_fingerprint,
                "status": "complete",
                "sharpe_25bps": round(stats25.sharpe, 6),
                "cagr_25bps": round(stats25.cagr_pct, 6),
                "max_drawdown_25bps": round(stats25.max_dd_pct, 6),
                "calmar_25bps": None if stats25.calmar is None else round(stats25.calmar, 6),
                "total_return_50bps": round(math.prod(by_cost[50]) - 1.0, 8),
                "segment_sharpes": [round(value, 6) for value in segment_sharpes],
                "segment_wins": sum(
                    candidate_value > benchmark_value
                    for candidate_value, benchmark_value in zip(
                        segment_sharpes, benchmark_segment_sharpes, strict=True
                    )
                ),
            }
        )
    winner_index = max(
        range(len(candidates)),
        key=lambda i: (
            records[i]["sharpe_25bps"],
            records[i]["calmar_25bps"] or -math.inf,
            -records[i]["max_drawdown_25bps"],
            candidates[i].candidate_id,
        ),
    )
    winner = candidates[winner_index]
    winner_record = records[winner_index]
    current_candidate_ids = {candidate.candidate_id for candidate in candidates}
    prior_complete = [
        record
        for record in (prior_trial_records or [])
        if isinstance(record, dict)
        and record.get("status") == "complete"
        and isinstance(record.get("segment_sharpes"), list)
        and len(record["segment_sharpes"]) == 10
        and record.get("candidate_id") not in current_candidate_ids
    ]
    trial_sharpes = [float(record["sharpe_25bps"]) for record in prior_complete]
    trial_sharpes.extend(float(record["sharpe_25bps"]) for record in records)
    dsr = deflated_sharpe_from_trials(primary_returns[winner_index], trial_sharpes)
    psr = probabilistic_sharpe(
        primary_returns[winner_index], benchmark_sharpe_annual=benchmark_stats.sharpe
    )
    cumulative_segment_scores = [
        [float(value) for value in record["segment_sharpes"]] for record in prior_complete
    ]
    cumulative_segment_scores.extend(segment_scores)
    pbo = probability_of_backtest_overfitting(cumulative_segment_scores)
    win_rate = winner_record["segment_wins"] / 10.0
    gates = (
        ("complete_trials", len(records) == EXPECTED_CANDIDATES, len(records), EXPECTED_CANDIDATES),
        ("holdout_months", len(benchmark) >= 120, len(benchmark), 120),
        ("dsr", dsr is not None and dsr >= 0.95, dsr, 0.95),
        ("pbo", pbo is not None and pbo <= 0.10, pbo, 0.10),
        ("psr_vs_benchmark", psr is not None and psr >= 0.95, psr, 0.95),
        ("segment_win_rate", win_rate >= 0.60, round(win_rate, 6), 0.60),
        (
            "sharpe_superiority",
            winner_record["sharpe_25bps"] >= benchmark_stats.sharpe + 0.20,
            round(winner_record["sharpe_25bps"] - benchmark_stats.sharpe, 6),
            0.20,
        ),
        (
            "calmar_superiority",
            winner_record["calmar_25bps"] is not None
            and benchmark_stats.calmar is not None
            and winner_record["calmar_25bps"] > benchmark_stats.calmar,
            winner_record["calmar_25bps"],
            benchmark_stats.calmar,
        ),
        (
            "drawdown_defense",
            winner_record["max_drawdown_25bps"] <= benchmark_stats.max_dd_pct * 0.80,
            winner_record["max_drawdown_25bps"],
            round(benchmark_stats.max_dd_pct * 0.80, 6),
        ),
        (
            "cost_50bps_positive",
            winner_record["total_return_50bps"] > 0.0,
            winner_record["total_return_50bps"],
            0.0,
        ),
    )
    gate_rows = [
        {
            "gate_id": key,
            "passed": bool(passed),
            "actual": None if actual is None else str(actual),
            "required": str(required),
        }
        for key, passed, actual, required in gates
    ]
    passed = all(row[1] for row in gates)
    data_fp = _fingerprint(
        {"first": dates[0], "last": dates[-1], "rows": len(rows), "gold_last": gold_levels[-1]}
    )
    batch_id = (
        "strategy-factory-"
        + _fingerprint(
            {
                "data": data_fp,
                "code": code_commit,
                "grammar": SCHEMA_VERSION,
                "batch_sequence": batch_sequence,
            }
        )[7:19]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "timestamp_utc": timestamp_utc or datetime.now(UTC).isoformat(),
        "code_commit": code_commit,
        "data_fingerprint": data_fp,
        "batch_sequence": batch_sequence,
        "candidate_count": len(candidates),
        "complete_trial_count": len(records),
        "multiplicity_trial_count": len(trial_sharpes),
        "candidates": [candidate.as_dict() for candidate in candidates],
        "trial_records": records,
        "decision": {
            "verdict": FACTORY_EDGE if passed else NO_FACTORY_EDGE,
            "selected_candidate_id": winner.candidate_id if passed else None,
            "provisional_best_candidate_id": winner.candidate_id,
            "dsr": None if dsr is None else str(dsr),
            "pbo": None if pbo is None else str(pbo),
            "psr": None if psr is None else str(psr),
            "gates": gate_rows,
            "research_canary_eligible": passed,
            "selected_strategy_fingerprint": winner.strategy_fingerprint if passed else None,
            "selected_deploy_config": render_candidate_toml(winner) if passed else None,
            "next_batch_sequence": (
                batch_sequence + 1 if not passed and batch_sequence < MAX_BATCH_SEQUENCE else None
            ),
            "search_space_exhausted": not passed and batch_sequence >= MAX_BATCH_SEQUENCE,
        },
        "benchmark": benchmark_stats.as_dict(),
        "safety": ["no broker API", "no orders", "no capital change", "long-only", "no leverage"],
    }


def render_factory_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    lines = [
        "# 자동 전략 공장 최신 실행",
        "",
        f"- 판정: **{decision['verdict']}**",
        f"- 묶음: `{payload['batch_id']}`",
        f"- 탐색 순번: {payload['batch_sequence']}",
        f"- 완료 시도: {payload['complete_trial_count']}/{payload['candidate_count']}",
        f"- 누적 다중검정 시도: {payload['multiplicity_trial_count']}",
        f"- 잠정 최고 후보: `{decision['provisional_best_candidate_id']}`",
        f"- DSR: {decision['dsr']}",
        f"- PBO: {decision['pbo']}",
        f"- PSR: {decision['psr']}",
        "",
        "## 관문",
        "",
        "| 관문 | 상태 | 현재 | 기준 |",
        "|---|:---:|---:|---:|",
    ]
    for gate in decision["gates"]:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"| {gate['gate_id']} | {status} | {gate['actual']} | {gate['required']} |")
    lines.extend(
        [
            "",
            "> 이 실행은 주문·자본 변경을 하지 않는다. 모든 관문을 통과한 경우에만 "
            "별도 연구 캐너리 심사를 요청한다.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "EXPECTED_CANDIDATES",
    "FACTORY_EDGE",
    "NO_FACTORY_EDGE",
    "StrategyCandidate",
    "generate_candidates",
    "render_candidate_toml",
    "render_factory_markdown",
    "run_strategy_factory",
]
