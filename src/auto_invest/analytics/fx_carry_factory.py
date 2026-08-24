"""Spec 155: point-in-time foreign-exchange carry strategy factory."""

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
    PAPER_PSR_MIN,
    PBO_DIAGNOSTIC_MAX,
)
from auto_invest.analytics.global_trend import gold_total_return_factors
from auto_invest.analytics.multi_asset_trend import bond_total_return_factors, correlation
from auto_invest.analytics.risk_managed_beta import (
    MonthlyRow,
    market_total_return_factors,
    summarize,
)
from auto_invest.config.rules import FxCarryPolicyConfig, PortfolioRebalanceConfig
from auto_invest.market_data.public_data import SeriesPoint, parse_fred_csv
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.strategy.rebalance import fx_carry_target_weights

SCHEMA_VERSION = "1.0"
EXPECTED_CANDIDATES = 16
EXPECTED_PRIOR_TRIALS = 640
EXPECTED_GLOBAL_AUDIT_TRIALS = 656
EXPECTED_MULTIPLICITY_TRIALS = 16
FACTORY_EDGE = "FACTORY_EDGE"
PAPER_CHALLENGER = "PAPER_CHALLENGER"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
OBJECTIVE = "alternative_return_diversifier"
FAMILIES = ("pure_carry", "carry_momentum", "carry_value", "defensive_carry")
CURRENCIES = ("AUD", "CAD", "JPY", "GBP", "USD")
FOREIGN_CURRENCIES = CURRENCIES[:-1]
SPOT_SERIES = {
    "AUD": ("DEXUSAL", False),
    "CAD": ("DEXCAUS", True),
    "JPY": ("DEXJPUS", True),
    "GBP": ("DEXUSUK", False),
}
RATE_SERIES = {
    "AUD": "IRSTCI01AUM156N",
    "CAD": "IRSTCI01CAM156N",
    "JPY": "IRSTCI01JPM156N",
    "GBP": "IRSTCI01GBM156N",
    "USD": "IRSTCI01USM156N",
}
EXECUTION_SYMBOLS = {"AUD": "FXA", "CAD": "FXC", "JPY": "FXY", "GBP": "FXB", "USD": "UUP"}
SERIES_IDS = tuple(series_id for series_id, _ in SPOT_SERIES.values()) + tuple(
    RATE_SERIES.values()
)
LIVE_WHITELIST_AUTHORIZED = False


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class FxCarrySnapshot:
    as_of_date: str
    usd_spot: dict[str, Decimal | None]
    short_rates: dict[str, Decimal | None]
    observation_dates: dict[str, str | None]
    spot_history: dict[str, tuple[Decimal | None, ...]]
    rate_history: dict[str, tuple[Decimal | None, ...]]
    complete: bool
    fresh: bool

    def as_dict(self, *, include_history: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "as_of_date": self.as_of_date,
            "usd_spot": _decimal_map(self.usd_spot),
            "short_rates": _decimal_map(self.short_rates),
            "observation_dates": dict(self.observation_dates),
            "complete": self.complete,
            "fresh": self.fresh,
        }
        if include_history:
            payload["spot_history"] = _history_map(self.spot_history)
            payload["rate_history"] = _history_map(self.rate_history)
        return payload


def _decimal_map(values: dict[str, Decimal | None]) -> dict[str, str | None]:
    return {key: None if value is None else str(value) for key, value in values.items()}


def _history_map(
    values: dict[str, tuple[Decimal | None, ...]],
) -> dict[str, list[str | None]]:
    return {
        key: [None if value is None else str(value) for value in history]
        for key, history in values.items()
    }


@dataclass(frozen=True)
class FxCarryCandidate:
    candidate_id: str
    trial_index: int
    policy: FxCarryPolicyConfig
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.policy.family,
            "policy": self.policy.model_dump(mode="json"),
            "strategy_fingerprint": self.strategy_fingerprint,
            "signal_series": list(SERIES_IDS),
            "execution_symbols": list(EXECUTION_SYMBOLS.values()),
            "research_config_text": render_fx_candidate_toml(self),
            "instrument_basis_risk": (
                "synthetic foreign cash differs from currency ETF total return"
            ),
            "live_expressible": False,
            "live_blocker": "currency ETF representatives are not in the active live whitelist",
        }


def _candidate(index: int, policy: FxCarryPolicyConfig) -> FxCarryCandidate:
    digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": policy.model_dump(mode="json")})
    provisional = FxCarryCandidate(
        candidate_id=f"fx-{policy.family}-{digest[7:19]}",
        trial_index=index,
        policy=policy,
        strategy_fingerprint="pending",
    )
    parsed = tomllib.loads(render_fx_candidate_toml(provisional))
    config = PortfolioRebalanceConfig.model_validate(parsed["portfolio"])
    return replace(provisional, strategy_fingerprint=strategy_fingerprint_digest(config))


def generate_fx_candidates() -> tuple[FxCarryCandidate, ...]:
    candidates: list[FxCarryCandidate] = []
    for family in FAMILIES:
        for lookback in (3, 12):
            for max_foreign_weight in (Decimal("0.5"), Decimal("1.0")):
                candidates.append(
                    _candidate(
                        len(candidates) + 1,
                        FxCarryPolicyConfig(
                            family=family,
                            lookback_months=lookback,
                            max_foreign_weight=max_foreign_weight,
                        ),
                    )
                )
    if len(candidates) != EXPECTED_CANDIDATES:
        raise RuntimeError("FX candidate count contract violated")
    if len({candidate.candidate_id for candidate in candidates}) != EXPECTED_CANDIDATES:
        raise RuntimeError("FX candidate id uniqueness contract violated")
    if len({candidate.strategy_fingerprint for candidate in candidates}) != EXPECTED_CANDIDATES:
        raise RuntimeError("FX strategy fingerprint uniqueness contract violated")
    return tuple(candidates)


def render_fx_candidate_toml(candidate: FxCarryCandidate) -> str:
    policy = candidate.policy
    return f'''[portfolio]
id = "{candidate.candidate_id}"
universe = ["FXA", "FXC", "FXY", "FXB", "UUP"]
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

[portfolio.fx_carry_policy]
family = "{policy.family}"
lookback_months = {policy.lookback_months}
top_n = {policy.top_n}
risk_lookback_months = {policy.risk_lookback_months}
value_lookback_months = {policy.value_lookback_months}
max_foreign_weight = "{policy.max_foreign_weight}"
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


def build_fx_snapshots(
    target_dates: list[str],
    *,
    series: dict[str, list[SeriesPoint]],
    max_spot_staleness_days: int = 14,
    max_rate_staleness_days: int = 100,
) -> list[FxCarrySnapshot]:
    spot_histories: dict[str, list[Decimal | None]] = {currency: [] for currency in CURRENCIES}
    rate_histories: dict[str, list[Decimal | None]] = {currency: [] for currency in CURRENCIES}
    snapshots: list[FxCarrySnapshot] = []
    for raw_target in target_dates:
        target = date.fromisoformat(raw_target)
        spot_cutoff = target - timedelta(days=1) if target.day == 1 else target
        spots: dict[str, Decimal | None] = {"USD": Decimal("1")}
        rates: dict[str, Decimal | None] = {}
        observations: dict[str, str | None] = {}
        spot_ages: list[int] = []
        rate_ages: list[int] = []
        for currency, (series_id, inverse) in SPOT_SERIES.items():
            point = _latest_point(series.get(series_id, []), spot_cutoff)
            value = None if point is None else point.value
            if value is not None and inverse:
                if value <= 0:
                    raise ValueError(f"{series_id} inverse quote must be positive")
                value = Decimal("1") / value
            if value is not None and value <= 0:
                raise ValueError(f"{series_id} normalized quote must be positive")
            spots[currency] = value
            observations[series_id] = None if point is None else point.date
            if point is not None:
                spot_ages.append((spot_cutoff - date.fromisoformat(point.date)).days)
        observations["USD_SPOT"] = raw_target

        for currency, series_id in RATE_SERIES.items():
            point = _latest_point(series.get(series_id, []), target, monthly_lag=True)
            rates[currency] = None if point is None else point.value
            observations[series_id] = None if point is None else point.date
            if point is not None:
                rate_ages.append((target - date.fromisoformat(point.date)).days)

        for currency in CURRENCIES:
            spot_histories[currency].append(spots.get(currency))
            rate_histories[currency].append(rates.get(currency))
        complete = all(spots.get(currency) is not None for currency in CURRENCIES) and all(
            rates.get(currency) is not None for currency in CURRENCIES
        )
        fresh = bool(
            complete
            and len(spot_ages) == len(FOREIGN_CURRENCIES)
            and all(0 <= age <= max_spot_staleness_days for age in spot_ages)
            and len(rate_ages) == len(CURRENCIES)
            and all(0 <= age <= max_rate_staleness_days for age in rate_ages)
        )
        snapshots.append(
            FxCarrySnapshot(
                as_of_date=raw_target,
                usd_spot=spots,
                short_rates=rates,
                observation_dates=observations,
                spot_history={key: tuple(values) for key, values in spot_histories.items()},
                rate_history={key: tuple(values) for key, values in rate_histories.items()},
                complete=complete,
                fresh=fresh,
            )
        )
    return snapshots


def load_fx_bundle(
    data_dir: Path, target_dates: list[str]
) -> tuple[list[FxCarrySnapshot], dict[str, Any]]:
    series: dict[str, list[SeriesPoint]] = {}
    quality_rows: dict[str, Any] = {}
    spot_ids = {series_id for series_id, _ in SPOT_SERIES.values()}
    for series_id in SERIES_IDS:
        path = data_dir / "fred" / f"{series_id}.csv"
        points = parse_fred_csv(path.read_text(encoding="utf-8"))
        series[series_id] = points
        observed = [point for point in points if point.value is not None]
        required = 14000 if series_id in spot_ids else 400
        quality_rows[series_id] = {
            "rows": len(points),
            "observed_rows": len(observed),
            "first_date": observed[0].date if observed else None,
            "last_date": observed[-1].date if observed else None,
            # H.10 includes expected holiday placeholders. The collector contract
            # measures dated rows; monthly snapshots separately prove usable values.
            "complete": len(points) >= required,
            "source": "Federal Reserve H.10 via FRED"
            if series_id in spot_ids
            else "OECD Main Economic Indicators via FRED",
            "citation_required": series_id not in spot_ids,
            "public_domain": series_id in spot_ids,
        }
    snapshots = build_fx_snapshots(target_dates, series=series)
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
        "return_model": "unlevered_foreign_cash_spot_plus_prior_short_rate",
        "instrument_basis_risk": (
            "synthetic foreign cash differs from CurrencyShares ETF total return"
        ),
        "development_window": "1990-01-01..2006-12-31",
        "holdout_window": "2007-02-01..latest",
    }
    return snapshots, quality


def _sleeve_factors(snapshots: list[FxCarrySnapshot]) -> dict[str, list[float | None]]:
    output: dict[str, list[float | None]] = {
        symbol: [] for symbol in EXECUTION_SYMBOLS.values()
    }
    for previous, current in zip(snapshots[:-1], snapshots[1:], strict=True):
        for currency, symbol in EXECUTION_SYMBOLS.items():
            rate = previous.short_rates.get(currency)
            prior_spot = previous.usd_spot.get(currency)
            current_spot = current.usd_spot.get(currency)
            if rate is None or prior_spot is None or current_spot is None:
                output[symbol].append(None)
                continue
            interest = Decimal("1") + rate / Decimal("1200")
            factor = interest * current_spot / prior_spot
            if factor <= 0:
                raise ValueError("FX return model produced a non-positive factor")
            output[symbol].append(float(factor))
    return output


def _candidate_factors(
    candidate: FxCarryCandidate,
    snapshots: list[FxCarrySnapshot],
    sleeves: dict[str, list[float | None]],
    *,
    cost_bps: int,
) -> tuple[list[float], float]:
    symbols = tuple(EXECUTION_SYMBOLS.values())
    previous_weights = {symbol: Decimal("0") for symbol in symbols}
    previous_weights["UUP"] = Decimal("1")
    output: list[float] = []
    turnover_total = Decimal("0")
    for index, snapshot in enumerate(snapshots[:-1]):
        try:
            weights = fx_carry_target_weights(
                policy=candidate.policy,
                snapshot=snapshot.as_dict(include_history=True),
            )
        except ValueError:
            weights = {symbol: Decimal("0") for symbol in symbols}
            weights["UUP"] = Decimal("1")
        turnover = sum(abs(weights[symbol] - previous_weights[symbol]) for symbol in symbols)
        gross = sum(
            weights[symbol]
            * Decimal(str(1.0 if sleeves[symbol][index] is None else sleeves[symbol][index]))
            for symbol in symbols
        )
        net = gross * max(Decimal("0"), Decimal("1") - turnover * cost_bps / Decimal("10000"))
        output.append(float(net))
        turnover_total += turnover
        previous_weights = weights
    return output, float(turnover_total)


def _currency_ladder_factors(sleeves: dict[str, list[float | None]]) -> list[float]:
    symbols = tuple(EXECUTION_SYMBOLS.values())
    return [
        sum(sleeves[symbol][index] or 1.0 for symbol in symbols) / len(symbols)
        for index in range(len(sleeves["UUP"]))
    ]


def _segments(returns: list[float], count: int = 10) -> list[list[float]]:
    size = len(returns) // count
    if size < 2:
        return []
    return [
        returns[index * size : (index + 1) * size if index < count - 1 else len(returns)]
        for index in range(count)
    ]


def _prior_records(prior_factory_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = prior_factory_payload.get("audit_records", [])
    unique: dict[str, dict[str, Any]] = {}
    for record in raw if isinstance(raw, list) else []:
        if (
            not isinstance(record, dict)
            or record.get("status") not in {"complete", "EXPLORATORY_REJECTED"}
            or not isinstance(record.get("segment_sharpes"), list)
            or len(record["segment_sharpes"]) != 10
        ):
            continue
        identity = str(record.get("strategy_fingerprint") or record.get("candidate_id") or "")
        if identity:
            unique.setdefault(identity, record)
    return [unique[key] for key in sorted(unique)][:EXPECTED_PRIOR_TRIALS]


def _calibration_valid(payload: dict[str, Any], *, code_commit: str) -> bool:
    scenario = payload.get("scenario", {})
    family = payload.get("family_calibrations", {}).get("16", {})
    thresholds = payload.get("thresholds", {})
    return bool(
        payload.get("gate_version") == GATE_VERSION
        and payload.get("verdict") == CALIBRATED
        and payload.get("code_commit") == code_commit
        and int(scenario.get("repetitions", 0)) >= 200
        and family.get("live_calibrated") is True
        and float(family.get("null_false_acceptance_rate", 1.0)) <= 0.05
        and float(family.get("target_live_detection_rate", 0.0)) >= 0.80
        and float(thresholds.get("holdout_psr_min", 0.0)) == HOLDOUT_PSR_MIN
        and float(thresholds.get("paper_psr_min", 0.0)) == PAPER_PSR_MIN
    )


def run_fx_carry_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    snapshots: list[FxCarrySnapshot],
    *,
    fx_data_quality: dict[str, Any],
    prior_factory_payload: dict[str, Any],
    calibration_evidence: dict[str, Any],
    live_snapshot: FxCarrySnapshot | None = None,
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    if len(rows) != len(gold_levels) or len(snapshots) != len(rows):
        raise ValueError("rows, gold, and FX snapshots must align")
    candidates = generate_fx_candidates()
    sleeves = _sleeve_factors(snapshots)
    dates = [row.date for row in rows[1:]]
    boundary = next(
        (index for index, value in enumerate(dates) if value >= "2007-01-01"), len(dates)
    )
    holdout_start = min(len(dates), boundary + 1)
    if boundary < 120 or len(dates) - holdout_start < 120:
        raise ValueError("development and holdout must each contain at least 120 months")

    usd_all = [factor or 1.0 for factor in sleeves["UUP"]]
    ladder_all = _currency_ladder_factors(sleeves)
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
        development = [
            candidate_factor / usd_factor - 1.0
            for candidate_factor, usd_factor in zip(
                full_by_cost[25][:boundary], usd_all[:boundary], strict=True
            )
        ]
        holdout = full_by_cost[25][holdout_start:]
        holdout_excess = [
            candidate_factor / usd_factor - 1.0
            for candidate_factor, usd_factor in zip(
                holdout, usd_all[holdout_start:], strict=True
            )
        ]
        segment_sharpes = [annualized_sharpe(segment) for segment in _segments(development)]
        development_stats = summarize([value + 1.0 for value in development])
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
                "development_sharpe_excess_25bps": round(development_stats.sharpe, 6),
                "development_max_drawdown_25bps": round(
                    development_stats.max_dd_pct, 6
                ),
                "holdout_sharpe_25bps": round(holdout_stats.sharpe, 6),
                "holdout_excess_sharpe_25bps": round(annualized_sharpe(holdout_excess), 6),
                "holdout_cagr_25bps": round(holdout_stats.cagr_pct, 6),
                "holdout_max_drawdown_25bps": round(holdout_stats.max_dd_pct, 6),
                "holdout_excess_total_return_50bps": round(
                    math.prod(
                        candidate_factor / usd_factor
                        for candidate_factor, usd_factor in zip(
                            full_by_cost[50][holdout_start:],
                            usd_all[holdout_start:],
                            strict=True,
                        )
                    )
                    - 1.0,
                    8,
                ),
                "turnover": round(turnover, 6),
                "segment_sharpes": [round(value, 6) for value in segment_sharpes],
                "segment_wins": sum(value > 0 for value in segment_sharpes),
            }
        )

    winner_index = max(
        range(len(records)),
        key=lambda index: (
            records[index]["development_sharpe_excess_25bps"],
            -records[index]["development_max_drawdown_25bps"],
            candidates[index].candidate_id,
        ),
    )
    winner = candidates[winner_index]
    winner_record = records[winner_index]
    trial_sharpes = [float(record["development_sharpe_excess_25bps"]) for record in records]
    effective_trials = effective_independent_trials(development_returns)
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index], trial_sharpes, effective_trial_count=effective_trials
    )
    pbo = probability_of_backtest_overfitting(development_segments)

    winner_holdout = holdout_by_cost[winner_index][25]
    winner_excess = [
        candidate_factor / usd_factor - 1.0
        for candidate_factor, usd_factor in zip(
            winner_holdout, usd_all[holdout_start:], strict=True
        )
    ]
    holdout_psr = probabilistic_sharpe(winner_excess)
    blend = [
        0.8 * incumbent + 0.2 * candidate
        for incumbent, candidate in zip(incumbent_holdout, winner_holdout, strict=True)
    ]
    blend_stats = summarize(blend)
    blend_psr = probabilistic_sharpe(
        [factor - 1.0 for factor in blend], benchmark_sharpe_annual=incumbent_stats.sharpe
    )
    incumbent_correlation = correlation(incumbent_holdout, winner_holdout)

    prior = _prior_records(prior_factory_payload)
    audit_records = prior + records
    audit_fingerprints = [
        str(record.get("strategy_fingerprint") or f"legacy:{record.get('candidate_id')}")
        for record in audit_records
    ]
    unique_audit = len(set(audit_fingerprints))
    calibration_passed = _calibration_valid(calibration_evidence, code_commit=code_commit)
    latest = live_snapshot or snapshots[-1]
    parity_weights = fx_carry_target_weights(
        policy=winner.policy, snapshot=latest.as_dict(include_history=True)
    )
    parity_digest = _fingerprint({key: str(value) for key, value in parity_weights.items()})
    publication_safe = all(
        observed is None or observed <= snapshot.as_of_date
        for snapshot in snapshots
        for observed in snapshot.observation_dates.values()
    )
    excess_50 = float(winner_record["holdout_excess_total_return_50bps"])
    blend_improvement = blend_stats.sharpe - incumbent_stats.sharpe

    gates: list[dict[str, Any]] = []
    paper_gates: list[dict[str, Any]] = []

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

    def add_paper_gate(gate_id: str, passed: bool, actual: Any, required: Any) -> None:
        paper_gates.append(
            {
                "gate_id": gate_id,
                "passed": bool(passed),
                "actual": str(actual),
                "required": str(required),
                "stage": "paper",
                "blocking": False,
            }
        )

    add_gate(
        "gate_calibration",
        calibration_passed,
        calibration_evidence.get("verdict"),
        CALIBRATED,
        stage="calibration",
    )
    add_gate("complete_family_trials", len(records) == 16, len(records), 16, stage="audit")
    add_gate("prior_audit_complete", len(prior) == 640, len(prior), 640, stage="audit")
    add_gate(
        "global_audit_trials",
        len(audit_records) == 656,
        len(audit_records),
        656,
        stage="audit",
    )
    add_gate("unique_audit_fingerprints", unique_audit == 656, unique_audit, 656, stage="audit")
    add_gate(
        "family_pbo_rows",
        len(development_segments) == 16,
        len(development_segments),
        16,
        stage="discovery",
    )
    add_gate(
        "fx_data_complete",
        fx_data_quality.get("complete") is True,
        fx_data_quality.get("complete"),
        True,
        stage="data",
    )
    add_gate("publication_safe", publication_safe, publication_safe, True, stage="data")
    add_gate("live_data_complete", latest.complete, latest.complete, True, stage="data")
    add_gate("live_data_fresh", latest.fresh, latest.fresh, True, stage="data")
    add_gate("research_live_parity", bool(parity_digest), bool(parity_digest), True, stage="parity")
    add_gate("development_months", boundary >= 120, boundary, 120, stage="split")
    add_gate(
        "embargo_months",
        holdout_start - boundary == 1,
        holdout_start - boundary,
        1,
        stage="split",
    )
    add_gate("holdout_months", len(winner_holdout) >= 120, len(winner_holdout), 120, stage="split")
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
        pbo is not None and pbo <= PBO_DIAGNOSTIC_MAX,
        pbo,
        PBO_DIAGNOSTIC_MAX,
        stage="discovery",
        blocking=False,
    )
    add_gate(
        "holdout_excess_psr",
        holdout_psr is not None
        and holdout_psr >= Decimal(str(HOLDOUT_PSR_MIN)),
        holdout_psr,
        HOLDOUT_PSR_MIN,
        stage="holdout",
    )
    add_gate(
        "holdout_excess_50bps_positive",
        excess_50 > 0.0,
        excess_50,
        "> 0",
        stage="economics",
    )
    add_gate(
        "incumbent_correlation",
        incumbent_correlation < 0.80,
        incumbent_correlation,
        "< 0.80",
        stage="economics",
    )
    add_gate(
        "blend_sharpe_improvement",
        blend_improvement >= 0.05,
        round(blend_improvement, 6),
        ">= 0.05",
        stage="economics",
    )
    add_gate(
        "blend_drawdown_non_worsening",
        blend_stats.max_dd_pct <= incumbent_stats.max_dd_pct,
        blend_stats.max_dd_pct,
        incumbent_stats.max_dd_pct,
        stage="economics",
    )

    common_passed = all(
        gate["passed"]
        for gate in gates
        if gate["blocking"] and gate["stage"] not in {"holdout", "economics"}
    )
    live_passed = common_passed and all(
        gate["passed"]
        for gate in gates
        if gate["blocking"] and gate["stage"] in {"holdout", "economics"}
    )
    add_paper_gate(
        "paper_holdout_psr",
        holdout_psr is not None and holdout_psr >= Decimal(str(PAPER_PSR_MIN)),
        holdout_psr,
        PAPER_PSR_MIN,
    )
    add_paper_gate("paper_excess_50bps_positive", excess_50 > 0.0, excess_50, "> 0")
    add_paper_gate(
        "paper_incumbent_correlation",
        incumbent_correlation < 0.80,
        incumbent_correlation,
        "< 0.80",
    )
    add_paper_gate(
        "paper_blend_sharpe_non_declining",
        blend_improvement >= 0.0,
        round(blend_improvement, 6),
        ">= 0.0",
    )
    add_paper_gate(
        "paper_blend_drawdown_bounded",
        blend_stats.max_dd_pct <= incumbent_stats.max_dd_pct * 1.20,
        blend_stats.max_dd_pct,
        round(incumbent_stats.max_dd_pct * 1.20, 6),
    )
    paper_passed = common_passed and all(gate["passed"] for gate in paper_gates)
    verdict = FACTORY_EDGE if live_passed else PAPER_CHALLENGER if paper_passed else NO_FACTORY_EDGE

    data_fingerprint = _fingerprint(
        {
            "quality": fx_data_quality,
            "first": snapshots[0].as_dict(include_history=False),
            "last": snapshots[-1].as_dict(include_history=False),
        }
    )
    batch_id = "fx-carry-factory-" + _fingerprint(
        {
            "code_commit": code_commit,
            "data": data_fingerprint,
            "candidates": [candidate.candidate_id for candidate in candidates],
            "gate": GATE_VERSION,
        }
    )[7:19]
    research_candidate = winner.as_dict() if live_passed else None
    paper_candidate = winner.as_dict() if paper_passed and not live_passed else None
    decision = {
        "verdict": verdict,
        "objective": OBJECTIVE,
        "provisional_best_candidate_id": winner.candidate_id,
        "selected_candidate_id": winner.candidate_id if live_passed else None,
        "paper_candidate_id": winner.candidate_id if paper_passed and not live_passed else None,
        "selected_strategy_fingerprint": winner.strategy_fingerprint if live_passed else None,
        "research_canary_eligible": live_passed,
        "paper_forward_eligible": paper_passed and not live_passed,
        "live_whitelist_authorized": LIVE_WHITELIST_AUTHORIZED,
        "selected_deploy_config": None,
        "gates": gates,
        "paper_gates": paper_gates,
        "dsr": None if dsr is None else str(dsr),
        "pbo": None if pbo is None else str(pbo),
        "psr": None if holdout_psr is None else str(holdout_psr),
        "blend_psr": None if blend_psr is None else str(blend_psr),
        "next_strategy_family": (
            "hardened_canary"
            if live_passed
            else "forward_paper_fx_carry"
            if paper_passed
            else "independent_commodity_term_structure"
        ),
        "search_space_exhausted": verdict == NO_FACTORY_EDGE,
    }
    family_calibration = calibration_evidence.get("family_calibrations", {}).get("16", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_version": GATE_VERSION,
        "timestamp_utc": timestamp_utc or datetime.now(UTC).isoformat(),
        "code_commit": code_commit,
        "batch_id": batch_id,
        "candidate_count": len(candidates),
        "complete_trial_count": len(records),
        "prior_trial_count": len(prior),
        "global_audit_trial_count": len(audit_records),
        "multiplicity_trial_count": len(records),
        "family_raw_trial_count": len(records),
        "family_effective_trial_count": str(effective_trials),
        "unique_trial_fingerprint_count": unique_audit,
        "fx_data": fx_data_quality,
        "fx_data_fingerprint": data_fingerprint,
        "gate_power": family_calibration,
        "development_selection": {
            "window": "1990-01-01..2006-12-31",
            "months": boundary,
            "selected_candidate_id": winner.candidate_id,
            "selection_metric": "development excess Sharpe after 25bps",
        },
        "holdout_confirmation": {
            "window": "2007-02-01..latest",
            "embargo_months": holdout_start - boundary,
            "months": len(winner_holdout),
            "psr_vs_usd_cash": None if holdout_psr is None else str(holdout_psr),
            "excess_total_return_50bps": excess_50,
        },
        "economic_comparison": {
            "incumbent_correlation": incumbent_correlation,
            "incumbent_sharpe": incumbent_stats.sharpe,
            "blend_sharpe": blend_stats.sharpe,
            "blend_sharpe_improvement": round(blend_improvement, 6),
            "incumbent_max_drawdown_pct": incumbent_stats.max_dd_pct,
            "blend_max_drawdown_pct": blend_stats.max_dd_pct,
            "currency_ladder_holdout_sharpe": summarize(ladder_all[holdout_start:]).sharpe,
        },
        "trial_records": records,
        "audit_records": audit_records,
        "development_returns": development_returns,
        "decision": decision,
        "research_candidate": research_candidate,
        "paper_candidate": paper_candidate,
        "research_live_parity": {
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "target_weights": {key: str(value) for key, value in parity_weights.items()},
            "target_weights_digest": parity_digest,
        },
        "live_fx_evidence": {
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "data_fingerprint": data_fingerprint,
            "code_commit": code_commit,
            "target_weights_digest": parity_digest,
            "fresh": latest.fresh,
            "complete": latest.complete,
            "live_whitelist_authorized": LIVE_WHITELIST_AUTHORIZED,
            "latest_snapshot": latest.as_dict(include_history=True),
        },
        "safety": [
            "research and paper-forward evidence only",
            "no broker API",
            "no orders",
            "no capital or whitelist change",
        ],
    }


def validate_live_fx_evidence(
    payload: dict[str, Any],
    *,
    candidate_id: str,
    strategy_fingerprint: str,
) -> dict[str, Any]:
    decision = payload.get("decision", {})
    evidence = payload.get("live_fx_evidence", {})
    if payload.get("gate_version") != GATE_VERSION:
        raise ValueError("FX factory gate version is missing or legacy")
    if decision.get("verdict") == PAPER_CHALLENGER:
        raise ValueError("paper FX challenger cannot access the broker")
    if decision.get("verdict") != FACTORY_EDGE or not decision.get("research_canary_eligible"):
        raise ValueError("FX factory has no eligible live-grade winner")
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
        raise ValueError("FX factory gates are incomplete or failed")
    if decision.get("selected_candidate_id") != candidate_id:
        raise ValueError("FX candidate id does not match factory winner")
    if decision.get("selected_strategy_fingerprint") != strategy_fingerprint:
        raise ValueError("FX strategy fingerprint does not match factory winner")
    if (
        evidence.get("candidate_id") != candidate_id
        or evidence.get("strategy_fingerprint") != strategy_fingerprint
    ):
        raise ValueError("live FX evidence identity mismatch")
    if evidence.get("data_fingerprint") != payload.get("fx_data_fingerprint"):
        raise ValueError("live FX data fingerprint mismatch")
    if evidence.get("code_commit") != payload.get("code_commit"):
        raise ValueError("live FX code commit mismatch")
    if evidence.get("fresh") is not True or evidence.get("complete") is not True:
        raise ValueError("live FX evidence is incomplete or stale")
    if evidence.get("target_weights_digest") != payload.get("research_live_parity", {}).get(
        "target_weights_digest"
    ):
        raise ValueError("live FX target-weight digest mismatch")
    if (
        decision.get("live_whitelist_authorized") is not True
        or evidence.get("live_whitelist_authorized") is not True
    ):
        raise ValueError("FX winner is not authorized by the active live whitelist")
    snapshot = evidence.get("latest_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("live FX snapshot is missing")
    return snapshot


def render_fx_factory_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    power = payload.get("gate_power", {})
    lines = [
        "# 독립 외환 금리차 전략 공장 최신 실행",
        "",
        f"- 판정: **{decision['verdict']}**",
        f"- 묶음: `{payload['batch_id']}`",
        f"- 공식 후보: {payload['complete_trial_count']}/{payload['candidate_count']}",
        f"- 전체 감사 시도: {payload['global_audit_trial_count']}",
        f"- 현재 통계 가족: {payload['family_raw_trial_count']}개 "
        f"(독립 환산 {payload['family_effective_trial_count']})",
        f"- 잠정 최고: `{decision['provisional_best_candidate_id']}`",
        f"- 홀드아웃 PSR: {decision['psr']}",
        "- 관문 검출력: 무신호 오탐 "
        f"{power.get('null_false_acceptance_rate')} / 샤프 0.60 검출 "
        f"{power.get('target_live_detection_rate')} / 80% 검출 최소 샤프 "
        f"{power.get('minimum_80pct_detectable_sharpe')}",
        "- 라이브 허용목록: 미승인(FXA·FXC·FXY·FXB·UUP 추가 없음)",
        "",
        "## 라이브 관문",
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
    lines.extend(
        [
            "",
            "## 무자본 종이 관문",
            "",
            "| 관문 | 상태 | 현재 | 기준 |",
            "|---|:---:|---:|---:|",
        ]
    )
    for gate in decision["paper_gates"]:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(
            f"| {gate['gate_id']} | {status} | {gate['actual']} | {gate['required']} |"
        )
    lines.extend(["", "> 이 실행은 주문·자본·라이브 허용목록을 변경하지 않는다."])
    return "\n".join(lines)


__all__ = [
    "EXPECTED_CANDIDATES",
    "EXPECTED_GLOBAL_AUDIT_TRIALS",
    "FxCarryCandidate",
    "FxCarrySnapshot",
    "build_fx_snapshots",
    "generate_fx_candidates",
    "load_fx_bundle",
    "render_fx_factory_markdown",
    "run_fx_carry_factory",
    "validate_live_fx_evidence",
]
