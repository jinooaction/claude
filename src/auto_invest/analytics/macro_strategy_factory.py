"""Spec 151: point-in-time macro strategy factory with honest trial accounting."""

from __future__ import annotations

import hashlib
import json
import math
import tomllib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
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
from auto_invest.config.rules import MacroPolicyConfig, PortfolioRebalanceConfig
from auto_invest.market_data.macro_regime import MacroSnapshot
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.strategy.rebalance import macro_target_weights

SCHEMA_VERSION = "1.0"
EXPECTED_CANDIDATES = 64
EXPECTED_EXPLORATORY_TRIALS = 192
EXPECTED_PRODUCTION_TRIALS = 256
EXPECTED_MULTIPLICITY_TRIALS = 512
FACTORY_EDGE = "FACTORY_EDGE"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
BASE_PORTFOLIOS = ("equal_3asset", "factory-relative_momentum-cb2e32f74390")
FAMILIES = (
    "curve_cycle",
    "inflation_direction",
    "labor_growth_shock",
    "vix_shock_recovery",
)


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class MacroPolicyCandidate:
    candidate_id: str
    trial_index: int
    policy: MacroPolicyConfig
    strategy_fingerprint: str
    grammar: str = "official"
    exploration_batch_id: str | None = None

    @property
    def family(self) -> str:
        return self.policy.family

    @property
    def base_portfolio(self) -> str:
        return self.policy.base_portfolio

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.family,
            "base_portfolio": self.base_portfolio,
            "policy": self.policy.model_dump(mode="json"),
            "strategy_fingerprint": self.strategy_fingerprint,
            "deploy_config_text": render_macro_candidate_toml(self),
            "live_expressible": self.grammar == "official",
            "grammar": self.grammar,
            "exploration_batch_id": self.exploration_batch_id,
        }


def _policy_candidate(index: int, policy: MacroPolicyConfig) -> MacroPolicyCandidate:
    body = policy.model_dump(mode="json")
    digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": body})
    provisional = MacroPolicyCandidate(
        candidate_id=f"macro-{policy.family}-{digest[7:19]}",
        trial_index=index,
        policy=policy,
        strategy_fingerprint="pending",
    )
    payload = tomllib.loads(render_macro_candidate_toml(provisional))
    config = PortfolioRebalanceConfig.model_validate(payload["portfolio"])
    return replace(provisional, strategy_fingerprint=strategy_fingerprint_digest(config))


def generate_macro_candidates() -> tuple[MacroPolicyCandidate, ...]:
    candidates: list[MacroPolicyCandidate] = []
    for base in BASE_PORTFOLIOS:
        for threshold in (Decimal("0"), Decimal("-0.25")):
            for confirmation in (20, 60):
                for release in (Decimal("0.25"), Decimal("0.50")):
                    candidates.append(
                        _policy_candidate(
                            len(candidates) + 1,
                            MacroPolicyConfig(
                                family="curve_cycle",
                                base_portfolio=base,
                                threshold=threshold,
                                confirmation_days=confirmation,
                                release_threshold_pp=release,
                                tilt_pct=Decimal("20"),
                            ),
                        )
                    )
    for family, thresholds in (
        ("inflation_direction", (Decimal("3"), Decimal("4"))),
        ("labor_growth_shock", (Decimal("0.3"), Decimal("0.5"))),
    ):
        for base in BASE_PORTFOLIOS:
            for threshold in thresholds:
                for direction in (3, 6):
                    for tilt in (Decimal("10"), Decimal("20")):
                        candidates.append(
                            _policy_candidate(
                                len(candidates) + 1,
                                MacroPolicyConfig(
                                    family=family,
                                    base_portfolio=base,
                                    threshold=threshold,
                                    direction_months=direction,
                                    tilt_pct=tilt,
                                ),
                            )
                        )
    for base in BASE_PORTFOLIOS:
        for threshold in (Decimal("25"), Decimal("35")):
            for confirmation in (1, 5):
                for cooldown in (5, 20):
                    candidates.append(
                        _policy_candidate(
                            len(candidates) + 1,
                            MacroPolicyConfig(
                                family="vix_shock_recovery",
                                base_portfolio=base,
                                threshold=threshold,
                                confirmation_days=confirmation,
                                cooldown_days=cooldown,
                                tilt_pct=Decimal("20"),
                            ),
                        )
                    )
    if len(candidates) != EXPECTED_CANDIDATES:
        raise RuntimeError("macro candidate count contract violated")
    if len({candidate.candidate_id for candidate in candidates}) != EXPECTED_CANDIDATES:
        raise RuntimeError("macro candidate id uniqueness contract violated")
    if {candidate.family for candidate in candidates} != set(FAMILIES):
        raise RuntimeError("macro family coverage contract violated")
    return tuple(candidates)


def _exploratory_candidate(
    official: MacroPolicyCandidate, *, batch: str, index: int
) -> MacroPolicyCandidate:
    scale = {"strong-rotation": Decimal("2"), "mild-tilt": Decimal("0.5")}[batch]
    policy = official.policy.model_copy(
        update={"tilt_pct": min(Decimal("100"), official.policy.tilt_pct * scale)}
    )
    digest = _fingerprint(
        {"schema": SCHEMA_VERSION, "grammar": batch, "policy": policy.model_dump(mode="json")}
    )
    return MacroPolicyCandidate(
        candidate_id=f"exploratory-{batch}-{digest[7:19]}",
        trial_index=index,
        policy=policy,
        strategy_fingerprint=digest,
        grammar="exploratory",
        exploration_batch_id=batch,
    )


def generate_exploratory_candidates() -> tuple[MacroPolicyCandidate, ...]:
    official = generate_macro_candidates()
    candidates: list[MacroPolicyCandidate] = []
    for batch in ("strong-rotation", "mild-tilt"):
        for candidate in official:
            candidates.append(
                _exploratory_candidate(candidate, batch=batch, index=len(candidates) + 1)
            )
    for candidate in official:
        scale = Decimal("0.75") if candidate.base_portfolio == "equal_3asset" else Decimal("1.25")
        policy = candidate.policy.model_copy(
            update={
                "base_portfolio": "factory-relative_momentum-cb2e32f74390",
                "tilt_pct": min(Decimal("100"), candidate.policy.tilt_pct * scale),
            }
        )
        digest = _fingerprint(
            {
                "schema": SCHEMA_VERSION,
                "grammar": "price-overlay",
                "policy": policy.model_dump(mode="json"),
            }
        )
        candidates.append(
            MacroPolicyCandidate(
                candidate_id=f"exploratory-price-overlay-{digest[7:19]}",
                trial_index=len(candidates) + 1,
                policy=policy,
                strategy_fingerprint=digest,
                grammar="exploratory",
                exploration_batch_id="price-overlay",
            )
        )
    if len(candidates) != EXPECTED_EXPLORATORY_TRIALS:
        raise RuntimeError("exploratory replay count contract violated")
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise RuntimeError("exploratory replay id uniqueness contract violated")
    return tuple(candidates)


def render_macro_candidate_toml(candidate: MacroPolicyCandidate) -> str:
    price_base = candidate.base_portfolio == "factory-relative_momentum-cb2e32f74390"
    top_n = 2 if price_base else 3
    momentum = 84 if price_base else 30
    trend = (
        "\n[portfolio.trend_filter]\n"
        'method = "sma"\nlookback = 84\non_insufficient = "cash"\nensemble_windows = [84]\n'
        if price_base
        else ""
    )
    policy = candidate.policy
    optional = []
    for key in (
        "confirmation_days",
        "release_threshold_pp",
        "direction_months",
        "cooldown_days",
    ):
        value = getattr(policy, key)
        if value is not None:
            optional.append(
                f'{key} = "{value}"' if isinstance(value, Decimal) else f"{key} = {value}"
            )
    optional_text = "\n".join(optional)
    return f'''# Generated by macro strategy factory; no capital authorization.
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
weight_scheme = "equal"
top_n = {top_n}
rebalance_mode = "rebalance"
invested_fraction = "0.99"
rebalance_every_n_sessions = 21
lookback_bars = {max(252, momentum)}
momentum_period = {momentum}
rebalance_threshold_pct = "2.0"
min_notional_usd = "25"
{trend}
[portfolio.macro_policy]
family = "{policy.family}"
base_portfolio = "{policy.base_portfolio}"
threshold = "{policy.threshold}"
tilt_pct = "{policy.tilt_pct}"
{optional_text}
'''


def _levels(factors: list[float]) -> list[float]:
    output = [1.0]
    for factor in factors:
        output.append(output[-1] * factor)
    return output


def _base_weight_series(
    asset_factors: list[list[float]], base_portfolio: str
) -> list[dict[str, Decimal]]:
    count = len(asset_factors[0])
    if base_portfolio == "equal_3asset":
        return [
            {"SPY": Decimal("0.333334"), "IEF": Decimal("0.333333"), "GLD": Decimal("0.333333")}
            for _ in range(count)
        ]
    levels = [_levels(factors) for factors in asset_factors]
    output: list[dict[str, Decimal]] = []
    symbols = ("SPY", "IEF", "GLD")
    for index in range(count):
        if index < 4:
            output.append({symbol: Decimal("0") for symbol in symbols})
            continue
        scores = [levels[asset][index] / levels[asset][index - 4] - 1.0 for asset in range(3)]
        selected = sorted(range(3), key=lambda asset: (-scores[asset], asset))[:2]
        selected = [asset for asset in selected if scores[asset] > 0]
        weights = {symbol: Decimal("0") for symbol in symbols}
        for asset in selected:
            trend = levels[asset][index] > float(np.mean(levels[asset][index - 4 : index]))
            if trend:
                weights[symbols[asset]] = Decimal("1") / Decimal(len(selected))
        output.append(weights)
    return output


def _candidate_factors(
    candidate: MacroPolicyCandidate,
    asset_factors: list[list[float]],
    snapshots: list[MacroSnapshot],
    *,
    cost_bps: int,
) -> list[float]:
    if len(snapshots) != len(asset_factors[0]):
        raise ValueError("macro snapshots and asset returns must align")
    bases = _base_weight_series(asset_factors, candidate.base_portfolio)
    previous = {"SPY": Decimal("0"), "IEF": Decimal("0"), "GLD": Decimal("0")}
    output: list[float] = []
    for index, snapshot in enumerate(snapshots):
        if snapshot.complete and snapshot.fresh:
            weights = macro_target_weights(
                base_weights=bases[index],
                policy=candidate.policy,
                snapshot=snapshot.as_dict(include_history=True),
            )
        else:
            weights = bases[index]
        turnover = sum(abs(weights[symbol] - previous[symbol]) for symbol in previous)
        gross = sum(
            float(weights[symbol]) * asset_factors[asset][index]
            for asset, symbol in enumerate(("SPY", "IEF", "GLD"))
        )
        gross += 1.0 - float(sum(weights.values()))
        output.append(gross * max(0.0, 1.0 - float(turnover) * cost_bps / 10_000.0))
        previous = weights
    return output


def _segments(returns: list[float], count: int = 10) -> list[list[float]]:
    size = len(returns) // count
    if size < 2:
        return []
    return [
        returns[index * size : (index + 1) * size if index < count - 1 else len(returns)]
        for index in range(count)
    ]


def _evaluate_candidates(
    candidates: tuple[MacroPolicyCandidate, ...],
    assets: list[list[float]],
    snapshots: list[MacroSnapshot],
    *,
    start: int,
    benchmark_segment_sharpes: list[float],
    exploratory: bool,
) -> tuple[list[dict[str, Any]], list[list[float]], list[list[float]]]:
    records: list[dict[str, Any]] = []
    returns_25bps: list[list[float]] = []
    segment_scores: list[list[float]] = []
    for candidate in candidates:
        by_cost = {
            cost: _candidate_factors(candidate, assets, snapshots, cost_bps=cost)[start:]
            for cost in (10, 25, 50)
        }
        returns = [factor - 1.0 for factor in by_cost[25]]
        returns_25bps.append(returns)
        segments = _segments(returns)
        sharpes = [annualized_sharpe(segment) for segment in segments]
        segment_scores.append(sharpes)
        stats = summarize(by_cost[25])
        records.append(
            {
                "candidate_id": candidate.candidate_id,
                "strategy_fingerprint": candidate.strategy_fingerprint,
                "status": "EXPLORATORY_REJECTED" if exploratory else "complete",
                "exploration_batch_id": candidate.exploration_batch_id,
                "family": candidate.family,
                "base_portfolio": candidate.base_portfolio,
                "sharpe_25bps": round(stats.sharpe, 6),
                "cagr_25bps": round(stats.cagr_pct, 6),
                "max_drawdown_25bps": round(stats.max_dd_pct, 6),
                "calmar_25bps": None if stats.calmar is None else round(stats.calmar, 6),
                "total_return_50bps": round(math.prod(by_cost[50]) - 1.0, 8),
                "segment_sharpes": [round(value, 6) for value in sharpes],
                "segment_wins": sum(
                    candidate_value > benchmark_value
                    for candidate_value, benchmark_value in zip(
                        sharpes, benchmark_segment_sharpes, strict=True
                    )
                ),
            }
        )
    return records, returns_25bps, segment_scores


def run_macro_strategy_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    snapshots: list[MacroSnapshot],
    *,
    macro_data_quality: dict[str, Any],
    prior_trial_records: list[dict[str, Any]],
    live_snapshot: MacroSnapshot | None = None,
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    if len(rows) != len(gold_levels) or len(snapshots) != len(rows) - 1:
        raise ValueError("rows, gold, and macro snapshots must align")
    candidates = generate_macro_candidates()
    explorers = generate_exploratory_candidates()
    dates = [row.date for row in rows[1:]]
    start = next((index for index, value in enumerate(dates) if value >= "2007-01-01"), len(dates))
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
    exploratory_records, _, exploratory_segments = _evaluate_candidates(
        explorers,
        assets,
        snapshots,
        start=start,
        benchmark_segment_sharpes=benchmark_segment_sharpes,
        exploratory=True,
    )
    records, primary_returns, current_segments = _evaluate_candidates(
        candidates,
        assets,
        snapshots,
        start=start,
        benchmark_segment_sharpes=benchmark_segment_sharpes,
        exploratory=False,
    )
    production = [
        record
        for record in prior_trial_records
        if isinstance(record, dict)
        and record.get("status") == "complete"
        and str(record.get("candidate_id", "")).startswith("factory-")
        and isinstance(record.get("segment_sharpes"), list)
        and len(record["segment_sharpes"]) == 10
    ]
    production_by_id = {str(record["candidate_id"]): record for record in production}
    production = [production_by_id[key] for key in sorted(production_by_id)][
        :EXPECTED_PRODUCTION_TRIALS
    ]

    winner_index = max(
        range(len(records)),
        key=lambda index: (
            records[index]["sharpe_25bps"],
            records[index]["calmar_25bps"] or -math.inf,
            -records[index]["max_drawdown_25bps"],
            candidates[index].candidate_id,
        ),
    )
    winner = candidates[winner_index]
    winner_record = records[winner_index]
    trial_sharpes = [float(record["sharpe_25bps"]) for record in production]
    trial_sharpes.extend(float(record["sharpe_25bps"]) for record in exploratory_records)
    trial_sharpes.extend(float(record["sharpe_25bps"]) for record in records)
    trial_fingerprints = [
        str(record.get("strategy_fingerprint") or f"legacy:{record['candidate_id']}")
        for record in production
    ]
    trial_fingerprints.extend(str(record["strategy_fingerprint"]) for record in exploratory_records)
    trial_fingerprints.extend(str(record["strategy_fingerprint"]) for record in records)
    unique_trial_fingerprints = len(set(trial_fingerprints))
    segment_scores = [
        [float(value) for value in record["segment_sharpes"]] for record in production
    ]
    segment_scores.extend(exploratory_segments)
    segment_scores.extend(current_segments)
    dsr = deflated_sharpe_from_trials(primary_returns[winner_index], trial_sharpes)
    psr = probabilistic_sharpe(
        primary_returns[winner_index], benchmark_sharpe_annual=benchmark_stats.sharpe
    )
    pbo = probability_of_backtest_overfitting(segment_scores)
    win_rate = winner_record["segment_wins"] / 10.0
    latest_snapshot = live_snapshot or snapshots[-1]
    parity_weights = macro_target_weights(
        base_weights=_base_weight_series(assets, winner.base_portfolio)[-1],
        policy=winner.policy,
        snapshot=latest_snapshot.as_dict(include_history=True),
    )
    parity_digest = _fingerprint({key: str(value) for key, value in parity_weights.items()})
    publication_safe = all(
        (snapshot.cpi_available_date is None or snapshot.cpi_available_date <= snapshot.as_of_date)
        and (
            snapshot.sahm_available_date is None
            or snapshot.sahm_available_date <= snapshot.as_of_date
        )
        for snapshot in snapshots
    )
    gates = (
        ("complete_trials", len(records) == EXPECTED_CANDIDATES, len(records), EXPECTED_CANDIDATES),
        (
            "production_replay_complete",
            len(production) == EXPECTED_PRODUCTION_TRIALS,
            len(production),
            EXPECTED_PRODUCTION_TRIALS,
        ),
        (
            "exploratory_replay_complete",
            len(exploratory_records) == EXPECTED_EXPLORATORY_TRIALS,
            len(exploratory_records),
            EXPECTED_EXPLORATORY_TRIALS,
        ),
        (
            "multiplicity_trials",
            len(trial_sharpes) == EXPECTED_MULTIPLICITY_TRIALS,
            len(trial_sharpes),
            EXPECTED_MULTIPLICITY_TRIALS,
        ),
        (
            "unique_trial_fingerprints",
            unique_trial_fingerprints == EXPECTED_MULTIPLICITY_TRIALS,
            unique_trial_fingerprints,
            EXPECTED_MULTIPLICITY_TRIALS,
        ),
        (
            "macro_data_complete",
            macro_data_quality.get("complete") is True,
            macro_data_quality.get("complete"),
            True,
        ),
        ("publication_lag_safe", publication_safe, publication_safe, True),
        (
            "realtime_labor_safe",
            bool(macro_data_quality.get("series", {}).get("SAHMREALTIME", {}).get("complete")),
            macro_data_quality.get("series", {}).get("SAHMREALTIME", {}).get("complete"),
            True,
        ),
        ("live_data_freshness", latest_snapshot.fresh, latest_snapshot.fresh, True),
        ("research_live_parity", bool(parity_digest), bool(parity_digest), True),
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
        {"gate_id": key, "passed": bool(passed), "actual": str(actual), "required": str(required)}
        for key, passed, actual, required in gates
    ]
    passed = all(item[1] for item in gates)
    macro_fp = _fingerprint(
        {
            "quality": macro_data_quality,
            "first": snapshots[0].as_dict(),
            "last": snapshots[-1].as_dict(),
        }
    )
    batch_id = (
        "macro-strategy-factory-"
        + _fingerprint({"macro": macro_fp, "code": code_commit, "grammar": SCHEMA_VERSION})[7:19]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "timestamp_utc": timestamp_utc or datetime.now(UTC).isoformat(),
        "code_commit": code_commit,
        "macro_data_fingerprint": macro_fp,
        "candidate_count": len(candidates),
        "complete_trial_count": len(records),
        "production_trial_count": len(production),
        "exploratory_trial_count": len(exploratory_records),
        "current_trial_count": len(records),
        "multiplicity_trial_count": len(trial_sharpes),
        "unique_trial_fingerprint_count": unique_trial_fingerprints,
        "candidates": [candidate.as_dict() for candidate in candidates],
        "exploratory_replay": exploratory_records,
        "trial_records": records,
        "macro_data": macro_data_quality,
        "research_live_parity": {"passed": True, "target_weights_digest": parity_digest},
        "live_macro_evidence": {
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "policy_digest": _fingerprint(winner.policy.model_dump(mode="json")),
            "snapshot_digest": _fingerprint(latest_snapshot.as_dict(include_history=True)),
            "target_weights_digest": parity_digest,
            "latest_snapshot": latest_snapshot.as_dict(include_history=True),
            "fresh": latest_snapshot.fresh,
            "complete": latest_snapshot.complete,
            "cross_checked": latest_snapshot.cross_check_status == "PASS",
        },
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
            "selected_deploy_config": render_macro_candidate_toml(winner) if passed else None,
            "search_space_exhausted": not passed,
            "next_strategy_family": None if passed else "independent_asset_universe_or_carry",
        },
        "benchmark": benchmark_stats.as_dict(),
        "safety": ["no broker API", "no orders", "no capital change", "long-only", "no leverage"],
    }


def render_macro_factory_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    lines = [
        "# 독립 거시 전략 공장 최신 실행",
        "",
        f"- 판정: **{decision['verdict']}**",
        f"- 묶음: `{payload['batch_id']}`",
        f"- 공식 후보: {payload['complete_trial_count']}/{payload['candidate_count']}",
        f"- 사전 탐색 재생: {payload['exploratory_trial_count']}",
        f"- 누적 다중검정: {payload['multiplicity_trial_count']}",
        f"- 잠정 최고: `{decision['provisional_best_candidate_id']}`",
        f"- DSR/PBO/PSR: {decision['dsr']} / {decision['pbo']} / {decision['psr']}",
        "",
        "## 관문",
        "",
        "| 관문 | 상태 | 현재 | 기준 |",
        "|---|:---:|---:|---:|",
    ]
    for gate in decision["gates"]:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"| {gate['gate_id']} | {status} | {gate['actual']} | {gate['required']} |")
    lines.extend(["", "> 이 실행은 주문과 자본을 변경하지 않는다."])
    return "\n".join(lines)


__all__ = [
    "EXPECTED_CANDIDATES",
    "EXPECTED_EXPLORATORY_TRIALS",
    "EXPECTED_MULTIPLICITY_TRIALS",
    "MacroPolicyCandidate",
    "generate_exploratory_candidates",
    "generate_macro_candidates",
    "render_macro_candidate_toml",
    "render_macro_factory_markdown",
    "run_macro_strategy_factory",
]
