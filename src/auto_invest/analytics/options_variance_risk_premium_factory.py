"""Spec 164: independent options variance-risk-premium strategy factory."""

from __future__ import annotations

import csv
import io
import math
import random
import re
import statistics
import zipfile
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probabilistic_sharpe,
    probability_of_backtest_overfitting,
)
from auto_invest.analytics.commodity_term_structure_factory import (
    _calibration_valid,
    _latest_rate_before,
)
from auto_invest.analytics.edge_gate_calibration import (
    HOLDOUT_PSR_MIN,
    PAPER_PSR_MIN,
)
from auto_invest.analytics.energy_cross_market_factory import (
    _content_digest,
    _fingerprint,
    _full_controls_valid,
    _segments,
    _shift_month,
    expanding_ridge_predictions,
)
from auto_invest.analytics.risk_managed_beta import summarize
from auto_invest.market_data.public_data import SeriesPoint

SCHEMA_VERSION = "1.0"
CONSUMER_GATE_VERSION = "3.0"
EXPECTED_CANDIDATES = 16
EXPECTED_PRIOR_TRIALS = 736
EXPECTED_GLOBAL_AUDIT_TRIALS = 752
DEVELOPMENT_MONTHS = 84
EMBARGO_MONTHS = 1
MIN_HOLDOUT_MONTHS = 120
MIN_FACTOR_MONTHS = 205
OUTER_TRAIN_MONTHS = 84
OUTER_EMBARGO_MONTHS = 1
OUTER_TEST_MONTHS = 12
INNER_TRAIN_MONTHS = 48
INNER_EMBARGO_MONTHS = 1
INNER_VALIDATION_MONTHS = 12
RIDGE_ALPHA = 10.0
RIDGE_MIN_TRAIN = 60
PUT_CONTINUOUS_START = date(2007, 1, 3)
WPUT_CONTINUOUS_START = date(2006, 1, 31)
OBJECTIVE = "standalone_options_variance_risk_premium"
FACTORY_EDGE_CONFIRMED = "FACTORY_EDGE_CONFIRMED"
PAPER_EDGE_CANDIDATE = "PAPER_EDGE_CANDIDATE"
REFERENCE_EDGE_CONFIRMED_SELECTION_UNCONFIRMED = "REFERENCE_EDGE_CONFIRMED_SELECTION_UNCONFIRMED"
GATE_OR_REFERENCE_SUSPECT = "GATE_OR_REFERENCE_SUSPECT"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
SELECTION_METHOD_CONFIRMED_DIAGNOSTIC = "SELECTION_METHOD_CONFIRMED_DIAGNOSTIC"
PREMIUM_CONFIRMED_SELECTION_UNRESOLVED = "PREMIUM_CONFIRMED_SELECTION_UNRESOLVED"
NO_CROSS_INDEX_PREMIUM = "NO_CROSS_INDEX_PREMIUM"
PUT_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/PUT_History.csv"
WPUT_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/WPUT_History.csv"
VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
FRENCH_DAILY_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_Factors_daily_CSV.zip"
)
FRED_DGS3MO_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO"
INTENDED_EXPRESSIONS = ("PUTW", "cash-secured SPX put overlay")
COST_CASES = ((25, 10), (50, 25), (100, 50))


@dataclass(frozen=True)
class DailyHistory:
    rows: tuple[tuple[date, float], ...]
    content_digest: str
    ignored_pre_continuous_rows: int = 0


@dataclass(frozen=True)
class FrenchDailyFactor:
    observed_date: date
    market_return: float
    cash_return: float


@dataclass(frozen=True)
class VarianceRiskPremiumSnapshot:
    target_month: date
    source_month: date
    horizon_months: int
    vix_level: float
    implied_variance: float
    realized_variance: float
    variance_premium: float
    smoothed_variance_premium: float
    equity_trend: float
    market_drawdown: float
    vix_shock: bool
    put_excess_lag: float

    def model_features(self) -> tuple[float, ...]:
        return (
            self.vix_level / 100.0,
            self.smoothed_variance_premium,
            self.equity_trend,
            self.market_drawdown,
            self.put_excess_lag,
        )


@dataclass(frozen=True)
class OptionsPremiumPolicy:
    family: str
    horizon_months: int | None
    max_put_weight: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "horizon_months": self.horizon_months,
            "max_put_weight": str(self.max_put_weight),
            "ridge_alpha": RIDGE_ALPHA if self.family == "ridge_forecast" else None,
            "ridge_min_train": (RIDGE_MIN_TRAIN if self.family == "ridge_forecast" else None),
        }


@dataclass(frozen=True)
class OptionsPremiumCandidate:
    candidate_id: str
    trial_index: int
    policy: OptionsPremiumPolicy
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.policy.family,
            "policy": self.policy.as_dict(),
            "strategy_fingerprint": self.strategy_fingerprint,
            "research_proxy": "Cboe S&P 500 PutWrite Index (PUT)",
            "intended_expressions": list(INTENDED_EXPRESSIONS),
            "live_expressible": False,
            "live_blocker": (
                "exact executable policy, history parity, assignment, tax, margin, "
                "collateral, whitelist, and canary contracts are missing"
            ),
        }


@dataclass(frozen=True)
class OptionsPremiumBundle:
    factor_months: tuple[str, ...]
    put_factors: tuple[float, ...]
    wput_factors: tuple[float, ...]
    market_factors: tuple[float, ...]
    cash_factors: tuple[float, ...]
    features: dict[int, tuple[VarianceRiskPremiumSnapshot, ...]]
    quality: dict[str, Any]


@dataclass(frozen=True)
class _NestedSelectionResult:
    contract: dict[str, Any]
    put_factors: tuple[float, ...]
    wput_factors: tuple[float, ...]
    cash_factors: tuple[float, ...]
    market_factors: tuple[float, ...]
    passive_put_factors: tuple[float, ...]
    passive_wput_factors: tuple[float, ...]
    selected_weights: tuple[Decimal, ...]


def _parse_mmddyyyy(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date()
    except ValueError as exc:
        raise ValueError(f"Cboe date is invalid: {raw!r}") from exc


def parse_cboe_put_history(raw: bytes) -> DailyHistory:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Cboe PUT history encoding mismatch") from exc
    reader = csv.reader(io.StringIO(text))
    try:
        header = [value.strip() for value in next(reader)]
    except StopIteration as exc:
        raise ValueError("Cboe PUT history is empty") from exc
    if header != ["DATE", "PUT"]:
        raise ValueError("Cboe PUT history header mismatch")
    rows: list[tuple[date, float]] = []
    seen: set[date] = set()
    ignored = 0
    for row in reader:
        if not row or not row[0].strip():
            continue
        if len(row) != 2:
            raise ValueError("Cboe PUT history row schema mismatch")
        observed = _parse_mmddyyyy(row[0].strip())
        try:
            level = float(row[1])
        except ValueError as exc:
            raise ValueError("Cboe PUT level is invalid") from exc
        if not math.isfinite(level) or level <= 0:
            raise ValueError("Cboe PUT level must be finite and positive")
        if observed in seen:
            raise ValueError("Cboe PUT date is duplicated")
        seen.add(observed)
        if observed < PUT_CONTINUOUS_START:
            ignored += 1
            continue
        rows.append((observed, level))
    if not rows or rows[0][0] != PUT_CONTINUOUS_START:
        raise ValueError("Cboe PUT continuous history must begin on 2007-01-03")
    if [row[0] for row in rows] != sorted(row[0] for row in rows):
        raise ValueError("Cboe PUT dates must increase")
    return DailyHistory(tuple(rows), _content_digest(raw), ignored)


def parse_cboe_wput_history(raw: bytes) -> DailyHistory:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Cboe WPUT history encoding mismatch") from exc
    reader = csv.reader(io.StringIO(text))
    try:
        header = [value.strip() for value in next(reader)]
    except StopIteration as exc:
        raise ValueError("Cboe WPUT history is empty") from exc
    if header != ["DATE", "WPUT"]:
        raise ValueError("Cboe WPUT history header mismatch")
    rows: list[tuple[date, float]] = []
    seen: set[date] = set()
    for row in reader:
        if not row or not row[0].strip():
            continue
        if len(row) != 2:
            raise ValueError("Cboe WPUT history row schema mismatch")
        observed = _parse_mmddyyyy(row[0].strip())
        try:
            level = float(row[1])
        except ValueError as exc:
            raise ValueError("Cboe WPUT level is invalid") from exc
        if not math.isfinite(level) or level <= 0:
            raise ValueError("Cboe WPUT level must be finite and positive")
        if observed in seen:
            raise ValueError("Cboe WPUT date is duplicated")
        seen.add(observed)
        rows.append((observed, level))
    if not rows or rows[0][0] != WPUT_CONTINUOUS_START:
        raise ValueError("Cboe WPUT history must begin on 2006-01-31")
    if [row[0] for row in rows] != sorted(row[0] for row in rows):
        raise ValueError("Cboe WPUT dates must increase")
    return DailyHistory(tuple(rows), _content_digest(raw))


def parse_cboe_vix_history(raw: bytes) -> DailyHistory:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Cboe VIX history encoding mismatch") from exc
    reader = csv.reader(io.StringIO(text))
    try:
        header = [value.strip() for value in next(reader)]
    except StopIteration as exc:
        raise ValueError("Cboe VIX history is empty") from exc
    if header != ["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]:
        raise ValueError("Cboe VIX history header mismatch")
    rows: list[tuple[date, float]] = []
    seen: set[date] = set()
    for row in reader:
        if not row or not row[0].strip():
            continue
        if len(row) != 5:
            raise ValueError("Cboe VIX history row schema mismatch")
        observed = _parse_mmddyyyy(row[0].strip())
        try:
            level = float(row[4])
        except ValueError as exc:
            raise ValueError("Cboe VIX close is invalid") from exc
        if not math.isfinite(level) or level <= 0:
            raise ValueError("Cboe VIX close must be finite and positive")
        if observed in seen:
            raise ValueError("Cboe VIX date is duplicated")
        seen.add(observed)
        rows.append((observed, level))
    if len(rows) < 2 or [row[0] for row in rows] != sorted(row[0] for row in rows):
        raise ValueError("Cboe VIX dates are incomplete or unordered")
    return DailyHistory(tuple(rows), _content_digest(raw))


def parse_fama_french_daily(raw: bytes) -> tuple[FrenchDailyFactor, ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError("Fama-French daily ZIP must contain one CSV")
            text = archive.read(names[0]).decode("utf-8-sig")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError("Fama-French daily ZIP schema mismatch") from exc
    output: list[FrenchDailyFactor] = []
    seen: set[date] = set()
    header_found = False
    for row in csv.reader(io.StringIO(text)):
        normalized = [value.strip() for value in row]
        if normalized[:5] == ["", "Mkt-RF", "SMB", "HML", "RF"]:
            header_found = True
            continue
        if not header_found or len(row) < 5:
            continue
        key = row[0].strip()
        if not re.fullmatch(r"\d{8}", key):
            if output:
                break
            continue
        observed = date(int(key[:4]), int(key[4:6]), int(key[6:]))
        try:
            market_excess = float(row[1].strip()) / 100.0
            cash_return = float(row[4].strip()) / 100.0
        except ValueError as exc:
            raise ValueError("Fama-French daily factor is invalid") from exc
        market_return = market_excess + cash_return
        if not all(math.isfinite(value) and value > -1 for value in (market_return, cash_return)):
            raise ValueError("Fama-French daily return is invalid")
        if observed in seen:
            raise ValueError("Fama-French daily date is duplicated")
        seen.add(observed)
        output.append(FrenchDailyFactor(observed, market_return, cash_return))
    if len(output) < 2 or not header_found:
        raise ValueError("Fama-French daily coverage or header is incomplete")
    if [row.observed_date for row in output] != sorted(row.observed_date for row in output):
        raise ValueError("Fama-French daily dates must increase")
    return tuple(output)


def _month(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_end(value: date) -> date:
    return _shift_month(_month(value), 1) - timedelta(days=1)


def _last_by_month(rows: Sequence[tuple[date, float]]) -> dict[date, float]:
    output: dict[date, tuple[date, float]] = {}
    for observed, value in rows:
        current = output.get(_month(observed))
        if current is None or observed > current[0]:
            output[_month(observed)] = (observed, value)
    return {month: row[1] for month, row in output.items()}


def _monthly_french(
    rows: Sequence[FrenchDailyFactor],
) -> tuple[dict[date, float], dict[date, float], dict[date, float]]:
    grouped: dict[date, list[FrenchDailyFactor]] = defaultdict(list)
    for row in rows:
        grouped[_month(row.observed_date)].append(row)
    market: dict[date, float] = {}
    cash: dict[date, float] = {}
    realized: dict[date, float] = {}
    for month, values in grouped.items():
        if len(values) < 2:
            continue
        market[month] = math.prod(1.0 + row.market_return for row in values)
        cash[month] = math.prod(1.0 + row.cash_return for row in values)
        realized[month] = statistics.pvariance(row.market_return for row in values) * 252.0
    return market, cash, realized


def _fred_cash_crosscheck(
    points: list[SeriesPoint],
    months: Sequence[date],
    cash_factors: dict[date, float],
) -> dict[str, Any]:
    differences: list[float] = []
    for month in months:
        rate = _latest_rate_before(points, month)
        if rate is None or month not in cash_factors:
            continue
        french_annual = (cash_factors[month] ** 12.0 - 1.0) * 100.0
        differences.append(abs(float(rate) - french_annual))
    if len(differences) < MIN_FACTOR_MONTHS:
        raise ValueError("FRED DGS3MO cash cross-check coverage is incomplete")
    return {
        "overlap_months": len(differences),
        "mean_absolute_difference_percentage_points": round(statistics.mean(differences), 6),
        "maximum_absolute_difference_percentage_points": round(max(differences), 6),
        "candidate_cash_source": "Kenneth French daily RF",
        "independent_crosscheck": "FRED DGS3MO",
    }


def load_options_premium_bundle(
    put_raw: bytes,
    wput_raw: bytes,
    vix_raw: bytes,
    french_daily_raw: bytes,
    cash_points: list[SeriesPoint],
    *,
    current_date: date,
) -> OptionsPremiumBundle:
    put = parse_cboe_put_history(put_raw)
    wput = parse_cboe_wput_history(wput_raw)
    vix = parse_cboe_vix_history(vix_raw)
    french = parse_fama_french_daily(french_daily_raw)
    put_levels = _last_by_month(put.rows)
    wput_levels = _last_by_month(wput.rows)
    vix_levels = _last_by_month(vix.rows)
    market, cash, realized = _monthly_french(french)
    complete_before = _month(current_date)
    put_factors = {
        month: put_levels[month] / put_levels[_shift_month(month, -1)]
        for month in put_levels
        if month < complete_before and _shift_month(month, -1) in put_levels
    }
    wput_factors = {
        month: wput_levels[month] / wput_levels[_shift_month(month, -1)]
        for month in wput_levels
        if month < complete_before and _shift_month(month, -1) in wput_levels
    }
    market_levels: dict[date, float] = {}
    level = 1.0
    for month in sorted(market):
        level *= market[month]
        market_levels[month] = level

    factor_months: list[date] = []
    for target in sorted(put_factors):
        source = _shift_month(target, -1)
        needed = (
            target in market
            and target in cash
            and target in wput_factors
            and source in put_factors
            and source in vix_levels
            and source in realized
            and all(
                _shift_month(source, -offset) in vix_levels
                and _shift_month(source, -offset) in realized
                for offset in range(12)
            )
            and _shift_month(source, -12) in market_levels
        )
        if needed:
            factor_months.append(target)
    if len(factor_months) < MIN_FACTOR_MONTHS:
        raise ValueError("options premium alignment does not leave 205 factor months")

    features: dict[int, tuple[VarianceRiskPremiumSnapshot, ...]] = {}
    for horizon in (6, 12):
        rows: list[VarianceRiskPremiumSnapshot] = []
        for target in factor_months:
            source = _shift_month(target, -1)
            trailing = [_shift_month(source, -offset) for offset in range(horizon)]
            premiums = [(vix_levels[month] / 100.0) ** 2 - realized[month] for month in trailing]
            shock_history = [
                vix_levels[_shift_month(source, -offset)] for offset in range(1, horizon + 1)
            ]
            deviation = statistics.stdev(shock_history) if len(shock_history) > 1 else 0.0
            peak = max(value for month, value in market_levels.items() if month <= source)
            implied = (vix_levels[source] / 100.0) ** 2
            rows.append(
                VarianceRiskPremiumSnapshot(
                    target_month=target,
                    source_month=source,
                    horizon_months=horizon,
                    vix_level=vix_levels[source],
                    implied_variance=implied,
                    realized_variance=realized[source],
                    variance_premium=implied - realized[source],
                    smoothed_variance_premium=statistics.mean(premiums),
                    equity_trend=(
                        market_levels[source] / market_levels[_shift_month(source, -horizon)] - 1.0
                    ),
                    market_drawdown=market_levels[source] / peak - 1.0,
                    vix_shock=(vix_levels[source] > statistics.mean(shock_history) + deviation),
                    put_excess_lag=put_factors[source] / cash[source] - 1.0,
                )
            )
        features[horizon] = tuple(rows)

    observed_cash = [point for point in cash_points if point.value is not None]
    if not observed_cash:
        raise ValueError("FRED DGS3MO has no observed values")
    source_ages = {
        "put_age_days": (current_date - put.rows[-1][0]).days,
        "wput_age_days": (current_date - wput.rows[-1][0]).days,
        "vix_age_days": (current_date - vix.rows[-1][0]).days,
        "french_age_days": (current_date - french[-1].observed_date).days,
        "fred_age_days": (current_date - date.fromisoformat(observed_cash[-1].date)).days,
    }
    crosscheck = _fred_cash_crosscheck(cash_points, factor_months, cash)
    holdout_months = len(factor_months) - DEVELOPMENT_MONTHS - EMBARGO_MONTHS
    complete = bool(
        len(factor_months) >= MIN_FACTOR_MONTHS
        and holdout_months >= MIN_HOLDOUT_MONTHS
        and all(
            0 <= source_ages[key] <= 10
            for key in ("put_age_days", "wput_age_days", "vix_age_days", "fred_age_days")
        )
        and 0 <= source_ages["french_age_days"] <= 90
        and all(
            row.source_month == _shift_month(row.target_month, -1)
            for values in features.values()
            for row in values
        )
    )
    quality = {
        "complete": complete,
        "factor_months": len(factor_months),
        "first_factor_month": factor_months[0].isoformat(),
        "last_factor_month": factor_months[-1].isoformat(),
        "continuous_put_start": PUT_CONTINUOUS_START.isoformat(),
        "continuous_wput_start": WPUT_CONTINUOUS_START.isoformat(),
        "sparse_pre_2007_rows_ignored": put.ignored_pre_continuous_rows,
        "signal_lag": "month t features first affect target month t+1",
        "point_in_time": False,
        "revision_limitation": (
            "current public histories are source-hashed but are not vintage archives"
        ),
        "basis_risk": (
            "Cboe PUT is a hypothetical benchmark and French broad market is not exact SPX"
        ),
        "source_ages": source_ages,
        "cash_crosscheck": crosscheck,
        "sources": {
            "cboe_put": {
                "url": PUT_URL,
                "digest": put.content_digest,
                "first_date": put.rows[0][0].isoformat(),
                "last_date": put.rows[-1][0].isoformat(),
            },
            "cboe_wput": {
                "url": WPUT_URL,
                "digest": wput.content_digest,
                "first_date": wput.rows[0][0].isoformat(),
                "last_date": wput.rows[-1][0].isoformat(),
                "selection_input": False,
            },
            "cboe_vix": {
                "url": VIX_URL,
                "digest": vix.content_digest,
                "first_date": vix.rows[0][0].isoformat(),
                "last_date": vix.rows[-1][0].isoformat(),
            },
            "fama_french_daily": {
                "url": FRENCH_DAILY_URL,
                "digest": _content_digest(french_daily_raw),
                "first_date": french[0].observed_date.isoformat(),
                "last_date": french[-1].observed_date.isoformat(),
            },
            "fred_dgs3mo": {
                "url": FRED_DGS3MO_URL,
                "digest": _fingerprint([(point.date, str(point.value)) for point in cash_points]),
                "first_date": observed_cash[0].date,
                "last_date": observed_cash[-1].date,
            },
        },
    }
    return OptionsPremiumBundle(
        factor_months=tuple(month.isoformat() for month in factor_months),
        put_factors=tuple(put_factors[month] for month in factor_months),
        wput_factors=tuple(wput_factors[month] for month in factor_months),
        market_factors=tuple(market[month] for month in factor_months),
        cash_factors=tuple(cash[month] for month in factor_months),
        features=features,
        quality=quality,
    )


def validate_options_premium_bundle(bundle: OptionsPremiumBundle) -> None:
    if bundle.quality.get("complete") is not True:
        raise ValueError("options premium data is incomplete or stale")


def generate_options_premium_candidates() -> tuple[OptionsPremiumCandidate, ...]:
    policies = [
        OptionsPremiumPolicy("passive_put", None, weight)
        for weight in (Decimal("0.25"), Decimal("0.5"), Decimal("0.75"), Decimal("1"))
    ]
    policies.extend(
        OptionsPremiumPolicy(family, horizon, maximum)
        for family in ("positive_vrp", "tail_guarded", "ridge_forecast")
        for horizon in (6, 12)
        for maximum in (Decimal("0.5"), Decimal("1"))
    )
    output: list[OptionsPremiumCandidate] = []
    for policy in policies:
        digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": policy.as_dict()})
        output.append(
            OptionsPremiumCandidate(
                candidate_id=f"options-vrp-{policy.family}-{digest[7:19]}",
                trial_index=len(output) + 1,
                policy=policy,
                strategy_fingerprint=_fingerprint(
                    {
                        "objective": OBJECTIVE,
                        "research_index": "CBOE_PUT",
                        "signal_lag_months": 1,
                        "cost_cases": COST_CASES,
                        "policy": policy.as_dict(),
                    }
                ),
            )
        )
    if len(output) != EXPECTED_CANDIDATES:
        raise RuntimeError("options premium candidate count contract violated")
    if len({row.candidate_id for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("options premium candidate ids are not unique")
    if len({row.strategy_fingerprint for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("options premium strategy fingerprints are not unique")
    return tuple(output)


def options_target_weight(
    policy: OptionsPremiumPolicy,
    feature: VarianceRiskPremiumSnapshot,
    *,
    ridge_prediction: float | None = None,
) -> Decimal:
    if policy.family != "passive_put" and policy.horizon_months != feature.horizon_months:
        raise ValueError("options policy and feature horizons differ")
    if policy.family == "passive_put":
        active = True
    elif policy.family == "positive_vrp":
        active = feature.smoothed_variance_premium > 0
    elif policy.family == "tail_guarded":
        active = (
            feature.smoothed_variance_premium > 0
            and feature.equity_trend > 0
            and not feature.vix_shock
        )
    elif policy.family == "ridge_forecast":
        active = ridge_prediction is not None and ridge_prediction > 0
    else:
        raise ValueError(f"unknown options premium family: {policy.family}")
    return policy.max_put_weight if active else Decimal("0")


def _candidate_factors(
    candidate: OptionsPremiumCandidate,
    bundle: OptionsPremiumBundle,
    ridge_predictions: dict[int, list[float | None]],
    *,
    annual_haircut_bps: int,
    turnover_cost_bps: int,
) -> tuple[list[float], list[Decimal], float]:
    horizon = candidate.policy.horizon_months or 6
    features = bundle.features[horizon]
    output: list[float] = []
    weights: list[Decimal] = []
    previous = Decimal("0")
    turnover_total = Decimal("0")
    for index, feature in enumerate(features):
        prediction = (
            ridge_predictions[horizon][index]
            if candidate.policy.family == "ridge_forecast"
            else None
        )
        weight = options_target_weight(
            candidate.policy,
            feature,
            ridge_prediction=prediction,
        )
        turnover = abs(weight - previous)
        gross = (
            float(weight) * bundle.put_factors[index]
            + (1.0 - float(weight)) * bundle.cash_factors[index]
        )
        annual_cost = float(weight) * annual_haircut_bps / 10_000.0 / 12.0
        turnover_cost = float(turnover) * turnover_cost_bps / 10_000.0
        net = gross * (1.0 - annual_cost) * (1.0 - turnover_cost)
        if not math.isfinite(net) or net <= 0:
            raise ValueError("options premium cost model produced a non-positive factor")
        output.append(net)
        weights.append(weight)
        turnover_total += turnover
        previous = weight
    return output, weights, float(turnover_total)


def _factors_from_fixed_weights(
    option_factors: Sequence[float],
    cash_factors: Sequence[float],
    weights: Sequence[Decimal],
    *,
    annual_haircut_bps: int = 50,
    turnover_cost_bps: int = 25,
) -> list[float]:
    if not (len(option_factors) == len(cash_factors) == len(weights)):
        raise ValueError("fixed-weight option replay factors must align")
    output: list[float] = []
    previous = Decimal("0")
    for option_factor, cash_factor, weight in zip(
        option_factors, cash_factors, weights, strict=True
    ):
        turnover = abs(weight - previous)
        gross = float(weight) * option_factor + (1.0 - float(weight)) * cash_factor
        annual_cost = float(weight) * annual_haircut_bps / 10_000.0 / 12.0
        turnover_cost = float(turnover) * turnover_cost_bps / 10_000.0
        net = gross * (1.0 - annual_cost) * (1.0 - turnover_cost)
        if not math.isfinite(net) or net <= 0:
            raise ValueError("fixed-weight option replay produced a non-positive factor")
        output.append(net)
        previous = weight
    return output


def _nested_outer_folds(factor_count: int) -> list[dict[str, Any]]:
    folds: list[dict[str, Any]] = []
    first_test = OUTER_TRAIN_MONTHS + OUTER_EMBARGO_MONTHS
    for test_start in range(first_test, factor_count - OUTER_TEST_MONTHS + 1, OUTER_TEST_MONTHS):
        outer_train_end = test_start - OUTER_EMBARGO_MONTHS
        inner_folds: list[dict[str, int]] = []
        first_validation = INNER_TRAIN_MONTHS + INNER_EMBARGO_MONTHS
        for validation_start in range(
            first_validation,
            outer_train_end - INNER_VALIDATION_MONTHS + 1,
            INNER_VALIDATION_MONTHS,
        ):
            inner_train_end = validation_start - INNER_EMBARGO_MONTHS
            inner_folds.append(
                {
                    "train_start_index": 0,
                    "train_end_index": inner_train_end - 1,
                    "embargo_index": validation_start - 1,
                    "validation_start_index": validation_start,
                    "validation_end_index": validation_start + INNER_VALIDATION_MONTHS - 1,
                }
            )
        if len(inner_folds) < 2:
            raise ValueError("nested options selection requires at least two inner folds")
        folds.append(
            {
                "outer_index": len(folds),
                "train_start_index": 0,
                "train_end_index": outer_train_end - 1,
                "embargo_index": test_start - 1,
                "test_start_index": test_start,
                "test_end_index": test_start + OUTER_TEST_MONTHS - 1,
                "inner_folds": inner_folds,
            }
        )
    if len(folds) < 8:
        raise ValueError("nested options selection requires at least eight outer folds")
    return folds


def _finite_score(value: float) -> float:
    return value if math.isfinite(value) else -1_000_000.0


def _portfolio_inner_score(
    candidate_factors: Sequence[float],
    cash_factors: Sequence[float],
    market_factors: Sequence[float],
    inner_folds: Sequence[dict[str, int]],
) -> dict[str, float]:
    cash_sharpes: list[float] = []
    equity_improvements: list[float] = []
    tail_advantages: list[float] = []
    for fold in inner_folds:
        start = fold["validation_start_index"]
        end = fold["validation_end_index"] + 1
        candidate = candidate_factors[start:end]
        cash = cash_factors[start:end]
        market = market_factors[start:end]
        cash_sharpes.append(
            _finite_score(
                annualized_sharpe(
                    [left / right - 1.0 for left, right in zip(candidate, cash, strict=True)]
                )
            )
        )
        equity_improvements.append(
            _finite_score(summarize(list(candidate)).sharpe - summarize(list(market)).sharpe)
        )
        tail_advantages.append(
            _finite_score(expected_shortfall_95(candidate) - expected_shortfall_95(market))
        )
    return {
        "worst_inner_cash_excess_sharpe": min(cash_sharpes),
        "median_inner_cash_excess_sharpe": statistics.median(cash_sharpes),
        "median_inner_equity_sharpe_improvement": statistics.median(equity_improvements),
        "median_inner_tail_advantage": statistics.median(tail_advantages),
    }


def _timing_inner_score(
    candidate_factors: Sequence[float],
    passive_factors: Sequence[float],
    inner_folds: Sequence[dict[str, int]],
) -> dict[str, float]:
    active_sharpes: list[float] = []
    annual_excesses: list[float] = []
    tail_advantages: list[float] = []
    for fold in inner_folds:
        start = fold["validation_start_index"]
        end = fold["validation_end_index"] + 1
        candidate = candidate_factors[start:end]
        passive = passive_factors[start:end]
        active_sharpes.append(
            _finite_score(
                annualized_sharpe(
                    [left / right - 1.0 for left, right in zip(candidate, passive, strict=True)]
                )
            )
        )
        annual_excesses.append(_finite_score(_annualized_excess(candidate, passive)))
        tail_advantages.append(
            _finite_score(expected_shortfall_95(candidate) - expected_shortfall_95(passive))
        )
    return {
        "worst_inner_active_excess_sharpe": min(active_sharpes),
        "median_inner_active_excess_sharpe": statistics.median(active_sharpes),
        "median_inner_annual_excess": statistics.median(annual_excesses),
        "median_inner_tail_advantage": statistics.median(tail_advantages),
    }


def _dated_fold(fold: dict[str, Any], months: Sequence[str]) -> dict[str, Any]:
    output = dict(fold)
    output["train_window"] = [months[fold["train_start_index"]], months[fold["train_end_index"]]]
    output["embargo_month"] = months[fold["embargo_index"]]
    if "test_start_index" in fold:
        output["test_window"] = [months[fold["test_start_index"]], months[fold["test_end_index"]]]
    if "validation_start_index" in fold:
        output["validation_window"] = [
            months[fold["validation_start_index"]],
            months[fold["validation_end_index"]],
        ]
    return output


def _run_nested_selection(
    *,
    mode: str,
    candidates: Sequence[OptionsPremiumCandidate],
    put_factors_by_candidate: Sequence[Sequence[float]],
    wput_factors_by_candidate: Sequence[Sequence[float]],
    weights_by_candidate: Sequence[Sequence[Decimal]],
    bundle: OptionsPremiumBundle,
) -> _NestedSelectionResult:
    if mode not in {"portfolio", "timing"}:
        raise ValueError("unknown nested options selection mode")
    candidate_indexes = [
        index
        for index, candidate in enumerate(candidates)
        if mode == "portfolio" or candidate.policy.family != "passive_put"
    ]
    passive_by_weight = {
        candidate.policy.max_put_weight: index
        for index, candidate in enumerate(candidates)
        if candidate.policy.family == "passive_put"
    }
    selected_put: list[float] = []
    selected_wput: list[float] = []
    selected_cash: list[float] = []
    selected_market: list[float] = []
    selected_passive_put: list[float] = []
    selected_passive_wput: list[float] = []
    selected_weights: list[Decimal] = []
    outer_contracts: list[dict[str, Any]] = []
    for fold in _nested_outer_folds(len(bundle.factor_months)):
        scored: list[tuple[tuple[Any, ...], int, dict[str, float]]] = []
        for candidate_index in candidate_indexes:
            candidate = candidates[candidate_index]
            if mode == "portfolio":
                score = _portfolio_inner_score(
                    put_factors_by_candidate[candidate_index],
                    bundle.cash_factors,
                    bundle.market_factors,
                    fold["inner_folds"],
                )
                key = (
                    -score["worst_inner_cash_excess_sharpe"],
                    -score["median_inner_cash_excess_sharpe"],
                    -score["median_inner_equity_sharpe_improvement"],
                    -score["median_inner_tail_advantage"],
                    candidate.candidate_id,
                )
            else:
                passive_index = passive_by_weight[candidate.policy.max_put_weight]
                score = _timing_inner_score(
                    put_factors_by_candidate[candidate_index],
                    put_factors_by_candidate[passive_index],
                    fold["inner_folds"],
                )
                key = (
                    -score["worst_inner_active_excess_sharpe"],
                    -score["median_inner_active_excess_sharpe"],
                    -score["median_inner_annual_excess"],
                    -score["median_inner_tail_advantage"],
                    candidate.candidate_id,
                )
            scored.append((key, candidate_index, score))
        _, selected_index, selected_score = min(scored, key=lambda row: row[0])
        selected = candidates[selected_index]
        start = fold["test_start_index"]
        end = fold["test_end_index"] + 1
        test_weights = list(weights_by_candidate[selected_index][start:end])
        selected_put.extend(put_factors_by_candidate[selected_index][start:end])
        selected_wput.extend(wput_factors_by_candidate[selected_index][start:end])
        selected_cash.extend(bundle.cash_factors[start:end])
        selected_market.extend(bundle.market_factors[start:end])
        selected_weights.extend(test_weights)
        if mode == "timing":
            passive_index = passive_by_weight[selected.policy.max_put_weight]
            selected_passive_put.extend(put_factors_by_candidate[passive_index][start:end])
            selected_passive_wput.extend(wput_factors_by_candidate[passive_index][start:end])
        latest_selection_index = max(
            row["validation_end_index"] for row in fold["inner_folds"]
        )
        chronology_valid = latest_selection_index < fold["embargo_index"]
        outer_contracts.append(
            {
                **_dated_fold(fold, bundle.factor_months),
                "inner_folds": [
                    _dated_fold(row, bundle.factor_months) for row in fold["inner_folds"]
                ],
                "selected_candidate_id": selected.candidate_id,
                "selected_strategy_fingerprint": selected.strategy_fingerprint,
                "selected_score": {
                    key: round(value, 8) for key, value in selected_score.items()
                },
                "selected_weights": [str(weight) for weight in test_weights],
                "selection_latest_index": latest_selection_index,
                "selection_latest_month": bundle.factor_months[latest_selection_index],
                "chronology_valid": chronology_valid,
                "wput_used_for_selection": False,
            }
        )
    identity = [
        {
            "candidate_id": row["selected_candidate_id"],
            "weights": row["selected_weights"],
        }
        for row in outer_contracts
    ]
    contract = {
        "selector": (
            "worst/median cash-excess Sharpe, equity Sharpe improvement, tail advantage, id"
            if mode == "portfolio"
            else "worst/median active-excess Sharpe, annual excess, tail advantage, id"
        ),
        "outer_folds": outer_contracts,
        "selection_fingerprint": _fingerprint(identity),
        "put_stitched": {
            "months": len(selected_put),
            "first_month": outer_contracts[0]["test_window"][0],
            "last_month": outer_contracts[-1]["test_window"][1],
        },
        "wput_replay": {
            "months": len(selected_wput),
            "selection_input": False,
            "exact_put_selection_fingerprint": _fingerprint(identity),
            "exact_weight_replay": True,
        },
    }
    return _NestedSelectionResult(
        contract=contract,
        put_factors=tuple(selected_put),
        wput_factors=tuple(selected_wput),
        cash_factors=tuple(selected_cash),
        market_factors=tuple(selected_market),
        passive_put_factors=tuple(selected_passive_put),
        passive_wput_factors=tuple(selected_passive_wput),
        selected_weights=tuple(selected_weights),
    )


def _annualized_excess(candidate: Sequence[float], benchmark: Sequence[float]) -> float:
    if not candidate or len(candidate) != len(benchmark):
        raise ValueError("annualized excess factors must align")
    relative = math.prod(left / right for left, right in zip(candidate, benchmark, strict=True))
    return relative ** (12.0 / len(candidate)) - 1.0


def expected_shortfall_95(factors: Sequence[float]) -> float:
    if not factors:
        raise ValueError("expected shortfall requires returns")
    returns = sorted(float(factor) - 1.0 for factor in factors)
    tail_count = max(1, math.ceil(len(returns) * 0.05))
    return statistics.mean(returns[:tail_count])


def _gate(passed: bool, actual: Any, required: str) -> dict[str, Any]:
    return {"passed": bool(passed), "actual": actual, "required": required}


def standalone_premium_lane(
    candidate_factors: Sequence[float],
    cash_factors: Sequence[float],
    market_factors: Sequence[float],
    *,
    paper: bool,
) -> dict[str, Any]:
    if not (len(candidate_factors) == len(cash_factors) == len(market_factors)):
        raise ValueError("standalone premium factors must align")
    excess = [
        candidate / cash - 1.0
        for candidate, cash in zip(candidate_factors, cash_factors, strict=True)
    ]
    psr = probabilistic_sharpe(excess)
    annual_excess = _annualized_excess(candidate_factors, cash_factors)
    candidate_stats = summarize(list(candidate_factors))
    market_stats = summarize(list(market_factors))
    sharpe_improvement = candidate_stats.sharpe - market_stats.sharpe
    candidate_es = expected_shortfall_95(candidate_factors)
    market_es = expected_shortfall_95(market_factors)
    if paper:
        psr_threshold = PAPER_PSR_MIN
        annual_passed = annual_excess > 0
        annual_required = "> 0"
        sharpe_threshold = 0.0
        drawdown_threshold = market_stats.max_dd_pct * 1.20
        es_threshold = market_es * 1.20
    else:
        psr_threshold = HOLDOUT_PSR_MIN
        annual_passed = annual_excess >= 0.02
        annual_required = ">= 0.02"
        sharpe_threshold = 0.05
        drawdown_threshold = market_stats.max_dd_pct
        es_threshold = market_es
    gates = {
        "cash_excess_psr": _gate(
            psr is not None and float(psr) >= psr_threshold,
            None if psr is None else str(psr),
            f">= {psr_threshold}",
        ),
        "annual_cash_excess": _gate(annual_passed, round(annual_excess, 8), annual_required),
        "broad_equity_sharpe_improvement": _gate(
            sharpe_improvement >= sharpe_threshold,
            round(sharpe_improvement, 6),
            f">= {sharpe_threshold}",
        ),
        "maximum_drawdown": _gate(
            candidate_stats.max_dd_pct <= drawdown_threshold,
            round(candidate_stats.max_dd_pct, 6),
            f"<= {drawdown_threshold:.6f}",
        ),
        "expected_shortfall_95": _gate(
            candidate_es >= es_threshold,
            round(candidate_es, 8),
            f">= {es_threshold:.8f}",
        ),
    }
    return {
        "passed": all(row["passed"] for row in gates.values()),
        "paper": paper,
        "gates": gates,
        "metrics": {
            "psr_vs_cash": None if psr is None else str(psr),
            "annual_cash_excess": round(annual_excess, 8),
            "candidate_sharpe": round(candidate_stats.sharpe, 6),
            "market_sharpe": round(market_stats.sharpe, 6),
            "sharpe_improvement": round(sharpe_improvement, 6),
            "candidate_max_drawdown_pct": round(candidate_stats.max_dd_pct, 6),
            "market_max_drawdown_pct": round(market_stats.max_dd_pct, 6),
            "candidate_expected_shortfall_95": round(candidate_es, 8),
            "market_expected_shortfall_95": round(market_es, 8),
        },
    }


def premium_existence_lane(
    candidate_factors: Sequence[float],
    cash_factors: Sequence[float],
) -> dict[str, Any]:
    """Test premium existence without claiming portfolio adoption."""
    if len(candidate_factors) != len(cash_factors):
        raise ValueError("premium existence factors must align")
    excess = [
        candidate / cash - 1.0
        for candidate, cash in zip(candidate_factors, cash_factors, strict=True)
    ]
    psr = probabilistic_sharpe(excess)
    annual_excess = _annualized_excess(candidate_factors, cash_factors)
    gates = {
        "cash_excess_psr": _gate(
            psr is not None and float(psr) >= HOLDOUT_PSR_MIN,
            None if psr is None else str(psr),
            f">= {HOLDOUT_PSR_MIN}",
        ),
        "annual_cash_excess": _gate(
            annual_excess >= 0.02,
            round(annual_excess, 8),
            ">= 0.02",
        ),
    }
    return {
        "passed": all(row["passed"] for row in gates.values()),
        "diagnostic_only": True,
        "promotion_eligible": False,
        "promotion_allowed": False,
        "gates": gates,
        "metrics": {
            "psr_vs_cash": None if psr is None else str(psr),
            "annual_cash_excess": round(annual_excess, 8),
        },
        "meaning": (
            "tests whether a compensated PUT premium exists; it does not establish "
            "portfolio adoption or executable parity"
        ),
    }


def portfolio_adoption_lane(
    candidate_factors: Sequence[float],
    cash_factors: Sequence[float],
    market_factors: Sequence[float],
) -> dict[str, Any]:
    """Test whether the premium improves an investable broad-equity alternative."""
    lane = standalone_premium_lane(
        candidate_factors,
        cash_factors,
        market_factors,
        paper=False,
    )
    return {
        "passed": lane["passed"],
        "diagnostic_only": True,
        "promotion_eligible": False,
        "promotion_allowed": False,
        "gates": lane["gates"],
        "metrics": lane["metrics"],
        "meaning": (
            "tests whether a selected premium portfolio improves cash and broad-equity "
            "risk-adjusted outcomes; it does not establish executable parity"
        ),
    }


def timing_enhancement_lane(
    candidate_factors: Sequence[float],
    passive_factors: Sequence[float],
    *,
    active_fraction: float,
) -> dict[str, Any]:
    candidate_stats = summarize(list(candidate_factors))
    passive_stats = summarize(list(passive_factors))
    annual_excess = _annualized_excess(candidate_factors, passive_factors)
    sharpe_improvement = candidate_stats.sharpe - passive_stats.sharpe
    candidate_es = expected_shortfall_95(candidate_factors)
    passive_es = expected_shortfall_95(passive_factors)
    gates = {
        "annual_excess_vs_passive": _gate(annual_excess > 0, round(annual_excess, 8), "> 0"),
        "sharpe_improvement_vs_passive": _gate(
            sharpe_improvement >= 0.05, round(sharpe_improvement, 6), ">= 0.05"
        ),
        "drawdown_non_worsening": _gate(
            candidate_stats.max_dd_pct <= passive_stats.max_dd_pct,
            round(candidate_stats.max_dd_pct, 6),
            f"<= {passive_stats.max_dd_pct:.6f}",
        ),
        "expected_shortfall_non_worsening": _gate(
            candidate_es >= passive_es, round(candidate_es, 8), f">= {passive_es:.8f}"
        ),
        "active_fraction": _gate(
            0.10 <= active_fraction <= 0.90, round(active_fraction, 6), "0.10 <= fraction <= 0.90"
        ),
    }
    return {
        "passed": all(row["passed"] for row in gates.values()),
        "diagnostic_only": True,
        "promotion_eligible": False,
        "promotion_allowed": False,
        "gates": gates,
        "metrics": {
            "annual_excess_vs_passive": round(annual_excess, 8),
            "sharpe_improvement_vs_passive": round(sharpe_improvement, 6),
            "candidate_expected_shortfall_95": round(candidate_es, 8),
            "passive_expected_shortfall_95": round(passive_es, 8),
            "active_fraction": round(active_fraction, 6),
        },
    }


def _cross_index_objective(
    put_lane: dict[str, Any],
    wput_lane: dict[str, Any],
    *,
    question: str,
) -> dict[str, Any]:
    return {
        "passed": bool(put_lane["passed"] and wput_lane["passed"]),
        "diagnostic_only": True,
        "promotion_eligible": False,
        "promotion_allowed": False,
        "question": question,
        "put": put_lane,
        "wput": wput_lane,
        "cross_index_required": True,
    }


def calibrate_options_premium_gate(
    holdout_months: int,
    *,
    repetitions: int = 500,
    seed: int = 16400,
) -> dict[str, Any]:
    if holdout_months < MIN_HOLDOUT_MONTHS or repetitions < 1:
        raise ValueError("options gate calibration coverage is incomplete")
    rng = random.Random(seed)
    null_passes = 0
    planted_detected = 0
    correctly_selected = 0

    def draws(count: int, mean: float, sigma: float) -> list[float]:
        return [rng.gauss(mean, sigma) for _ in range(count)]

    for _ in range(repetitions):
        null_development = [draws(DEVELOPMENT_MONTHS, 0.0, 0.035) for _ in range(16)]
        null_winner = max(range(16), key=lambda index: annualized_sharpe(null_development[index]))
        null_holdout = draws(holdout_months, 0.0, 0.035)
        null_market = draws(holdout_months, 0.006, 0.045)
        null_lane = standalone_premium_lane(
            [1.002 * (1.0 + value) for value in null_holdout],
            [1.002] * holdout_months,
            [1.002 * (1.0 + value) for value in null_market],
            paper=False,
        )
        null_passes += int(null_lane["passed"] and null_winner >= 0)

        development = [draws(DEVELOPMENT_MONTHS, 0.0, 0.035) for _ in range(15)]
        development.insert(0, draws(DEVELOPMENT_MONTHS, 0.008, 0.025))
        winner = max(range(16), key=lambda index: annualized_sharpe(development[index]))
        correctly_selected += int(winner == 0)
        holdout = draws(
            holdout_months,
            0.008 if winner == 0 else 0.0,
            0.025 if winner == 0 else 0.035,
        )
        market = draws(holdout_months, 0.006, 0.045)
        lane = standalone_premium_lane(
            [1.002 * (1.0 + value) for value in holdout],
            [1.002] * holdout_months,
            [1.002 * (1.0 + value) for value in market],
            paper=False,
        )
        planted_detected += int(lane["passed"])
    null_rate = null_passes / repetitions
    detection_rate = planted_detected / repetitions
    return {
        "method": "16-candidate selection with independent options-premium holdout",
        "seed": seed,
        "repetitions": repetitions,
        "holdout_months": holdout_months,
        "null_false_acceptance_rate": round(null_rate, 6),
        "planted_edge_detection_rate": round(detection_rate, 6),
        "planted_edge_correct_selection_rate": round(correctly_selected / repetitions, 6),
        "thresholds": {"null_max": 0.06, "detection_min": 0.80},
        "passable": null_rate <= 0.06 and detection_rate >= 0.80,
    }


def _prior_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("audit_records", [])
    unique: dict[str, dict[str, Any]] = {}
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict) or record.get("status") not in {
            "complete",
            "EXPLORATORY_REJECTED",
        }:
            continue
        identity = str(record.get("strategy_fingerprint") or record.get("candidate_id") or "")
        if identity:
            unique.setdefault(identity, record)
    return [unique[key] for key in sorted(unique)]


def audit_prior_adoption(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for family, payload in sorted(payloads.items()):
        decision = payload.get("decision", {}) if isinstance(payload, dict) else {}
        verdict = str(decision.get("verdict") or payload.get("verdict") or "UNKNOWN")
        diagnosis = str(decision.get("criterion_diagnosis") or "")
        if decision.get("paper_candidate_id") or "PAPER" in verdict:
            classification = "missing_clean_forward_evidence"
        elif "OBJECTIVE" in diagnosis and "UNCONFIRMED" not in diagnosis:
            classification = "objective_mismatch_already_corrected"
        elif decision.get("psr") is None or "UNCONFIRMED" in diagnosis:
            classification = "statistical_uncertainty"
        elif decision.get("posthoc_candidate_id"):
            classification = "posthoc_only_evidence"
        elif decision.get("confirmed_candidate_id"):
            classification = "missing_executable_parity"
        else:
            classification = "negative_economics"
        output.append(
            {
                "family": family,
                "frozen_candidate_id": decision.get("provisional_best_candidate_id"),
                "original_verdict": verdict,
                "classification": classification,
                "retroactive_promotion_allowed": False,
                "evidence_source_digest": _fingerprint(payload),
            }
        )
    return output


def _development_winner_index(records: Sequence[dict[str, Any]]) -> int:
    if not records:
        raise ValueError("options premium development selection requires records")
    return min(
        range(len(records)),
        key=lambda index: (
            -float(records[index]["development_sharpe"]),
            float(records[index]["development_expected_shortfall_loss_pct"]),
            float(records[index]["development_max_drawdown_pct"]),
            str(records[index]["candidate_id"]),
        ),
    )


def _reference_null(
    put: Sequence[float],
    cash: Sequence[float],
) -> list[float]:
    excess = [left / right - 1.0 for left, right in zip(put, cash, strict=True)]
    mean = statistics.mean(excess)
    output = []
    for index, (value, cash_factor) in enumerate(zip(excess, cash, strict=True)):
        factor = cash_factor * (1.0 + value - mean) * (1.0 - 50 / 10_000.0 / 12.0)
        if index == 0:
            factor *= 1.0 - 25 / 10_000.0
        output.append(factor)
    return output


def _classify_verdict(
    *,
    infrastructure_passed: bool,
    selected_live_passed: bool,
    selected_paper_passed: bool,
    reference_adoption_passed: bool,
    objective_calibration_passed: bool,
) -> str:
    if not infrastructure_passed:
        return GATE_OR_REFERENCE_SUSPECT
    if not reference_adoption_passed and objective_calibration_passed:
        return GATE_OR_REFERENCE_SUSPECT
    if selected_live_passed:
        return FACTORY_EDGE_CONFIRMED
    if selected_paper_passed:
        return PAPER_EDGE_CANDIDATE
    if reference_adoption_passed:
        return REFERENCE_EDGE_CONFIRMED_SELECTION_UNCONFIRMED
    return NO_FACTORY_EDGE


def run_options_variance_risk_premium_factory(
    bundle: OptionsPremiumBundle,
    *,
    prior_factory_payload: dict[str, Any],
    prior_family_payloads: dict[str, dict[str, Any]],
    calibration_evidence: dict[str, Any],
    full_gate_controls: dict[str, Any],
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
    calibration_repetitions: int = 500,
) -> dict[str, Any]:
    validate_options_premium_bundle(bundle)
    factor_count = len(bundle.factor_months)
    if not (
        factor_count
        == len(bundle.put_factors)
        == len(bundle.wput_factors)
        == len(bundle.market_factors)
        == len(bundle.cash_factors)
        == len(bundle.features[6])
        == len(bundle.features[12])
    ):
        raise ValueError("options premium bundle lengths differ")
    holdout_start = DEVELOPMENT_MONTHS + EMBARGO_MONTHS
    holdout_months = factor_count - holdout_start
    if factor_count < MIN_FACTOR_MONTHS or holdout_months < MIN_HOLDOUT_MONTHS:
        raise ValueError("options premium holdout must contain at least 120 months")

    candidates = generate_options_premium_candidates()
    target_excess = [
        put / cash - 1.0 for put, cash in zip(bundle.put_factors, bundle.cash_factors, strict=True)
    ]
    ridge_predictions: dict[int, list[float | None]] = {}
    ridge_chronology: dict[int, list[dict[str, int | None]]] = {}
    for horizon in (6, 12):
        predictions, chronology = expanding_ridge_predictions(
            [row.model_features() for row in bundle.features[horizon]],
            target_excess,
        )
        ridge_predictions[horizon] = predictions
        ridge_chronology[horizon] = chronology

    records: list[dict[str, Any]] = []
    all_factors: list[dict[tuple[int, int], list[float]]] = []
    all_weights: list[list[Decimal]] = []
    development_returns: list[list[float]] = []
    development_segments: list[list[float]] = []
    for candidate in candidates:
        by_cost: dict[tuple[int, int], list[float]] = {}
        weights: list[Decimal] = []
        turnover = 0.0
        for annual_cost, turnover_cost in COST_CASES:
            factors, current_weights, current_turnover = _candidate_factors(
                candidate,
                bundle,
                ridge_predictions,
                annual_haircut_bps=annual_cost,
                turnover_cost_bps=turnover_cost,
            )
            by_cost[(annual_cost, turnover_cost)] = factors
            if (annual_cost, turnover_cost) == (50, 25):
                weights = current_weights
                turnover = current_turnover
        middle = by_cost[(50, 25)]
        development_excess = [
            factor / cash - 1.0
            for factor, cash in zip(
                middle[:DEVELOPMENT_MONTHS],
                bundle.cash_factors[:DEVELOPMENT_MONTHS],
                strict=True,
            )
        ]
        development_stats = summarize(middle[:DEVELOPMENT_MONTHS])
        development_es = expected_shortfall_95(middle[:DEVELOPMENT_MONTHS])
        holdout = middle[holdout_start:]
        holdout_cash = bundle.cash_factors[holdout_start:]
        holdout_market = bundle.market_factors[holdout_start:]
        live_lane = standalone_premium_lane(holdout, holdout_cash, holdout_market, paper=False)
        paper_lane = standalone_premium_lane(holdout, holdout_cash, holdout_market, paper=True)
        active_fraction = sum(weight > 0 for weight in weights[holdout_start:]) / holdout_months
        development_returns.append(development_excess)
        segment_sharpes = [
            annualized_sharpe(segment) for segment in _segments(development_excess, count=8)
        ]
        development_segments.append(segment_sharpes)
        all_factors.append(by_cost)
        all_weights.append(weights)
        records.append(
            {
                "candidate_id": candidate.candidate_id,
                "strategy_fingerprint": candidate.strategy_fingerprint,
                "status": "complete",
                "family": candidate.policy.family,
                "policy": candidate.policy.as_dict(),
                "development_sharpe": round(annualized_sharpe(development_excess), 6),
                "development_expected_shortfall_loss_pct": round(-development_es * 100.0, 6),
                "development_max_drawdown_pct": round(development_stats.max_dd_pct, 6),
                "holdout_metrics_by_cost": {
                    f"annual_{annual}_turnover_{turnover_cost}": {
                        "cagr_pct": round(
                            summarize(by_cost[(annual, turnover_cost)][holdout_start:]).cagr_pct, 6
                        ),
                        "max_drawdown_pct": round(
                            summarize(by_cost[(annual, turnover_cost)][holdout_start:]).max_dd_pct,
                            6,
                        ),
                        "expected_shortfall_95": round(
                            expected_shortfall_95(by_cost[(annual, turnover_cost)][holdout_start:]),
                            8,
                        ),
                    }
                    for annual, turnover_cost in COST_CASES
                },
                "holdout_psr": live_lane["metrics"]["psr_vs_cash"],
                "holdout_annual_cash_excess": live_lane["metrics"]["annual_cash_excess"],
                "holdout_sharpe_improvement": live_lane["metrics"]["sharpe_improvement"],
                "holdout_active_fraction": round(active_fraction, 6),
                "posthoc_standalone_live_passed": live_lane["passed"],
                "posthoc_standalone_paper_passed": paper_lane["passed"],
                "turnover": round(turnover, 6),
                "segment_sharpes": [round(value, 6) for value in segment_sharpes],
            }
        )

    put_factors_by_candidate = [row[(50, 25)] for row in all_factors]
    wput_factors_by_candidate = [
        _factors_from_fixed_weights(
            bundle.wput_factors,
            bundle.cash_factors,
            weights,
        )
        for weights in all_weights
    ]
    portfolio_selection = _run_nested_selection(
        mode="portfolio",
        candidates=candidates,
        put_factors_by_candidate=put_factors_by_candidate,
        wput_factors_by_candidate=wput_factors_by_candidate,
        weights_by_candidate=all_weights,
        bundle=bundle,
    )
    timing_selection = _run_nested_selection(
        mode="timing",
        candidates=candidates,
        put_factors_by_candidate=put_factors_by_candidate,
        wput_factors_by_candidate=wput_factors_by_candidate,
        weights_by_candidate=all_weights,
        bundle=bundle,
    )
    selection_rows = (
        portfolio_selection.contract["outer_folds"]
        + timing_selection.contract["outer_folds"]
    )
    chronology_violations = [
        {
            "mode": "portfolio" if index < len(selection_rows) / 2 else "timing",
            "outer_index": row["outer_index"],
            "selection_latest_index": row["selection_latest_index"],
            "embargo_index": row["embargo_index"],
        }
        for index, row in enumerate(selection_rows)
        if not row["chronology_valid"]
    ]
    nested_chronology = {
        "fold_count": len(portfolio_selection.contract["outer_folds"]),
        "all_folds_valid": not chronology_violations,
        "violations": chronology_violations,
        "minimum_inner_folds": min(
            len(row["inner_folds"])
            for row in portfolio_selection.contract["outer_folds"]
        ),
    }

    winner_index = _development_winner_index(records)
    winner = candidates[winner_index]
    winner_factors = all_factors[winner_index][(50, 25)][holdout_start:]
    holdout_cash = bundle.cash_factors[holdout_start:]
    holdout_market = bundle.market_factors[holdout_start:]
    standalone_live = standalone_premium_lane(
        winner_factors, holdout_cash, holdout_market, paper=False
    )
    standalone_paper = standalone_premium_lane(
        winner_factors, holdout_cash, holdout_market, paper=True
    )
    winner_weights = all_weights[winner_index][holdout_start:]
    active_fraction = sum(weight > 0 for weight in winner_weights) / holdout_months

    timing_lane: dict[str, Any] | None = None
    if winner.policy.family != "passive_put":
        passive = next(
            candidate
            for candidate in candidates
            if candidate.policy.family == "passive_put"
            and candidate.policy.max_put_weight == winner.policy.max_put_weight
        )
        passive_index = candidates.index(passive)
        timing_lane = timing_enhancement_lane(
            winner_factors,
            all_factors[passive_index][(50, 25)][holdout_start:],
            active_fraction=active_fraction,
        )

    reference_index = next(
        index
        for index, candidate in enumerate(candidates)
        if candidate.policy.family == "passive_put"
        and candidate.policy.max_put_weight == Decimal("1")
    )
    reference_factors = all_factors[reference_index][(50, 25)][holdout_start:]
    reference_live = standalone_premium_lane(
        reference_factors, holdout_cash, holdout_market, paper=False
    )
    reference_paper = standalone_premium_lane(
        reference_factors, holdout_cash, holdout_market, paper=True
    )
    reference_existence = premium_existence_lane(reference_factors, holdout_cash)
    null_factors = _reference_null(bundle.put_factors[holdout_start:], holdout_cash)
    null_live = standalone_premium_lane(null_factors, holdout_cash, holdout_market, paper=False)
    null_paper = standalone_premium_lane(null_factors, holdout_cash, holdout_market, paper=True)
    reference_control = {
        "full_put_live": reference_live,
        "full_put_paper": reference_paper,
        "full_put_premium_existence": reference_existence,
        "mean_zero_null_live": null_live,
        "mean_zero_null_paper": null_paper,
        "recognized_reference_passed": reference_live["passed"] or reference_paper["passed"],
        "economic_premium_detected": reference_existence["passed"],
        "mean_zero_null_rejected": not null_live["passed"] and not null_paper["passed"],
    }

    repair_start = portfolio_selection.contract["outer_folds"][0]["test_start_index"]
    repair_end = portfolio_selection.contract["outer_folds"][-1]["test_end_index"] + 1
    repair_cash = bundle.cash_factors[repair_start:repair_end]
    premium_put = premium_existence_lane(
        put_factors_by_candidate[reference_index][repair_start:repair_end],
        repair_cash,
    )
    premium_wput = premium_existence_lane(
        wput_factors_by_candidate[reference_index][repair_start:repair_end],
        repair_cash,
    )
    portfolio_put = portfolio_adoption_lane(
        portfolio_selection.put_factors,
        portfolio_selection.cash_factors,
        portfolio_selection.market_factors,
    )
    portfolio_wput = portfolio_adoption_lane(
        portfolio_selection.wput_factors,
        portfolio_selection.cash_factors,
        portfolio_selection.market_factors,
    )
    timing_active_fraction = sum(
        weight > 0 for weight in timing_selection.selected_weights
    ) / len(timing_selection.selected_weights)
    timing_put = timing_enhancement_lane(
        timing_selection.put_factors,
        timing_selection.passive_put_factors,
        active_fraction=timing_active_fraction,
    )
    timing_wput = timing_enhancement_lane(
        timing_selection.wput_factors,
        timing_selection.passive_wput_factors,
        active_fraction=timing_active_fraction,
    )
    objective_lanes = {
        "premium_existence": _cross_index_objective(
            premium_put,
            premium_wput,
            question="does cash-secured put exposure beat cash after costs?",
        ),
        "portfolio_adoption": _cross_index_objective(
            portfolio_put,
            portfolio_wput,
            question=(
                "does nested-selected put exposure improve broad-equity risk-adjusted outcomes?"
            ),
        ),
        "timing_value": _cross_index_objective(
            timing_put,
            timing_wput,
            question="does automated timing improve matching passive put exposure?",
        ),
    }
    portfolio_selection.contract["put_stitched"]["metrics"] = portfolio_put["metrics"]
    portfolio_selection.contract["wput_replay"]["metrics"] = portfolio_wput["metrics"]
    timing_selection.contract["put_stitched"]["metrics"] = timing_put["metrics"]
    timing_selection.contract["wput_replay"]["metrics"] = timing_wput["metrics"]

    prior = _prior_records(prior_factory_payload)
    audit_records = prior + records
    identities = [
        str(record.get("strategy_fingerprint") or record.get("candidate_id"))
        for record in audit_records
    ]
    unique_audit = len(set(identities))
    calibration_passed = _calibration_valid(calibration_evidence, code_commit=code_commit)
    controls_passed = _full_controls_valid(full_gate_controls, code_commit=code_commit)
    objective_calibration = calibrate_options_premium_gate(
        holdout_months,
        repetitions=calibration_repetitions,
    )
    chronology_passed = all(
        row.source_month == _shift_month(row.target_month, -1)
        for values in bundle.features.values()
        for row in values
    ) and all(
        item["latest_training_target_index"] is None
        or int(item["latest_training_target_index"]) < int(item["prediction_index"])
        for values in ridge_chronology.values()
        for item in values
    )
    prior_adoption = audit_prior_adoption(prior_family_payloads)
    common_gates = {
        "gate_calibration": calibration_passed,
        "full_gate_controls": controls_passed,
        "options_objective_calibration": objective_calibration["passable"],
        "complete_family_trials": len(records) == EXPECTED_CANDIDATES,
        "prior_audit_complete": len(prior) == EXPECTED_PRIOR_TRIALS,
        "global_audit_trials": len(audit_records) == EXPECTED_GLOBAL_AUDIT_TRIALS,
        "unique_audit_fingerprints": unique_audit == EXPECTED_GLOBAL_AUDIT_TRIALS,
        "options_premium_data_complete": bundle.quality.get("complete") is True,
        "development_months": DEVELOPMENT_MONTHS == 84,
        "embargo_months": EMBARGO_MONTHS == 1,
        "holdout_months": holdout_months >= MIN_HOLDOUT_MONTHS,
        "model_chronology": chronology_passed,
        "nested_selection_chronology": nested_chronology["all_folds_valid"],
        "nested_selection_coverage": (
            nested_chronology["fold_count"] >= 8
            and nested_chronology["minimum_inner_folds"] >= 2
        ),
        "wput_independent_replay": all(
            row["wput_used_for_selection"] is False for row in selection_rows
        ),
        "prior_adoption_non_promoting": all(
            row["retroactive_promotion_allowed"] is False for row in prior_adoption
        ),
        "mean_zero_null_rejected": reference_control["mean_zero_null_rejected"],
    }
    infrastructure_passed = all(common_gates.values())
    live_passed = infrastructure_passed and standalone_live["passed"]
    paper_passed = infrastructure_passed and standalone_paper["passed"]
    reference_passed = infrastructure_passed and reference_control["recognized_reference_passed"]
    verdict = _classify_verdict(
        infrastructure_passed=infrastructure_passed,
        selected_live_passed=live_passed,
        selected_paper_passed=paper_passed,
        reference_adoption_passed=reference_passed,
        objective_calibration_passed=objective_calibration["passable"],
    )

    trial_sharpes = [float(row["development_sharpe"]) for row in records]
    effective_trials = effective_independent_trials(development_returns)
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index],
        trial_sharpes,
        effective_trial_count=effective_trials,
    )
    pbo = probability_of_backtest_overfitting(development_segments)
    best_holdout = max(
        records,
        key=lambda row: (
            float(row["holdout_psr"] or -1),
            float(row["holdout_annual_cash_excess"]),
        ),
    )
    posthoc_live = [
        str(row["candidate_id"]) for row in records if row["posthoc_standalone_live_passed"]
    ]
    posthoc_paper = [
        str(row["candidate_id"]) for row in records if row["posthoc_standalone_paper_passed"]
    ]
    split = {
        "development": [bundle.factor_months[0], bundle.factor_months[DEVELOPMENT_MONTHS - 1]],
        "embargo": bundle.factor_months[DEVELOPMENT_MONTHS],
        "holdout": [bundle.factor_months[holdout_start], bundle.factor_months[-1]],
        "development_months": DEVELOPMENT_MONTHS,
        "embargo_months": EMBARGO_MONTHS,
        "holdout_months": holdout_months,
    }
    data_fingerprint = _fingerprint(bundle.quality)
    split_fingerprint = _fingerprint(split)
    model_fingerprint = _fingerprint(
        {
            "model": "StandardScaler+Ridge",
            "alpha": RIDGE_ALPHA,
            "min_train": RIDGE_MIN_TRAIN,
            "features": [
                "vix_level",
                "variance_premium",
                "equity_trend",
                "market_drawdown",
                "prior_put_excess",
            ],
            "chronology": "training target index < prediction index",
        }
    )
    latest_feature = bundle.features[winner.policy.horizon_months or 6][-1]
    latest_prediction = ridge_predictions[winner.policy.horizon_months or 6][-1]
    latest_weight = options_target_weight(
        winner.policy,
        latest_feature,
        ridge_prediction=latest_prediction,
    )
    target_weights = {"PUT_proxy": str(latest_weight), "USD": str(Decimal("1") - latest_weight)}
    batch_id = (
        "options-variance-risk-premium-"
        + _fingerprint(
            {
                "code": code_commit,
                "data": data_fingerprint,
                "split": split_fingerprint,
                "model": model_fingerprint,
                "candidates": [candidate.candidate_id for candidate in candidates],
            }
        )[7:19]
    )
    if not infrastructure_passed:
        diagnosis = "INFRASTRUCTURE_OR_CONTROL_INVALID"
    elif not reference_passed and objective_calibration["passable"]:
        diagnosis = (
            "ECONOMIC_PREMIUM_EXISTS_BUT_ADOPTION_GATE_OVERCONSTRAINED"
            if reference_existence["passed"]
            else "RECOGNIZED_REFERENCE_NOT_CONFIRMED_GATE_OR_REFERENCE_SUSPECT"
        )
    elif live_passed or paper_passed:
        diagnosis = "OBJECTIVE_GATE_PASSABLE_SELECTED_CANDIDATE_CONFIRMED"
    elif reference_passed:
        diagnosis = "REFERENCE_EDGE_RECOGNIZED_SELECTION_FAILED"
    else:
        diagnosis = "RECOGNIZED_REFERENCE_NOT_CONFIRMED_GATE_OR_REFERENCE_SUSPECT"
    audit_gate_counts = {
        "complete_family_trials": (len(records), EXPECTED_CANDIDATES),
        "prior_audit_complete": (len(prior), EXPECTED_PRIOR_TRIALS),
        "global_audit_trials": (len(audit_records), EXPECTED_GLOBAL_AUDIT_TRIALS),
        "unique_audit_fingerprints": (unique_audit, EXPECTED_GLOBAL_AUDIT_TRIALS),
    }
    common_gate_rows = []
    for gate_id, passed in common_gates.items():
        actual, required = audit_gate_counts.get(gate_id, (bool(passed), True))
        common_gate_rows.append(
            {
                "gate_id": gate_id,
                "passed": bool(passed),
                "actual": str(actual),
                "required": str(required),
                "stage": "control",
                "blocking": True,
            }
        )
    live_gate_rows = [
        {
            "gate_id": gate_id,
            "passed": row["passed"],
            "actual": str(row["actual"]),
            "required": row["required"],
            "stage": "standalone_holdout",
            "blocking": True,
        }
        for gate_id, row in standalone_live["gates"].items()
    ]
    failed_live = [
        gate_id for gate_id, row in standalone_live["gates"].items() if not row["passed"]
    ]
    decision = {
        "verdict": verdict,
        "criterion_diagnosis": diagnosis,
        "objective": OBJECTIVE,
        "provisional_best_candidate_id": winner.candidate_id,
        "confirmed_candidate_id": (
            winner.candidate_id if verdict == FACTORY_EDGE_CONFIRMED else None
        ),
        "paper_candidate_id": (
            winner.candidate_id
            if paper_passed and not live_passed and verdict == PAPER_EDGE_CANDIDATE
            else None
        ),
        "selected_candidate_id": None,
        "selected_strategy_fingerprint": None,
        "research_canary_eligible": False,
        "paper_forward_eligible": (
            paper_passed and not live_passed and verdict == PAPER_EDGE_CANDIDATE
        ),
        "gates": common_gate_rows + live_gate_rows,
        "paper_gates": standalone_paper["gates"],
        "failed_standalone_live_gates": failed_live,
        "dsr": None if dsr is None else str(dsr),
        "pbo": None if pbo is None else str(pbo),
        "psr": standalone_live["metrics"]["psr_vs_cash"],
        "next_strategy_family": (
            "exact_options_execution_parity_design"
            if live_passed and verdict == FACTORY_EDGE_CONFIRMED
            else "forward_paper_options_variance_risk_premium"
            if verdict
            in {
                PAPER_EDGE_CANDIDATE,
                REFERENCE_EDGE_CONFIRMED_SELECTION_UNCONFIRMED,
            }
            else "preregister_options_selection_and_objective_repair"
        ),
        "search_space_exhausted": verdict == NO_FACTORY_EDGE,
    }
    legacy_decision = decision
    if not infrastructure_passed:
        repair_verdict = GATE_OR_REFERENCE_SUSPECT
        repair_diagnosis = "INFRASTRUCTURE_OR_CONTROL_INVALID"
    elif objective_lanes["premium_existence"]["passed"] and (
        objective_lanes["portfolio_adoption"]["passed"]
        or objective_lanes["timing_value"]["passed"]
    ):
        repair_verdict = SELECTION_METHOD_CONFIRMED_DIAGNOSTIC
        repair_diagnosis = "CROSS_INDEX_SELECTION_DIAGNOSTIC_PASSED"
    elif objective_lanes["premium_existence"]["passed"]:
        repair_verdict = PREMIUM_CONFIRMED_SELECTION_UNRESOLVED
        repair_diagnosis = "CROSS_INDEX_PREMIUM_EXISTS_ADOPTION_OR_TIMING_UNRESOLVED"
    else:
        repair_verdict = NO_CROSS_INDEX_PREMIUM
        repair_diagnosis = "CROSS_INDEX_PREMIUM_NOT_CONFIRMED"
    latest_nested_candidate = portfolio_selection.contract["outer_folds"][-1][
        "selected_candidate_id"
    ]
    objective_gate_rows = [
        {
            "gate_id": f"cross_index_{lane_id}",
            "passed": lane["passed"],
            "actual": str(lane["passed"]),
            "required": "diagnostic only; never promotes",
            "stage": "historical_nested_replay",
            "blocking": False,
        }
        for lane_id, lane in objective_lanes.items()
    ]
    decision = {
        "verdict": repair_verdict,
        "criterion_diagnosis": repair_diagnosis,
        "objective": "separated_options_premium_adoption_and_timing",
        "provisional_best_candidate_id": latest_nested_candidate,
        "confirmed_candidate_id": None,
        "paper_candidate_id": None,
        "selected_candidate_id": None,
        "selected_strategy_fingerprint": None,
        "research_canary_eligible": False,
        "paper_forward_eligible": False,
        "promotion_allowed": False,
        "historical_reuse": True,
        "gates": common_gate_rows + objective_gate_rows,
        "paper_gates": {},
        "failed_standalone_live_gates": [
            lane_id for lane_id, lane in objective_lanes.items() if not lane["passed"]
        ],
        "dsr": None,
        "pbo": None,
        "psr": None,
        "next_strategy_family": "collect_clean_forward_options_evidence",
        "search_space_exhausted": False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_version": CONSUMER_GATE_VERSION,
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
        "research_canary_eligible": False,
        "paper_forward_eligible": False,
        "promotion_allowed": False,
        "options_premium_data": bundle.quality,
        "options_premium_data_fingerprint": data_fingerprint,
        "energy_cross_market_data_fingerprint": prior_factory_payload.get(
            "energy_cross_market_data_fingerprint"
        ),
        "model_fingerprint": model_fingerprint,
        "model_chronology": {
            "passed": chronology_passed,
            "minimum_training_labels": RIDGE_MIN_TRAIN,
            "first_prediction_index": RIDGE_MIN_TRAIN,
            "latest_rows": {str(horizon): ridge_chronology[horizon][-1] for horizon in (6, 12)},
        },
        "selection_repair": {
            "protocol": {
                "outer_train_months": OUTER_TRAIN_MONTHS,
                "outer_embargo_months": OUTER_EMBARGO_MONTHS,
                "outer_test_months": OUTER_TEST_MONTHS,
                "inner_train_months": INNER_TRAIN_MONTHS,
                "inner_embargo_months": INNER_EMBARGO_MONTHS,
                "inner_validation_months": INNER_VALIDATION_MONTHS,
                "independent_index": "WPUT",
                "independent_index_used_for_selection": False,
            },
            "chronology": nested_chronology,
            "portfolio_selection": portfolio_selection.contract,
            "timing_selection": timing_selection.contract,
            "historical_reuse": True,
            "diagnostic_only": True,
            "promotion_eligible": False,
        },
        "objective_lanes": objective_lanes,
        "split": split,
        "split_fingerprint": split_fingerprint,
        "development_selection": {
            "window": split["development"],
            "months": DEVELOPMENT_MONTHS,
            "selected_candidate_id": winner.candidate_id,
            "selection_metric": (
                "development cash-excess Sharpe after 50bp annual and 25bp turnover costs"
            ),
        },
        "holdout_confirmation": {
            "window": split["holdout"],
            "months": holdout_months,
            **standalone_live["metrics"],
        },
        "standalone_live_lane": standalone_live,
        "standalone_paper_lane": standalone_paper,
        "timing_enhancement_lane": timing_lane,
        "reference_control": reference_control,
        "objective_gate_calibration": objective_calibration,
        "repository_gate_calibration": calibration_evidence,
        "full_gate_controls": full_gate_controls,
        "prior_adoption_audit": prior_adoption,
        "selection_sanity": {
            "development_winner_matches_best_holdout": winner.candidate_id
            == best_holdout["candidate_id"],
            "best_holdout_candidate_id": best_holdout["candidate_id"],
            "posthoc_standalone_live_candidate_ids": posthoc_live,
            "posthoc_standalone_paper_candidate_ids": posthoc_paper,
            "promotion_allowed": False,
        },
        "legacy_selection": {
            "protocol": "spec-164 one-shot development selection and untouched holdout",
            "development_selection": {
                "window": split["development"],
                "months": DEVELOPMENT_MONTHS,
                "selected_candidate_id": winner.candidate_id,
            },
            "holdout_confirmation": {
                "window": split["holdout"],
                "months": holdout_months,
                **standalone_live["metrics"],
            },
            "standalone_live_lane": standalone_live,
            "standalone_paper_lane": standalone_paper,
            "timing_enhancement_lane": timing_lane,
            "decision": legacy_decision,
            "selection_sanity": {
                "development_winner_matches_best_holdout": winner.candidate_id
                == best_holdout["candidate_id"],
                "best_holdout_candidate_id": best_holdout["candidate_id"],
                "posthoc_standalone_live_candidate_ids": posthoc_live,
                "posthoc_standalone_paper_candidate_ids": posthoc_paper,
                "promotion_allowed": False,
            },
        },
        "trial_records": records,
        "audit_records": audit_records,
        "development_returns": development_returns,
        "development_segment_sharpes": development_segments,
        "decision": decision,
        "research_candidate": None,
        "paper_candidate": None,
        "research_live_parity": {
            "passed": False,
            "intended_expressions": list(INTENDED_EXPRESSIONS),
            "reason": (
                "exact policy code, executable history parity, assignment, tax, margin, "
                "collateral, whitelist, hardened canary, and consumer fingerprint are missing"
            ),
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "target_weights": target_weights,
            "target_weights_digest": _fingerprint(target_weights),
        },
        "criterion_audit": {
            "premium_question": (
                "does cash-secured PUT exposure beat cash after costs?"
            ),
            "portfolio_adoption_question": (
                "does selected PUT exposure improve broad-equity risk-adjusted outcomes?"
            ),
            "timing_question": "does automation improve matching passive PUT exposure?",
            "timing_is_non_blocking_for_premium": True,
            "threshold_change_after_results": False,
            "prior_candidate_reclassification": False,
            "historical_reuse": True,
            "public_history_point_in_time": False,
            "benchmark_execution_parity": False,
        },
        "safety": [
            "research evidence only",
            "no broker API",
            "no orders",
            "no capital, margin, cap, arming, whitelist, constitution, or kernel change",
        ],
    }


def render_options_variance_risk_premium_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    holdout = payload["legacy_selection"]["holdout_confirmation"]
    reference = payload["reference_control"]
    objectives = payload["objective_lanes"]
    return "\n".join(
        [
            "# 옵션 선택·목적 교정 독립 전략 공장",
            "",
            f"- 관문 진단: `{decision['criterion_diagnosis']}`",
            f"- 진단 판정: `{decision['verdict']}`",
            f"- 최신 중첩 선택 후보: `{decision['provisional_best_candidate_id']}`",
            f"- 감사 시도: {payload['global_audit_trial_count']}회 (현재 전략군 16회)",
            f"- 기존 홀드아웃: {holdout['months']}개월, 현금 초과 PSR {holdout['psr_vs_cash']}",
            f"- 교차지수 프리미엄 존재: {objectives['premium_existence']['passed']}",
            f"- 교차지수 포트폴리오 채택: {objectives['portfolio_adoption']['passed']}",
            f"- 교차지수 자동 타이밍 추가가치: {objectives['timing_value']['passed']}",
            "- WPUT 선택 입력 사용: False",
            f"- 중첩 시간 순서: {payload['selection_repair']['chronology']['all_folds_valid']}",
            f"- 알려진 PUT 기준 관문 인식: {reference['recognized_reference_passed']}",
            f"- 알려진 PUT 현금 프리미엄 존재: {reference['economic_premium_detected']}",
            f"- 평균 0 대조군 기각: {reference['mean_zero_null_rejected']}",
            "- 실패 교차지수 목적: "
            f"{', '.join(decision['failed_standalone_live_gates']) or '없음'}",
            "- 역사 결과 승격 가능: False",
            "- PUTW/SPX 옵션 실행 정합: False",
            "- 주문/자본/마진/허용목록 변경: 0",
        ]
    )


__all__ = [
    "FRENCH_DAILY_URL",
    "PUT_URL",
    "VIX_URL",
    "WPUT_URL",
    "OptionsPremiumBundle",
    "OptionsPremiumPolicy",
    "VarianceRiskPremiumSnapshot",
    "audit_prior_adoption",
    "calibrate_options_premium_gate",
    "expected_shortfall_95",
    "generate_options_premium_candidates",
    "load_options_premium_bundle",
    "options_target_weight",
    "parse_cboe_put_history",
    "parse_cboe_vix_history",
    "parse_cboe_wput_history",
    "parse_fama_french_daily",
    "render_options_variance_risk_premium_markdown",
    "run_options_variance_risk_premium_factory",
    "standalone_premium_lane",
    "premium_existence_lane",
    "portfolio_adoption_lane",
    "timing_enhancement_lane",
    "validate_options_premium_bundle",
]
