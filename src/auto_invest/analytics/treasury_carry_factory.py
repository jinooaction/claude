"""Spec 152: point-in-time Treasury carry factory with cumulative trial accounting."""

from __future__ import annotations

import hashlib
import json
import math
import tomllib
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probabilistic_sharpe,
    probability_of_backtest_overfitting,
)
from auto_invest.analytics.edge_gate_calibration import (
    CALIBRATED,
    GATE_VERSION,
    HOLDOUT_PSR_MIN,
    PBO_DIAGNOSTIC_MAX,
)
from auto_invest.analytics.global_trend import gold_total_return_factors
from auto_invest.analytics.multi_asset_trend import bond_total_return_factors, correlation
from auto_invest.analytics.risk_managed_beta import (
    MonthlyRow,
    market_total_return_factors,
    summarize,
)
from auto_invest.config.rules import PortfolioRebalanceConfig, TreasuryCarryPolicyConfig
from auto_invest.market_data.public_data import SeriesPoint, parse_fred_csv
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.strategy.rebalance import treasury_target_weights

SCHEMA_VERSION = "1.0"
EXPECTED_CANDIDATES = 64
EXPECTED_PRIOR_TRIALS = 512
EXPECTED_GLOBAL_AUDIT_TRIALS = 576
EXPECTED_MULTIPLICITY_TRIALS = EXPECTED_GLOBAL_AUDIT_TRIALS
FACTORY_EDGE = "FACTORY_EDGE"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
OBJECTIVE = "diversifier"
FAMILIES = ("carry_roll", "carry_rate_trend", "defensive_curve", "curve_barbell")
SERIES_TO_SYMBOL = {
    "DGS3MO": "SGOV",
    "DGS2": "SHY",
    "DGS5": "IEI",
    "DGS10": "IEF",
    "DGS30": "TLT",
}
MATURITY_YEARS = {
    "SGOV": Decimal("0.25"),
    "SHY": Decimal("2"),
    "IEI": Decimal("5"),
    "IEF": Decimal("10"),
    "TLT": Decimal("30"),
}
EFFECTIVE_DURATION = {
    "SGOV": Decimal("0.20"),
    "SHY": Decimal("1.90"),
    "IEI": Decimal("4.50"),
    "IEF": Decimal("7.50"),
    "TLT": Decimal("16.00"),
}


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class TreasuryCurveSnapshot:
    as_of_date: str
    yields: dict[str, Decimal | None]
    observation_dates: dict[str, str | None]
    yield_history: dict[str, tuple[Decimal | None, ...]]
    complete: bool
    fresh: bool

    def as_dict(self, *, include_history: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "as_of_date": self.as_of_date,
            "yields": {
                key: None if value is None else str(value) for key, value in self.yields.items()
            },
            "observation_dates": dict(self.observation_dates),
            "complete": self.complete,
            "fresh": self.fresh,
        }
        if include_history:
            payload["yield_history"] = {
                key: [None if value is None else str(value) for value in values]
                for key, values in self.yield_history.items()
            }
        return payload


@dataclass(frozen=True)
class TreasuryCarryCandidate:
    candidate_id: str
    trial_index: int
    policy: TreasuryCarryPolicyConfig
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        execution_symbols = [
            symbol
            for symbol, maturity in MATURITY_YEARS.items()
            if maturity <= Decimal(self.policy.max_maturity_years)
        ]
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.policy.family,
            "policy": self.policy.model_dump(mode="json"),
            "strategy_fingerprint": self.strategy_fingerprint,
            "signal_symbols": list(SERIES_TO_SYMBOL),
            "execution_symbols": execution_symbols,
            "deploy_config_text": render_treasury_candidate_toml(self),
            "live_expressible": True,
        }


def _candidate(index: int, policy: TreasuryCarryPolicyConfig) -> TreasuryCarryCandidate:
    digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": policy.model_dump(mode="json")})
    provisional = TreasuryCarryCandidate(
        candidate_id=f"treasury-{policy.family}-{digest[7:19]}",
        trial_index=index,
        policy=policy,
        strategy_fingerprint="pending",
    )
    parsed = tomllib.loads(render_treasury_candidate_toml(provisional))
    config = PortfolioRebalanceConfig.model_validate(parsed["portfolio"])
    return replace(provisional, strategy_fingerprint=strategy_fingerprint_digest(config))


def generate_treasury_candidates() -> tuple[TreasuryCarryCandidate, ...]:
    candidates: list[TreasuryCarryCandidate] = []
    for family in FAMILIES:
        for max_maturity in (10, 30):
            for lookback in (3, 12):
                for top_n in (1, 2):
                    for strength in (Decimal("0.5"), Decimal("1.0")):
                        candidates.append(
                            _candidate(
                                len(candidates) + 1,
                                TreasuryCarryPolicyConfig(
                                    family=family,
                                    max_maturity_years=max_maturity,
                                    lookback_months=lookback,
                                    top_n=top_n,
                                    signal_strength=strength,
                                ),
                            )
                        )
    if len(candidates) != EXPECTED_CANDIDATES:
        raise RuntimeError("Treasury candidate count contract violated")
    if len({candidate.candidate_id for candidate in candidates}) != EXPECTED_CANDIDATES:
        raise RuntimeError("Treasury candidate id uniqueness contract violated")
    if len({candidate.strategy_fingerprint for candidate in candidates}) != EXPECTED_CANDIDATES:
        raise RuntimeError("Treasury strategy fingerprint uniqueness contract violated")
    return tuple(candidates)


def render_treasury_candidate_toml(candidate: TreasuryCarryCandidate) -> str:
    policy = candidate.policy
    universe = [
        symbol
        for symbol, maturity in MATURITY_YEARS.items()
        if maturity <= Decimal(policy.max_maturity_years)
    ]
    universe_text = ", ".join(f'"{symbol}"' for symbol in universe)
    return f'''[portfolio]
id = "{candidate.candidate_id}"
universe = [{universe_text}]
weights = {{ momentum = "1.0" }}
weight_scheme = "equal"
top_n = 5
rebalance_mode = "rebalance"
invested_fraction = "0.99"
rebalance_every_n_sessions = 21
lookback_bars = 252
momentum_period = 252
rebalance_threshold_pct = "2.0"
min_notional_usd = "25"

[portfolio.treasury_carry_policy]
family = "{policy.family}"
max_maturity_years = {policy.max_maturity_years}
lookback_months = {policy.lookback_months}
top_n = {policy.top_n}
signal_strength = "{policy.signal_strength}"
'''


def _latest_point(points: list[SeriesPoint], target: date) -> SeriesPoint | None:
    return next(
        (
            point
            for point in reversed(points)
            if point.value is not None and date.fromisoformat(point.date) <= target
        ),
        None,
    )


def build_treasury_curve_snapshots(
    target_dates: list[str],
    *,
    series: dict[str, list[SeriesPoint]],
    max_staleness_days: int = 7,
) -> list[TreasuryCurveSnapshot]:
    histories: dict[str, list[Decimal | None]] = {
        symbol: [] for symbol in SERIES_TO_SYMBOL.values()
    }
    snapshots: list[TreasuryCurveSnapshot] = []
    for raw_target in target_dates:
        target = date.fromisoformat(raw_target)
        yields: dict[str, Decimal | None] = {}
        observed: dict[str, str | None] = {}
        fresh_values: list[bool] = []
        for series_id, symbol in SERIES_TO_SYMBOL.items():
            point = _latest_point(series.get(series_id, []), target)
            value = None if point is None else point.value
            observation_date = None if point is None else point.date
            if observation_date is not None:
                age = (target - date.fromisoformat(observation_date)).days
                if age > 35:
                    value = None
                    observation_date = None
                else:
                    fresh_values.append(age <= max_staleness_days)
            yields[symbol] = value
            observed[symbol] = observation_date
            histories[symbol].append(value)
        complete = all(value is not None for value in yields.values())
        fresh = len(fresh_values) >= 4 and all(fresh_values)
        snapshots.append(
            TreasuryCurveSnapshot(
                as_of_date=raw_target,
                yields=yields,
                observation_dates=observed,
                yield_history={key: tuple(values) for key, values in histories.items()},
                complete=complete,
                fresh=fresh,
            )
        )
    return snapshots


def load_treasury_curve_bundle(
    data_dir: Path, target_dates: list[str]
) -> tuple[list[TreasuryCurveSnapshot], dict[str, Any]]:
    series: dict[str, list[SeriesPoint]] = {}
    quality_rows: dict[str, Any] = {}
    for series_id in SERIES_TO_SYMBOL:
        path = data_dir / "fred" / f"{series_id}.csv"
        points = parse_fred_csv(path.read_text(encoding="utf-8"))
        series[series_id] = points
        observed = [point for point in points if point.value is not None]
        quality_rows[series_id] = {
            "rows": len(points),
            "observed_rows": len(observed),
            "first_date": observed[0].date if observed else None,
            "last_date": observed[-1].date if observed else None,
            "complete": len(observed) >= 1500,
        }
    snapshots = build_treasury_curve_snapshots(target_dates, series=series)
    publication_safe = all(
        observed is None or observed <= snapshot.as_of_date
        for snapshot in snapshots
        for observed in snapshot.observation_dates.values()
    )
    coverage_complete = all(row["complete"] for row in quality_rows.values())
    quality = {
        "series": quality_rows,
        "coverage_complete": coverage_complete,
        "publication_safe": publication_safe,
        "latest_complete": snapshots[-1].complete if snapshots else False,
        "latest_fresh": snapshots[-1].fresh if snapshots else False,
        "complete": bool(
            snapshots
            and coverage_complete
            and publication_safe
            and snapshots[-1].complete
            and snapshots[-1].fresh
        ),
        "return_model": "rolling_par_duration_approximation",
        "development_window": "1990-01-01..2006-12-31",
        "holdout_window": "2007-01-01..latest",
    }
    return snapshots, quality


def _monthly_sleeve_factors(
    snapshots: list[TreasuryCurveSnapshot],
) -> dict[str, list[float | None]]:
    output = {symbol: [] for symbol in MATURITY_YEARS}
    for previous, current in zip(snapshots[:-1], snapshots[1:], strict=True):
        for symbol in MATURITY_YEARS:
            y0 = previous.yields[symbol]
            y1 = current.yields[symbol]
            if y0 is None or y1 is None:
                output[symbol].append(None)
                continue
            carry = y0 / Decimal("100") / Decimal("12")
            delta = (y1 - y0) / Decimal("100")
            duration = EFFECTIVE_DURATION[symbol]
            convexity = duration * (duration + Decimal("1"))
            monthly_return = carry - duration * delta + convexity * delta * delta / Decimal("2")
            factor = Decimal("1") + monthly_return
            if factor <= 0:
                raise ValueError(f"Treasury return model produced non-positive factor for {symbol}")
            output[symbol].append(float(factor))
    return output


def _candidate_factors(
    candidate: TreasuryCarryCandidate,
    snapshots: list[TreasuryCurveSnapshot],
    sleeves: dict[str, list[float | None]],
    *,
    cost_bps: int,
) -> tuple[list[float], float]:
    previous_weights = {symbol: Decimal("0") for symbol in MATURITY_YEARS}
    output: list[float] = []
    turnover_total = Decimal("0")
    for index, snapshot in enumerate(snapshots[:-1]):
        try:
            weights = treasury_target_weights(
                policy=candidate.policy,
                snapshot=snapshot.as_dict(include_history=True),
                allow_partial=True,
            )
        except ValueError:
            weights = {}
        turnover = sum(
            abs(weights.get(symbol, Decimal("0")) - previous_weights[symbol])
            for symbol in previous_weights
        )
        gross = Decimal("1") - sum(weights.values(), Decimal("0"))
        for symbol, weight in weights.items():
            factor = sleeves[symbol][index]
            gross += weight * Decimal(str(1.0 if factor is None else factor))
        net = gross * max(Decimal("0"), Decimal("1") - turnover * cost_bps / Decimal("10000"))
        output.append(float(net))
        turnover_total += turnover
        previous_weights = {symbol: weights.get(symbol, Decimal("0")) for symbol in MATURITY_YEARS}
    return output, float(turnover_total)


def _ladder_factors(
    snapshots: list[TreasuryCurveSnapshot],
    sleeves: dict[str, list[float | None]],
    *,
    cost_bps: int = 25,
) -> list[float]:
    previous: dict[str, Decimal] = {}
    output: list[float] = []
    for index, snapshot in enumerate(snapshots[:-1]):
        eligible = [
            symbol
            for symbol in MATURITY_YEARS
            if snapshot.yields[symbol] is not None and sleeves[symbol][index] is not None
        ]
        weights = (
            {symbol: Decimal("1") / Decimal(len(eligible)) for symbol in eligible}
            if eligible
            else {}
        )
        turnover = sum(
            abs(weights.get(symbol, Decimal("0")) - previous.get(symbol, Decimal("0")))
            for symbol in set(weights) | set(previous)
        )
        gross = Decimal("1") - sum(weights.values(), Decimal("0"))
        gross += sum(
            weight * Decimal(str(sleeves[symbol][index])) for symbol, weight in weights.items()
        )
        output.append(
            float(gross * max(Decimal("0"), Decimal("1") - turnover * cost_bps / Decimal("10000")))
        )
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


def _prior_records(
    prior_trial_records: list[dict[str, Any]], prior_factory_payload: dict[str, Any]
) -> list[dict[str, Any]]:
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
    production = [production_by_id[key] for key in sorted(production_by_id)][:256]
    exploratory = [
        record
        for record in prior_factory_payload.get("exploratory_replay", [])
        if isinstance(record, dict) and len(record.get("segment_sharpes", [])) == 10
    ]
    macro = [
        record
        for record in prior_factory_payload.get("trial_records", [])
        if isinstance(record, dict)
        and record.get("status") == "complete"
        and len(record.get("segment_sharpes", [])) == 10
    ]
    return production[:256] + exploratory[:192] + macro[:64]


def _calibration_valid(payload: dict[str, Any], *, code_commit: str) -> bool:
    scenario = payload.get("scenario", {})
    revised = payload.get("revised", {})
    thresholds = payload.get("thresholds", {})
    return bool(
        payload.get("gate_version") == GATE_VERSION
        and payload.get("verdict") == CALIBRATED
        and payload.get("code_commit") == code_commit
        and int(scenario.get("repetitions", 0)) >= 200
        and float(revised.get("false_acceptance_rate", 1.0)) <= 0.05
        and float(revised.get("detection_rate", 0.0)) >= 0.80
        and float(thresholds.get("development_dsr_diagnostic_min", 0.0)) == 0.95
        and float(thresholds.get("development_pbo_diagnostic_max", 1.0)) == 0.10
        and float(thresholds.get("holdout_psr_min", 0.0)) == HOLDOUT_PSR_MIN
    )


def run_treasury_carry_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    snapshots: list[TreasuryCurveSnapshot],
    *,
    treasury_data_quality: dict[str, Any],
    prior_trial_records: list[dict[str, Any]],
    prior_factory_payload: dict[str, Any],
    calibration_evidence: dict[str, Any],
    live_snapshot: TreasuryCurveSnapshot | None = None,
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Run gate v2 with family-local discovery and untouched confirmation."""

    if len(rows) != len(gold_levels) or len(snapshots) != len(rows):
        raise ValueError("rows, gold, and Treasury snapshots must align")
    candidates = generate_treasury_candidates()
    sleeves = _monthly_sleeve_factors(snapshots)
    dates = [row.date for row in rows[1:]]
    boundary = next(
        (index for index, value in enumerate(dates) if value >= "2007-01-01"), len(dates)
    )
    holdout_start = min(len(dates), boundary + 1)
    if boundary < 120 or len(dates) - holdout_start < 120:
        raise ValueError("development and holdout must each contain at least 120 months")

    ladder_all = _ladder_factors(snapshots, sleeves)
    ladder_development = ladder_all[:boundary]
    ladder_holdout = ladder_all[holdout_start:]
    ladder_holdout_stats = summarize(ladder_holdout)
    ladder_development_segments = [
        annualized_sharpe(segment)
        for segment in _segments([factor - 1.0 for factor in ladder_development])
    ]
    incumbent_assets = [
        market_total_return_factors(rows),
        bond_total_return_factors(rows),
        gold_total_return_factors(gold_levels),
    ]
    incumbent_all = [sum(values) / 3.0 for values in zip(*incumbent_assets, strict=True)]
    incumbent_holdout = incumbent_all[holdout_start:]
    incumbent_holdout_stats = summarize(incumbent_holdout)

    records: list[dict[str, Any]] = []
    development_returns: list[list[float]] = []
    holdout_factors_by_cost: list[dict[int, list[float]]] = []
    development_segments: list[list[float]] = []
    for candidate in candidates:
        full_by_cost: dict[int, list[float]] = {}
        turnover = 0.0
        for cost in (10, 25, 50):
            factors, candidate_turnover = _candidate_factors(
                candidate, snapshots, sleeves, cost_bps=cost
            )
            full_by_cost[cost] = factors
            if cost == 25:
                turnover = candidate_turnover
        candidate_development = [factor - 1.0 for factor in full_by_cost[25][:boundary]]
        candidate_holdout = full_by_cost[25][holdout_start:]
        segments = _segments(candidate_development)
        segment_sharpes = [annualized_sharpe(segment) for segment in segments]
        development_stats = summarize(full_by_cost[25][:boundary])
        holdout_stats = summarize(candidate_holdout)
        development_returns.append(candidate_development)
        development_segments.append(segment_sharpes)
        holdout_factors_by_cost.append(
            {cost: values[holdout_start:] for cost, values in full_by_cost.items()}
        )
        records.append(
            {
                "candidate_id": candidate.candidate_id,
                "strategy_fingerprint": candidate.strategy_fingerprint,
                "status": "complete",
                "family": candidate.policy.family,
                "sharpe_25bps": round(development_stats.sharpe, 6),
                "development_sharpe_25bps": round(development_stats.sharpe, 6),
                "development_calmar_25bps": (
                    None if development_stats.calmar is None else round(development_stats.calmar, 6)
                ),
                "development_max_drawdown_25bps": round(development_stats.max_dd_pct, 6),
                "holdout_sharpe_25bps": round(holdout_stats.sharpe, 6),
                "holdout_cagr_25bps": round(holdout_stats.cagr_pct, 6),
                "holdout_max_drawdown_25bps": round(holdout_stats.max_dd_pct, 6),
                "holdout_calmar_25bps": (
                    None if holdout_stats.calmar is None else round(holdout_stats.calmar, 6)
                ),
                "holdout_total_return_50bps": round(
                    math.prod(full_by_cost[50][holdout_start:]) - 1.0, 8
                ),
                "turnover": round(turnover, 6),
                "segment_sharpes": [round(value, 6) for value in segment_sharpes],
                "segment_wins": sum(
                    value > benchmark
                    for value, benchmark in zip(
                        segment_sharpes, ladder_development_segments, strict=True
                    )
                ),
            }
        )

    winner_index = max(
        range(len(records)),
        key=lambda index: (
            records[index]["development_sharpe_25bps"],
            records[index]["development_calmar_25bps"] or -math.inf,
            -records[index]["development_max_drawdown_25bps"],
            candidates[index].candidate_id,
        ),
    )
    winner = candidates[winner_index]
    winner_record = records[winner_index]
    family_trial_sharpes = [float(record["development_sharpe_25bps"]) for record in records]
    effective_trials = effective_independent_trials(development_returns)
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index],
        family_trial_sharpes,
        effective_trial_count=effective_trials,
    )
    pbo = probability_of_backtest_overfitting(development_segments)

    winner_holdout = holdout_factors_by_cost[winner_index][25]
    blend = [
        0.8 * base + 0.2 * candidate
        for base, candidate in zip(incumbent_holdout, winner_holdout, strict=True)
    ]
    blend_stats = summarize(blend)
    blend_psr = probabilistic_sharpe(
        [factor - 1.0 for factor in blend],
        benchmark_sharpe_annual=incumbent_holdout_stats.sharpe,
    )
    standalone_psr = probabilistic_sharpe(
        [factor - 1.0 for factor in winner_holdout],
        benchmark_sharpe_annual=ladder_holdout_stats.sharpe,
    )
    incumbent_correlation = correlation(incumbent_holdout, winner_holdout)

    prior = _prior_records(prior_trial_records, prior_factory_payload)
    audit_records = prior + records
    audit_fingerprints = [
        str(record.get("strategy_fingerprint") or f"legacy:{record.get('candidate_id')}")
        for record in audit_records
    ]
    unique_audit_fingerprints = len(set(audit_fingerprints))
    calibration_passed = _calibration_valid(calibration_evidence, code_commit=code_commit)

    latest = live_snapshot or snapshots[-1]
    parity_weights = treasury_target_weights(
        policy=winner.policy,
        snapshot=latest.as_dict(include_history=True),
    )
    parity_digest = _fingerprint({key: str(value) for key, value in parity_weights.items()})
    publication_safe = all(
        observed is None or observed <= snapshot.as_of_date
        for snapshot in snapshots
        for observed in snapshot.observation_dates.values()
    )

    gate_rows: list[dict[str, Any]] = []

    def add_gate(
        gate_id: str,
        passed: bool,
        actual: Any,
        required: Any,
        *,
        stage: str,
        blocking: bool = True,
    ) -> None:
        gate_rows.append(
            {
                "gate_id": gate_id,
                "passed": bool(passed),
                "actual": str(actual),
                "required": str(required),
                "stage": stage,
                "blocking": blocking,
            }
        )

    add_gate(
        "gate_calibration",
        calibration_passed,
        calibration_evidence.get("verdict"),
        CALIBRATED,
        stage="calibration",
    )
    add_gate("complete_family_trials", len(records) == 64, len(records), 64, stage="audit")
    add_gate("prior_audit_complete", len(prior) == 512, len(prior), 512, stage="audit")
    add_gate(
        "global_audit_trials", len(audit_records) == 576, len(audit_records), 576, stage="audit"
    )
    add_gate(
        "unique_audit_fingerprints",
        unique_audit_fingerprints == 576,
        unique_audit_fingerprints,
        576,
        stage="audit",
    )
    add_gate(
        "family_pbo_rows",
        len(development_segments) == 64,
        len(development_segments),
        64,
        stage="discovery",
    )
    add_gate(
        "treasury_data_complete",
        treasury_data_quality.get("complete") is True,
        treasury_data_quality.get("complete"),
        True,
        stage="data",
    )
    add_gate("publication_safe", publication_safe, publication_safe, True, stage="data")
    add_gate("live_data_complete", latest.complete, latest.complete, True, stage="data")
    add_gate("live_data_fresh", latest.fresh, latest.fresh, True, stage="data")
    add_gate("research_live_parity", bool(parity_digest), bool(parity_digest), True, stage="parity")
    add_gate("development_months", boundary >= 120, boundary, 120, stage="split")
    add_gate(
        "embargo_months", holdout_start - boundary == 1, holdout_start - boundary, 1, stage="split"
    )
    add_gate("holdout_months", len(ladder_holdout) >= 120, len(ladder_holdout), 120, stage="split")
    add_gate(
        "development_dsr_diagnostic",
        dsr is not None and dsr >= Decimal("0.95"),
        dsr,
        Decimal("0.95"),
        stage="discovery",
        blocking=False,
    )
    add_gate(
        "development_pbo_diagnostic",
        pbo is not None and pbo <= Decimal(str(PBO_DIAGNOSTIC_MAX)),
        pbo,
        PBO_DIAGNOSTIC_MAX,
        stage="discovery",
        blocking=False,
    )
    add_gate(
        "holdout_blend_psr",
        blend_psr is not None and blend_psr >= Decimal(str(HOLDOUT_PSR_MIN)),
        blend_psr,
        HOLDOUT_PSR_MIN,
        stage="confirmation",
    )
    add_gate(
        "holdout_cost_50bps_positive",
        winner_record["holdout_total_return_50bps"] > 0.0,
        winner_record["holdout_total_return_50bps"],
        0.0,
        stage="confirmation",
    )
    add_gate(
        "incumbent_correlation",
        incumbent_correlation is not None and incumbent_correlation < 0.80,
        incumbent_correlation,
        0.80,
        stage="economics",
    )
    add_gate(
        "blend_sharpe_improvement",
        blend_stats.sharpe >= incumbent_holdout_stats.sharpe + 0.05,
        round(blend_stats.sharpe - incumbent_holdout_stats.sharpe, 6),
        0.05,
        stage="economics",
    )
    add_gate(
        "blend_drawdown_non_worsening",
        blend_stats.max_dd_pct <= incumbent_holdout_stats.max_dd_pct,
        blend_stats.max_dd_pct,
        incumbent_holdout_stats.max_dd_pct,
        stage="economics",
    )
    add_gate(
        "standalone_psr_diagnostic",
        standalone_psr is not None and standalone_psr >= Decimal("0.95"),
        standalone_psr,
        Decimal("0.95"),
        stage="replacement_diagnostic",
        blocking=False,
    )
    add_gate(
        "standalone_sharpe_diagnostic",
        winner_record["holdout_sharpe_25bps"] >= ladder_holdout_stats.sharpe + 0.20,
        round(winner_record["holdout_sharpe_25bps"] - ladder_holdout_stats.sharpe, 6),
        0.20,
        stage="replacement_diagnostic",
        blocking=False,
    )
    add_gate(
        "standalone_calmar_diagnostic",
        winner_record["holdout_calmar_25bps"] is not None
        and ladder_holdout_stats.calmar is not None
        and winner_record["holdout_calmar_25bps"] > ladder_holdout_stats.calmar,
        winner_record["holdout_calmar_25bps"],
        ladder_holdout_stats.calmar,
        stage="replacement_diagnostic",
        blocking=False,
    )
    add_gate(
        "standalone_drawdown_diagnostic",
        winner_record["holdout_max_drawdown_25bps"] <= ladder_holdout_stats.max_dd_pct * 0.80,
        winner_record["holdout_max_drawdown_25bps"],
        round(ladder_holdout_stats.max_dd_pct * 0.80, 6),
        stage="replacement_diagnostic",
        blocking=False,
    )

    passed = all(gate["passed"] for gate in gate_rows if gate["blocking"])
    data_fp = _fingerprint(
        {
            "quality": treasury_data_quality,
            "first": snapshots[0].as_dict(include_history=False),
            "last": snapshots[-1].as_dict(include_history=False),
        }
    )
    batch_id = (
        "treasury-carry-factory-v2-"
        + _fingerprint(
            {"data": data_fp, "code": code_commit, "grammar": SCHEMA_VERSION, "gate": GATE_VERSION}
        )[7:19]
    )
    return {
        "schema_version": "2.0",
        "gate_version": GATE_VERSION,
        "batch_id": batch_id,
        "timestamp_utc": timestamp_utc or datetime.now(UTC).isoformat(),
        "code_commit": code_commit,
        "treasury_data_fingerprint": data_fp,
        "candidate_count": len(candidates),
        "complete_trial_count": len(records),
        "prior_trial_count": len(prior),
        "current_trial_count": len(records),
        "global_audit_trial_count": len(audit_records),
        "multiplicity_trial_count": len(records),
        "family_raw_trial_count": len(records),
        "family_effective_trial_count": str(effective_trials),
        "unique_trial_fingerprint_count": unique_audit_fingerprints,
        "calibration": calibration_evidence,
        "statistical_family": {
            "family_id": "treasury_carry_v1",
            "objective": OBJECTIVE,
            "benchmark_id": "incumbent_80_20_blend",
            "selection_rule": "max_development_sharpe_then_calmar_then_drawdown",
            "development_range": [dates[0], dates[boundary - 1]],
            "embargo_date": dates[boundary],
            "holdout_range": [dates[holdout_start], dates[-1]],
        },
        "development_selection": {
            "selected_candidate_id": winner.candidate_id,
            "selected_strategy_fingerprint": winner.strategy_fingerprint,
            "dsr": None if dsr is None else str(dsr),
            "pbo": None if pbo is None else str(pbo),
        },
        "holdout_confirmation": {
            "candidate_id": winner.candidate_id,
            "blend_psr_vs_incumbent": None if blend_psr is None else str(blend_psr),
            "standalone_psr_vs_treasury_ladder": (
                None if standalone_psr is None else str(standalone_psr)
            ),
        },
        "candidates": [candidate.as_dict() for candidate in candidates],
        "trial_records": records,
        "treasury_data": treasury_data_quality,
        "research_live_parity": {"passed": True, "target_weights_digest": parity_digest},
        "live_treasury_evidence": {
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "data_fingerprint": data_fp,
            "code_commit": code_commit,
            "target_weights_digest": parity_digest,
            "latest_snapshot": latest.as_dict(include_history=True),
            "fresh": latest.fresh,
            "complete": latest.complete,
        },
        "decision": {
            "verdict": FACTORY_EDGE if passed else NO_FACTORY_EDGE,
            "objective": OBJECTIVE,
            "selected_candidate_id": winner.candidate_id if passed else None,
            "provisional_best_candidate_id": winner.candidate_id,
            "dsr": None if dsr is None else str(dsr),
            "pbo": None if pbo is None else str(pbo),
            "psr": None if blend_psr is None else str(blend_psr),
            "gates": gate_rows,
            "research_canary_eligible": passed,
            "selected_strategy_fingerprint": winner.strategy_fingerprint if passed else None,
            "selected_deploy_config": render_treasury_candidate_toml(winner) if passed else None,
            "search_space_exhausted": not passed,
            "next_strategy_family": None if passed else "independent_credit_or_fx_carry",
        },
        "treasury_benchmark": ladder_holdout_stats.as_dict(),
        "incumbent_benchmark": incumbent_holdout_stats.as_dict(),
        "blend": {
            **blend_stats.as_dict(),
            "candidate_weight": "0.20",
            "incumbent_weight": "0.80",
            "candidate_correlation": incumbent_correlation,
        },
        "safety": ["no broker API", "no orders", "no capital change", "long-only", "no leverage"],
    }


def validate_live_treasury_evidence(
    payload: dict[str, Any],
    *,
    candidate_id: str,
    strategy_fingerprint: str,
    now: datetime | None = None,
    max_age_days: int = 7,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    try:
        generated = datetime.fromisoformat(str(payload["timestamp_utc"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        raise ValueError("Treasury evidence timestamp is missing or invalid") from exc
    age = current - generated.astimezone(UTC)
    if age < timedelta(minutes=-5) or age > timedelta(days=max_age_days):
        raise ValueError("Treasury evidence is stale")
    decision = payload.get("decision", {})
    evidence = payload.get("live_treasury_evidence", {})
    if payload.get("gate_version") != GATE_VERSION:
        raise ValueError("Treasury factory gate version is missing or legacy")
    if decision.get("verdict") != FACTORY_EDGE or not decision.get("research_canary_eligible"):
        raise ValueError("Treasury factory has no eligible winner")
    gates = decision.get("gates")
    if (
        not isinstance(gates, list)
        or not gates
        or any(
            not isinstance(gate, dict)
            or (gate.get("blocking") is not False and gate.get("passed") is not True)
            for gate in gates
        )
    ):
        raise ValueError("Treasury factory gates are incomplete or failed")
    if decision.get("selected_candidate_id") != candidate_id:
        raise ValueError("Treasury candidate id does not match factory winner")
    if decision.get("selected_strategy_fingerprint") != strategy_fingerprint:
        raise ValueError("Treasury strategy fingerprint does not match factory winner")
    if (
        evidence.get("candidate_id") != candidate_id
        or evidence.get("strategy_fingerprint") != strategy_fingerprint
    ):
        raise ValueError("live Treasury evidence identity mismatch")
    if evidence.get("data_fingerprint") != payload.get("treasury_data_fingerprint"):
        raise ValueError("live Treasury data fingerprint mismatch")
    if evidence.get("code_commit") != payload.get("code_commit"):
        raise ValueError("live Treasury code commit mismatch")
    if evidence.get("fresh") is not True or evidence.get("complete") is not True:
        raise ValueError("live Treasury evidence is incomplete or stale")
    if evidence.get("target_weights_digest") != payload.get("research_live_parity", {}).get(
        "target_weights_digest"
    ):
        raise ValueError("live Treasury target-weight digest mismatch")
    snapshot = evidence.get("latest_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("live Treasury snapshot is missing")
    if snapshot.get("complete") is not True or snapshot.get("fresh") is not True:
        raise ValueError("live Treasury snapshot is incomplete or stale")
    try:
        snapshot_age = current.date() - date.fromisoformat(str(snapshot["as_of_date"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("live Treasury snapshot date is invalid") from exc
    if snapshot_age.days < 0 or snapshot_age.days > max_age_days:
        raise ValueError("live Treasury snapshot is stale")
    return snapshot


def render_treasury_factory_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    lines = [
        "# 독립 국채 캐리 전략 공장 최신 실행",
        "",
        f"- 판정: **{decision['verdict']}**",
        f"- 묶음: `{payload['batch_id']}`",
        f"- 공식 후보: {payload['complete_trial_count']}/{payload['candidate_count']}",
        f"- 전체 감사 시도: {payload.get('global_audit_trial_count')}",
        f"- 현재 통계 가족: {payload.get('family_raw_trial_count')}개 ",
        f"  (독립 환산 {payload.get('family_effective_trial_count')})",
        f"- 잠정 최고: `{decision['provisional_best_candidate_id']}`",
        "- 개발 진단 DSR/PBO, 홀드아웃 PSR: "
        f"{decision['dsr']} / {decision['pbo']} / {decision['psr']}",
        "",
        "## 관문",
        "",
        "| 관문 | 역할 | 상태 | 현재 | 기준 |",
        "|---|---|:---:|---:|---:|",
    ]
    for gate in decision["gates"]:
        status = "PASS" if gate["passed"] else "FAIL"
        role = "차단" if gate.get("blocking", True) else "진단"
        lines.append(
            f"| {gate['gate_id']} | {role} | {status} | {gate['actual']} | {gate['required']} |"
        )
    lines.extend(["", "> 이 실행은 주문과 자본을 변경하지 않는다."])
    return "\n".join(lines)


__all__ = [
    "EXPECTED_CANDIDATES",
    "EXPECTED_GLOBAL_AUDIT_TRIALS",
    "EXPECTED_MULTIPLICITY_TRIALS",
    "FACTORY_EDGE",
    "NO_FACTORY_EDGE",
    "TreasuryCarryCandidate",
    "TreasuryCurveSnapshot",
    "build_treasury_curve_snapshots",
    "generate_treasury_candidates",
    "load_treasury_curve_bundle",
    "render_treasury_candidate_toml",
    "render_treasury_factory_markdown",
    "run_treasury_carry_factory",
    "validate_live_treasury_evidence",
]
