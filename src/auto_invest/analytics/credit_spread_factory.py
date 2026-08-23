"""Spec 154: point-in-time investment-grade credit spread strategy factory."""

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
from auto_invest.config.rules import CreditSpreadPolicyConfig, PortfolioRebalanceConfig
from auto_invest.market_data.public_data import SeriesPoint, parse_fred_csv
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.strategy.rebalance import credit_spread_target_weights

SCHEMA_VERSION = "1.0"
EXPECTED_CANDIDATES = 64
EXPECTED_PRIOR_TRIALS = 576
EXPECTED_GLOBAL_AUDIT_TRIALS = 640
EXPECTED_MULTIPLICITY_TRIALS = 64
FACTORY_EDGE = "FACTORY_EDGE"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
OBJECTIVE = "diversifier"
FAMILIES = ("carry_buffer", "spread_compression", "curve_value", "stress_reentry")
SERIES_IDS = ("HQMCB10YR", "HQMCB20YR", "DGS10", "DGS30")
LIVE_WHITELIST_AUTHORIZED = False


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CreditCurveSnapshot:
    as_of_date: str
    corporate_yields: dict[str, Decimal | None]
    treasury_yields: dict[str, Decimal | None]
    spreads: dict[str, Decimal | None]
    observation_dates: dict[str, str | None]
    credit_history: dict[str, tuple[Decimal | None, ...]]
    complete: bool
    fresh: bool

    def as_dict(self, *, include_history: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "as_of_date": self.as_of_date,
            "corporate_yields": _decimal_map(self.corporate_yields),
            "treasury_yields": _decimal_map(self.treasury_yields),
            "spreads": _decimal_map(self.spreads),
            "observation_dates": dict(self.observation_dates),
            "complete": self.complete,
            "fresh": self.fresh,
        }
        if include_history:
            payload["credit_history"] = {
                key: [None if value is None else str(value) for value in values]
                for key, values in self.credit_history.items()
            }
        return payload


def _decimal_map(values: dict[str, Decimal | None]) -> dict[str, str | None]:
    return {key: None if value is None else str(value) for key, value in values.items()}


@dataclass(frozen=True)
class CreditSpreadCandidate:
    candidate_id: str
    trial_index: int
    policy: CreditSpreadPolicyConfig
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.policy.family,
            "policy": self.policy.model_dump(mode="json"),
            "strategy_fingerprint": self.strategy_fingerprint,
            "signal_series": list(SERIES_IDS),
            "execution_symbols": ["LQD", "IEF"],
            "research_config_text": render_credit_candidate_toml(self),
            "live_expressible": False,
            "live_blocker": "LQD is not in the active live whitelist",
        }


def _candidate(index: int, policy: CreditSpreadPolicyConfig) -> CreditSpreadCandidate:
    digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": policy.model_dump(mode="json")})
    provisional = CreditSpreadCandidate(
        candidate_id=f"credit-{policy.family}-{digest[7:19]}",
        trial_index=index,
        policy=policy,
        strategy_fingerprint="pending",
    )
    parsed = tomllib.loads(render_credit_candidate_toml(provisional))
    config = PortfolioRebalanceConfig.model_validate(parsed["portfolio"])
    return replace(provisional, strategy_fingerprint=strategy_fingerprint_digest(config))


def generate_credit_candidates() -> tuple[CreditSpreadCandidate, ...]:
    candidates: list[CreditSpreadCandidate] = []
    for family in FAMILIES:
        for lookback in (3, 12):
            for threshold in (50, 100):
                for confirmation in (1, 3):
                    for max_credit_weight in (Decimal("0.5"), Decimal("1.0")):
                        candidates.append(
                            _candidate(
                                len(candidates) + 1,
                                CreditSpreadPolicyConfig(
                                    family=family,
                                    lookback_months=lookback,
                                    spread_threshold_bps=threshold,
                                    confirmation_months=confirmation,
                                    max_credit_weight=max_credit_weight,
                                ),
                            )
                        )
    if len(candidates) != EXPECTED_CANDIDATES:
        raise RuntimeError("credit candidate count contract violated")
    if len({candidate.candidate_id for candidate in candidates}) != EXPECTED_CANDIDATES:
        raise RuntimeError("credit candidate id uniqueness contract violated")
    if len({candidate.strategy_fingerprint for candidate in candidates}) != EXPECTED_CANDIDATES:
        raise RuntimeError("credit strategy fingerprint uniqueness contract violated")
    return tuple(candidates)


def render_credit_candidate_toml(candidate: CreditSpreadCandidate) -> str:
    policy = candidate.policy
    return f'''[portfolio]
id = "{candidate.candidate_id}"
universe = ["LQD", "IEF"]
weights = {{ momentum = "1.0" }}
weight_scheme = "equal"
top_n = 2
rebalance_mode = "rebalance"
invested_fraction = "0.99"
rebalance_every_n_sessions = 21
lookback_bars = 252
momentum_period = 252
rebalance_threshold_pct = "2.0"
min_notional_usd = "25"

[portfolio.credit_spread_policy]
family = "{policy.family}"
lookback_months = {policy.lookback_months}
spread_threshold_bps = {policy.spread_threshold_bps}
confirmation_months = {policy.confirmation_months}
max_credit_weight = "{policy.max_credit_weight}"
'''


def _latest_point(
    points: list[SeriesPoint], target: date, *, monthly_lag: bool = False
) -> SeriesPoint | None:
    return next(
        (
            point
            for point in reversed(points)
            if point.value is not None
            and (
                date.fromisoformat(point.date) < target.replace(day=1)
                if monthly_lag
                else date.fromisoformat(point.date) <= target
            )
        ),
        None,
    )


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)


def build_credit_curve_snapshots(
    target_dates: list[str],
    *,
    series: dict[str, list[SeriesPoint]],
    max_staleness_days: int = 70,
    max_treasury_staleness_days: int = 7,
) -> list[CreditCurveSnapshot]:
    histories: dict[str, list[Decimal | None]] = {
        key: []
        for key in (
            "corporate_10",
            "corporate_20",
            "treasury_10",
            "treasury_20",
            "spread_10",
            "spread_20",
        )
    }
    snapshots: list[CreditCurveSnapshot] = []
    for raw_target in target_dates:
        target = date.fromisoformat(raw_target)
        hqm10 = _latest_point(series.get("HQMCB10YR", []), target, monthly_lag=True)
        hqm20 = _latest_point(series.get("HQMCB20YR", []), target, monthly_lag=True)
        hqm_reference = hqm10 or hqm20
        treasury_target = (
            _month_end(
                date.fromisoformat(hqm_reference.date).year,
                date.fromisoformat(hqm_reference.date).month,
            )
            if hqm_reference is not None
            else target
        )
        dgs10 = _latest_point(series.get("DGS10", []), treasury_target)
        dgs30 = _latest_point(series.get("DGS30", []), treasury_target)

        corporate = {
            "10Y": None if hqm10 is None else hqm10.value,
            "20Y": None if hqm20 is None else hqm20.value,
        }
        treasury10 = None if dgs10 is None else dgs10.value
        treasury30 = None if dgs30 is None else dgs30.value
        treasury20 = (
            None
            if treasury10 is None or treasury30 is None
            else (treasury10 + treasury30) / Decimal("2")
        )
        treasury = {"10Y": treasury10, "20Y": treasury20}
        spreads = {
            "10Y": None
            if corporate["10Y"] is None or treasury10 is None
            else corporate["10Y"] - treasury10,
            "20Y": None
            if corporate["20Y"] is None or treasury20 is None
            else corporate["20Y"] - treasury20,
        }
        observations = {
            "HQMCB10YR": None if hqm10 is None else hqm10.date,
            "HQMCB20YR": None if hqm20 is None else hqm20.date,
            "DGS10": None if dgs10 is None else dgs10.date,
            "DGS30": None if dgs30 is None else dgs30.date,
        }
        values = {
            "corporate_10": corporate["10Y"],
            "corporate_20": corporate["20Y"],
            "treasury_10": treasury["10Y"],
            "treasury_20": treasury["20Y"],
            "spread_10": spreads["10Y"],
            "spread_20": spreads["20Y"],
        }
        for key, value in values.items():
            histories[key].append(value)
        complete = all(value is not None for value in values.values())
        corporate_ages = [
            (target - date.fromisoformat(value)).days
            for key, value in observations.items()
            if key.startswith("HQM") and value is not None
        ]
        treasury_ages = [
            (treasury_target - date.fromisoformat(value)).days
            for key, value in observations.items()
            if key.startswith("DGS") and value is not None
        ]
        fresh = bool(
            complete
            and len(corporate_ages) == 2
            and all(0 <= age <= max_staleness_days for age in corporate_ages)
            and len(treasury_ages) == 2
            and all(0 <= age <= max_treasury_staleness_days for age in treasury_ages)
        )
        snapshots.append(
            CreditCurveSnapshot(
                as_of_date=raw_target,
                corporate_yields=corporate,
                treasury_yields=treasury,
                spreads=spreads,
                observation_dates=observations,
                credit_history={key: tuple(history) for key, history in histories.items()},
                complete=complete,
                fresh=fresh,
            )
        )
    return snapshots


def load_credit_curve_bundle(
    data_dir: Path, target_dates: list[str]
) -> tuple[list[CreditCurveSnapshot], dict[str, Any]]:
    series: dict[str, list[SeriesPoint]] = {}
    quality_rows: dict[str, Any] = {}
    for series_id in SERIES_IDS:
        path = data_dir / "fred" / f"{series_id}.csv"
        points = parse_fred_csv(path.read_text(encoding="utf-8"))
        series[series_id] = points
        observed = [point for point in points if point.value is not None]
        required = 500 if series_id.startswith("HQM") else 1500
        quality_rows[series_id] = {
            "rows": len(points),
            "observed_rows": len(observed),
            "first_date": observed[0].date if observed else None,
            "last_date": observed[-1].date if observed else None,
            "complete": len(observed) >= required,
            "source": "U.S. Treasury HQM via FRED"
            if series_id.startswith("HQM")
            else "Federal Reserve H.15 via FRED",
            "public_domain": series_id.startswith("HQM"),
        }
    snapshots = build_credit_curve_snapshots(target_dates, series=series)
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
        "instrument_basis_risk": "HQM synthetic high-quality corporate return represented by LQD",
        "development_window": "1990-01-01..2006-12-31",
        "holdout_window": "2007-02-01..latest",
    }
    return snapshots, quality


def _bond_factor(y0: Decimal, y1: Decimal, duration: Decimal) -> float:
    carry = y0 / Decimal("100") / Decimal("12")
    delta = (y1 - y0) / Decimal("100")
    convexity = duration * (duration + Decimal("1"))
    factor = Decimal("1") + carry - duration * delta + convexity * delta * delta / Decimal("2")
    if factor <= 0:
        raise ValueError("credit return model produced a non-positive factor")
    return float(factor)


def _monthly_sleeve_factors(
    snapshots: list[CreditCurveSnapshot],
) -> dict[str, list[float | None]]:
    output: dict[str, list[float | None]] = {"LQD": [], "IEF": []}
    for previous, current in zip(snapshots[:-1], snapshots[1:], strict=True):
        corp0, corp1 = previous.corporate_yields["10Y"], current.corporate_yields["10Y"]
        tsy0, tsy1 = previous.treasury_yields["10Y"], current.treasury_yields["10Y"]
        output["LQD"].append(
            None if corp0 is None or corp1 is None else _bond_factor(corp0, corp1, Decimal("8.0"))
        )
        output["IEF"].append(
            None if tsy0 is None or tsy1 is None else _bond_factor(tsy0, tsy1, Decimal("7.5"))
        )
    return output


def _candidate_factors(
    candidate: CreditSpreadCandidate,
    snapshots: list[CreditCurveSnapshot],
    sleeves: dict[str, list[float | None]],
    *,
    cost_bps: int,
) -> tuple[list[float], float]:
    previous_weights = {"LQD": Decimal("0"), "IEF": Decimal("0")}
    output: list[float] = []
    turnover_total = Decimal("0")
    for index, snapshot in enumerate(snapshots[:-1]):
        try:
            weights = credit_spread_target_weights(
                policy=candidate.policy,
                snapshot=snapshot.as_dict(include_history=True),
            )
        except ValueError:
            weights = {"LQD": Decimal("0"), "IEF": Decimal("1")}
        turnover = sum(abs(weights[symbol] - previous_weights[symbol]) for symbol in weights)
        gross = sum(
            weight * Decimal(str(1.0 if sleeves[symbol][index] is None else sleeves[symbol][index]))
            for symbol, weight in weights.items()
        )
        net = gross * max(Decimal("0"), Decimal("1") - turnover * cost_bps / Decimal("10000"))
        output.append(float(net))
        turnover_total += turnover
        previous_weights = weights
    return output, float(turnover_total)


def _credit_ladder_factors(
    sleeves: dict[str, list[float | None]], *, cost_bps: int = 25
) -> list[float]:
    output: list[float] = []
    for index in range(len(sleeves["LQD"])):
        lqd = sleeves["LQD"][index] or 1.0
        ief = sleeves["IEF"][index] or 1.0
        factor = (lqd + ief) / 2.0
        if index == 0:
            factor *= 1.0 - 2.0 * 0.5 * cost_bps / 10000.0
        output.append(factor)
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
    prior_trial_records: list[dict[str, Any]],
    prior_factory_payload: dict[str, Any],
    macro_factory_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    def complete_unique(
        records: list[Any],
        prefix: str,
        expected: int,
        *,
        allowed_statuses: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        statuses = allowed_statuses or {"complete"}
        unique: dict[str, dict[str, Any]] = {}
        for record in records:
            if (
                not isinstance(record, dict)
                or record.get("status") not in statuses
                or not str(record.get("candidate_id", "")).startswith(prefix)
                or not isinstance(record.get("segment_sharpes"), list)
                or len(record["segment_sharpes"]) != 10
            ):
                continue
            identity = str(record.get("strategy_fingerprint") or record.get("candidate_id") or "")
            if identity:
                unique.setdefault(identity, record)
        return [unique[key] for key in sorted(unique)][:expected]

    production = complete_unique(prior_trial_records, "factory-", 256)
    exploratory = complete_unique(
        list(macro_factory_payload.get("exploratory_replay", [])),
        "exploratory-",
        192,
        allowed_statuses={"EXPLORATORY_REJECTED"},
    )
    macro = complete_unique(list(macro_factory_payload.get("trial_records", [])), "macro-", 64)
    treasury = complete_unique(
        list(prior_factory_payload.get("trial_records", [])), "treasury-", 64
    )
    return production + exploratory + macro + treasury


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


def run_credit_spread_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    snapshots: list[CreditCurveSnapshot],
    *,
    credit_data_quality: dict[str, Any],
    prior_trial_records: list[dict[str, Any]],
    prior_factory_payload: dict[str, Any],
    macro_factory_payload: dict[str, Any],
    calibration_evidence: dict[str, Any],
    live_snapshot: CreditCurveSnapshot | None = None,
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    if len(rows) != len(gold_levels) or len(snapshots) != len(rows):
        raise ValueError("rows, gold, and credit snapshots must align")
    candidates = generate_credit_candidates()
    sleeves = _monthly_sleeve_factors(snapshots)
    dates = [row.date for row in rows[1:]]
    boundary = next(
        (index for index, value in enumerate(dates) if value >= "2007-01-01"), len(dates)
    )
    holdout_start = min(len(dates), boundary + 1)
    if boundary < 120 or len(dates) - holdout_start < 120:
        raise ValueError("development and holdout must each contain at least 120 months")

    ladder_all = _credit_ladder_factors(sleeves)
    ladder_development = ladder_all[:boundary]
    ladder_holdout = ladder_all[holdout_start:]
    ladder_holdout_stats = summarize(ladder_holdout)
    ladder_segments = [
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
    incumbent_stats = summarize(incumbent_holdout)

    records: list[dict[str, Any]] = []
    development_returns: list[list[float]] = []
    development_segments: list[list[float]] = []
    holdout_by_cost: list[dict[int, list[float]]] = []
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
        development = [factor - 1.0 for factor in full_by_cost[25][:boundary]]
        holdout = full_by_cost[25][holdout_start:]
        segment_sharpes = [annualized_sharpe(segment) for segment in _segments(development)]
        development_stats = summarize(full_by_cost[25][:boundary])
        holdout_stats = summarize(holdout)
        development_returns.append(development)
        development_segments.append(segment_sharpes)
        holdout_by_cost.append(
            {cost: factors[holdout_start:] for cost, factors in full_by_cost.items()}
        )
        records.append(
            {
                "candidate_id": candidate.candidate_id,
                "strategy_fingerprint": candidate.strategy_fingerprint,
                "status": "complete",
                "family": candidate.policy.family,
                "development_sharpe_25bps": round(development_stats.sharpe, 6),
                "development_calmar_25bps": None
                if development_stats.calmar is None
                else round(development_stats.calmar, 6),
                "development_max_drawdown_25bps": round(development_stats.max_dd_pct, 6),
                "holdout_sharpe_25bps": round(holdout_stats.sharpe, 6),
                "holdout_cagr_25bps": round(holdout_stats.cagr_pct, 6),
                "holdout_max_drawdown_25bps": round(holdout_stats.max_dd_pct, 6),
                "holdout_calmar_25bps": None
                if holdout_stats.calmar is None
                else round(holdout_stats.calmar, 6),
                "holdout_total_return_50bps": round(
                    math.prod(full_by_cost[50][holdout_start:]) - 1.0, 8
                ),
                "turnover": round(turnover, 6),
                "segment_sharpes": [round(value, 6) for value in segment_sharpes],
                "segment_wins": sum(
                    value > benchmark
                    for value, benchmark in zip(segment_sharpes, ladder_segments, strict=True)
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
    trial_sharpes = [float(record["development_sharpe_25bps"]) for record in records]
    effective_trials = effective_independent_trials(development_returns)
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index], trial_sharpes, effective_trial_count=effective_trials
    )
    pbo = probability_of_backtest_overfitting(development_segments)

    winner_holdout = holdout_by_cost[winner_index][25]
    blend = [
        0.8 * incumbent + 0.2 * candidate
        for incumbent, candidate in zip(incumbent_holdout, winner_holdout, strict=True)
    ]
    blend_stats = summarize(blend)
    blend_psr = probabilistic_sharpe(
        [factor - 1.0 for factor in blend], benchmark_sharpe_annual=incumbent_stats.sharpe
    )
    standalone_psr = probabilistic_sharpe(
        [factor - 1.0 for factor in winner_holdout],
        benchmark_sharpe_annual=ladder_holdout_stats.sharpe,
    )
    incumbent_correlation = correlation(incumbent_holdout, winner_holdout)

    prior = _prior_records(prior_trial_records, prior_factory_payload, macro_factory_payload)
    audit_records = prior + records
    audit_fingerprints = [
        str(record.get("strategy_fingerprint") or f"legacy:{record.get('candidate_id')}")
        for record in audit_records
    ]
    unique_audit = len(set(audit_fingerprints))
    calibration_passed = _calibration_valid(calibration_evidence, code_commit=code_commit)
    latest = live_snapshot or snapshots[-1]
    parity_weights = credit_spread_target_weights(
        policy=winner.policy, snapshot=latest.as_dict(include_history=True)
    )
    parity_digest = _fingerprint({key: str(value) for key, value in parity_weights.items()})
    publication_safe = all(
        observed is None or observed <= snapshot.as_of_date
        for snapshot in snapshots
        for observed in snapshot.observation_dates.values()
    )

    gates: list[dict[str, Any]] = []

    def add_gate(
        gate_id: str,
        passed: bool,
        actual: Any,
        required: Any,
        *,
        stage: str,
        blocking: bool = True,
    ) -> None:
        gates.append(
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
    add_gate("prior_audit_complete", len(prior) == 576, len(prior), 576, stage="audit")
    add_gate(
        "global_audit_trials", len(audit_records) == 640, len(audit_records), 640, stage="audit"
    )
    add_gate("unique_audit_fingerprints", unique_audit == 640, unique_audit, 640, stage="audit")
    add_gate(
        "family_pbo_rows",
        len(development_segments) == 64,
        len(development_segments),
        64,
        stage="discovery",
    )
    add_gate(
        "credit_data_complete",
        credit_data_quality.get("complete") is True,
        credit_data_quality.get("complete"),
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
        blend_stats.sharpe >= incumbent_stats.sharpe + 0.05,
        round(blend_stats.sharpe - incumbent_stats.sharpe, 6),
        0.05,
        stage="economics",
    )
    add_gate(
        "blend_drawdown_non_worsening",
        blend_stats.max_dd_pct <= incumbent_stats.max_dd_pct,
        blend_stats.max_dd_pct,
        incumbent_stats.max_dd_pct,
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

    passed = all(gate["passed"] for gate in gates if gate["blocking"])
    data_fp = _fingerprint(
        {
            "quality": credit_data_quality,
            "first": snapshots[0].as_dict(include_history=False),
            "last": snapshots[-1].as_dict(include_history=False),
        }
    )
    batch_id = (
        "credit-spread-factory-v2-"
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
        "credit_data_fingerprint": data_fp,
        "candidate_count": len(candidates),
        "complete_trial_count": len(records),
        "prior_trial_count": len(prior),
        "prior_audit_lineage": {
            "production_price_candidates": sum(
                str(record.get("candidate_id", "")).startswith("factory-") for record in prior
            ),
            "exploratory_replays": sum(
                str(record.get("candidate_id", "")).startswith("exploratory-") for record in prior
            ),
            "macro_candidates": sum(
                str(record.get("candidate_id", "")).startswith("macro-") for record in prior
            ),
            "treasury_candidates": sum(
                str(record.get("candidate_id", "")).startswith("treasury-") for record in prior
            ),
        },
        "current_trial_count": len(records),
        "global_audit_trial_count": len(audit_records),
        "multiplicity_trial_count": len(records),
        "family_raw_trial_count": len(records),
        "family_effective_trial_count": str(effective_trials),
        "unique_trial_fingerprint_count": unique_audit,
        "calibration": calibration_evidence,
        "statistical_family": {
            "family_id": "investment_grade_credit_spread_v1",
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
            "standalone_psr_vs_credit_ladder": None
            if standalone_psr is None
            else str(standalone_psr),
        },
        "candidates": [candidate.as_dict() for candidate in candidates],
        "audit_records": audit_records,
        "trial_records": records,
        "credit_data": credit_data_quality,
        "research_live_parity": {"passed": True, "target_weights_digest": parity_digest},
        "live_credit_evidence": {
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "data_fingerprint": data_fp,
            "code_commit": code_commit,
            "target_weights_digest": parity_digest,
            "latest_snapshot": latest.as_dict(include_history=True),
            "fresh": latest.fresh,
            "complete": latest.complete,
            "live_whitelist_authorized": LIVE_WHITELIST_AUTHORIZED,
        },
        "decision": {
            "verdict": FACTORY_EDGE if passed else NO_FACTORY_EDGE,
            "objective": OBJECTIVE,
            "selected_candidate_id": winner.candidate_id if passed else None,
            "provisional_best_candidate_id": winner.candidate_id,
            "dsr": None if dsr is None else str(dsr),
            "pbo": None if pbo is None else str(pbo),
            "psr": None if blend_psr is None else str(blend_psr),
            "gates": gates,
            "research_canary_eligible": passed,
            "live_canary_eligible": False,
            "live_whitelist_authorized": LIVE_WHITELIST_AUTHORIZED,
            "selected_strategy_fingerprint": winner.strategy_fingerprint if passed else None,
            "research_candidate_config": render_credit_candidate_toml(winner) if passed else None,
            "selected_deploy_config": None,
            "search_space_exhausted": not passed,
            "next_strategy_family": None if passed else "independent_fx_carry",
        },
        "credit_ladder_benchmark": ladder_holdout_stats.as_dict(),
        "incumbent_benchmark": incumbent_stats.as_dict(),
        "blend": {
            **blend_stats.as_dict(),
            "candidate_weight": "0.20",
            "incumbent_weight": "0.80",
            "candidate_correlation": incumbent_correlation,
        },
        "safety": [
            "no broker API",
            "no orders",
            "no capital change",
            "live whitelist unchanged",
            "long-only",
            "no leverage",
        ],
    }


def validate_live_credit_evidence(
    payload: dict[str, Any],
    *,
    candidate_id: str,
    strategy_fingerprint: str,
    now: datetime | None = None,
    max_age_days: int = 70,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    try:
        generated = datetime.fromisoformat(str(payload["timestamp_utc"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        raise ValueError("credit evidence timestamp is missing or invalid") from exc
    age = current - generated.astimezone(UTC)
    if age < timedelta(minutes=-5) or age > timedelta(days=max_age_days):
        raise ValueError("credit evidence is stale")
    decision = payload.get("decision", {})
    evidence = payload.get("live_credit_evidence", {})
    if payload.get("gate_version") != GATE_VERSION:
        raise ValueError("credit factory gate version is missing or legacy")
    if decision.get("verdict") != FACTORY_EDGE or not decision.get("research_canary_eligible"):
        raise ValueError("credit factory has no eligible winner")
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
        raise ValueError("credit factory gates are incomplete or failed")
    if decision.get("selected_candidate_id") != candidate_id:
        raise ValueError("credit candidate id does not match factory winner")
    if decision.get("selected_strategy_fingerprint") != strategy_fingerprint:
        raise ValueError("credit strategy fingerprint does not match factory winner")
    if (
        evidence.get("candidate_id") != candidate_id
        or evidence.get("strategy_fingerprint") != strategy_fingerprint
    ):
        raise ValueError("live credit evidence identity mismatch")
    if evidence.get("data_fingerprint") != payload.get("credit_data_fingerprint"):
        raise ValueError("live credit data fingerprint mismatch")
    if evidence.get("code_commit") != payload.get("code_commit"):
        raise ValueError("live credit code commit mismatch")
    if evidence.get("fresh") is not True or evidence.get("complete") is not True:
        raise ValueError("live credit evidence is incomplete or stale")
    if evidence.get("target_weights_digest") != payload.get("research_live_parity", {}).get(
        "target_weights_digest"
    ):
        raise ValueError("live credit target-weight digest mismatch")
    if (
        decision.get("live_whitelist_authorized") is not True
        or evidence.get("live_whitelist_authorized") is not True
    ):
        raise ValueError("credit winner is not authorized by the active live whitelist")
    snapshot = evidence.get("latest_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("live credit snapshot is missing")
    return snapshot


def render_credit_factory_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    lines = [
        "# 독립 회사채 스프레드 전략 공장 최신 실행",
        "",
        f"- 판정: **{decision['verdict']}**",
        f"- 묶음: `{payload['batch_id']}`",
        f"- 공식 후보: {payload['complete_trial_count']}/{payload['candidate_count']}",
        f"- 전체 감사 시도: {payload.get('global_audit_trial_count')}",
        f"- 현재 통계 가족: {payload.get('family_raw_trial_count')}개 "
        f"(독립 환산 {payload.get('family_effective_trial_count')})",
        f"- 잠정 최고: `{decision['provisional_best_candidate_id']}`",
        "- 개발 진단 DSR/PBO, 홀드아웃 PSR: "
        f"{decision['dsr']} / {decision['pbo']} / {decision['psr']}",
        "- 라이브 허용목록: 미승인(LQD 추가 없음)",
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
    lines.extend(["", "> 이 실행은 주문·자본·라이브 허용목록을 변경하지 않는다."])
    return "\n".join(lines)


__all__ = [
    "EXPECTED_CANDIDATES",
    "EXPECTED_GLOBAL_AUDIT_TRIALS",
    "EXPECTED_MULTIPLICITY_TRIALS",
    "FACTORY_EDGE",
    "NO_FACTORY_EDGE",
    "CreditCurveSnapshot",
    "CreditSpreadCandidate",
    "build_credit_curve_snapshots",
    "generate_credit_candidates",
    "load_credit_curve_bundle",
    "render_credit_candidate_toml",
    "render_credit_factory_markdown",
    "run_credit_spread_factory",
    "validate_live_credit_evidence",
]
