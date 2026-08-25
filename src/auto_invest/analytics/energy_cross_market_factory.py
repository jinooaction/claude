"""Spec 163: independent energy cross-market strategy factory."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import statistics
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from statistics import NormalDist
from typing import Any

import numpy as np
import xlrd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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
    GATE_VERSION,
    HOLDOUT_PSR_MIN,
    PAPER_PSR_MIN,
)
from auto_invest.analytics.global_trend import gold_total_return_factors
from auto_invest.analytics.multi_asset_trend import bond_total_return_factors, correlation
from auto_invest.analytics.real_world_gate_controls import FULL_GATE_CONTROLS_VALID
from auto_invest.analytics.risk_managed_beta import (
    MonthlyRow,
    market_total_return_factors,
    summarize,
)
from auto_invest.market_data.public_data import SeriesPoint

SCHEMA_VERSION = "1.0"
EXPECTED_CANDIDATES = 16
EXPECTED_PRIOR_TRIALS = 720
EXPECTED_GLOBAL_AUDIT_TRIALS = 736
DEVELOPMENT_MONTHS = 120
EMBARGO_MONTHS = 1
MIN_HOLDOUT_MONTHS = 180
MIN_FACTOR_MONTHS = 301
RIDGE_ALPHA = 10.0
RIDGE_MIN_TRAIN = 60
FACTORY_EDGE = "FACTORY_EDGE"
PAPER_CHALLENGER = "PAPER_CHALLENGER"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
OBJECTIVE = "standalone_energy_timing"
FAMILIES = (
    "wti_trend",
    "refining_margin",
    "market_breadth",
    "ridge_forecast",
)
FRENCH_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "49_Industry_Portfolios_CSV.zip"
)
INTENDED_LIVE_SYMBOL = "XLE"
LIVE_IMPLEMENTATION_AVAILABLE = False
LIVE_WHITELIST_AUTHORIZED = False


@dataclass(frozen=True)
class EiaSeriesSpec:
    series_id: str
    name: str
    unit: str
    url: str


EIA_SERIES = {
    "RWTC": EiaSeriesSpec(
        "RWTC",
        "wti_crude",
        "Dollars per Barrel",
        "https://www.eia.gov/dnav/pet/hist_xls/RWTCm.xls",
    ),
    "EER_EPMRU_PF4_RGC_DPG": EiaSeriesSpec(
        "EER_EPMRU_PF4_RGC_DPG",
        "gulf_gasoline",
        "Dollars per Gallon",
        "https://www.eia.gov/dnav/pet/hist_xls/EER_EPMRU_PF4_RGC_DPGm.xls",
    ),
    "EER_EPD2F_PF4_Y35NY_DPG": EiaSeriesSpec(
        "EER_EPD2F_PF4_Y35NY_DPG",
        "ny_heating_oil",
        "Dollars per Gallon",
        "https://www.eia.gov/dnav/pet/hist_xls/EER_EPD2F_PF4_Y35NY_DPGm.xls",
    ),
    "RNGWHHD": EiaSeriesSpec(
        "RNGWHHD",
        "henry_hub_natural_gas",
        "Dollars per Million Btu",
        "https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDm.xls",
    ),
}


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _content_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _shift_month(value: date, months: int) -> date:
    offset = value.year * 12 + value.month - 1 + months
    return date(offset // 12, offset % 12 + 1, 1)


def _month_end(value: date) -> date:
    return _shift_month(_month_start(value), 1) - timedelta(days=1)


@dataclass(frozen=True)
class EnergyMarketObservation:
    series_id: str
    period_month: date
    available_month: date
    value: float
    unit: str
    source_url: str
    content_digest: str


@dataclass(frozen=True)
class EnergyFeatureSnapshot:
    target_month: date
    source_month: date
    horizon_months: int
    wti_return: float
    gasoline_return: float
    heating_return: float
    natural_gas_return: float
    crack_margin: float
    crack_zscore: float

    def model_features(self) -> tuple[float, ...]:
        return (
            self.wti_return,
            self.gasoline_return,
            self.heating_return,
            self.natural_gas_return,
            self.crack_zscore,
        )


@dataclass(frozen=True)
class EnergyCrossMarketPolicy:
    family: str
    feature_horizon: int
    max_energy_weight: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "feature_horizon": self.feature_horizon,
            "max_energy_weight": str(self.max_energy_weight),
            "ridge_alpha": RIDGE_ALPHA if self.family == "ridge_forecast" else None,
            "ridge_min_train": (
                RIDGE_MIN_TRAIN if self.family == "ridge_forecast" else None
            ),
        }


@dataclass(frozen=True)
class EnergyCrossMarketCandidate:
    candidate_id: str
    trial_index: int
    policy: EnergyCrossMarketPolicy
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.policy.family,
            "policy": self.policy.as_dict(),
            "strategy_fingerprint": self.strategy_fingerprint,
            "research_proxy": "Kenneth French 49-industry value-weighted Oil",
            "intended_live_symbol": INTENDED_LIVE_SYMBOL,
            "live_expressible": LIVE_IMPLEMENTATION_AVAILABLE,
            "live_blocker": (
                "XLE policy, history parity, whitelist authorization, and exact "
                "strategy fingerprint are not implemented"
            ),
        }


@dataclass(frozen=True)
class EnergyCrossMarketBundle:
    factor_months: tuple[str, ...]
    energy_factors: tuple[float, ...]
    cash_factors: tuple[float, ...]
    features: dict[int, tuple[EnergyFeatureSnapshot, ...]]
    quality: dict[str, Any]


def parse_eia_monthly_series(
    raw: bytes,
    expected_series_id: str,
) -> tuple[EnergyMarketObservation, ...]:
    spec = EIA_SERIES.get(expected_series_id)
    if spec is None:
        raise ValueError("unsupported EIA energy series identity")
    try:
        workbook = xlrd.open_workbook(file_contents=raw)
        sheet = workbook.sheet_by_name("Data 1")
    except (xlrd.XLRDError, IndexError) as exc:
        raise ValueError("EIA monthly workbook schema mismatch") from exc
    if sheet.nrows < 300 or str(sheet.cell_value(1, 1)).strip() != expected_series_id:
        raise ValueError("EIA monthly series identity or coverage mismatch")
    header = str(sheet.cell_value(2, 1)).strip()
    if spec.unit not in header:
        raise ValueError("EIA monthly series unit mismatch")
    output: list[EnergyMarketObservation] = []
    seen: set[date] = set()
    digest = _content_digest(raw)
    for index in range(3, sheet.nrows):
        try:
            serial = float(sheet.cell_value(index, 0))
            value = float(sheet.cell_value(index, 1))
            period = _month_start(
                xlrd.xldate_as_datetime(serial, workbook.datemode).date()
            )
        except (TypeError, ValueError, xlrd.XLDateError) as exc:
            raise ValueError("EIA monthly row schema mismatch") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("EIA monthly value must be finite and positive")
        if period in seen:
            raise ValueError("EIA monthly period is duplicated")
        seen.add(period)
        output.append(
            EnergyMarketObservation(
                expected_series_id,
                period,
                _shift_month(period, 2),
                value,
                spec.unit,
                spec.url,
                digest,
            )
        )
    if [item.period_month for item in output] != sorted(item.period_month for item in output):
        raise ValueError("EIA monthly periods must increase")
    return tuple(output)


def parse_french_oil_returns(raw: bytes) -> tuple[tuple[date, float], ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError("French industry ZIP must contain one CSV")
            text = archive.read(names[0]).decode("utf-8-sig")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError("French industry ZIP schema mismatch") from exc
    lines = text.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "Average Value Weighted Returns -- Monthly" in line
        ),
        None,
    )
    if header_index is None or header_index + 1 >= len(lines):
        raise ValueError("French value-weighted monthly Oil table is missing")
    header = next(csv.reader([lines[header_index + 1]]))
    normalized = [value.strip() for value in header]
    if "Oil" not in normalized:
        raise ValueError("French value-weighted monthly Oil column is missing")
    oil_index = normalized.index("Oil")
    output: list[tuple[date, float]] = []
    for line in lines[header_index + 2 :]:
        row = next(csv.reader([line]))
        key = row[0].strip() if row else ""
        if not (len(key) == 6 and key.isdigit()):
            break
        if oil_index >= len(row):
            raise ValueError("French monthly Oil row is incomplete")
        value = float(row[oil_index].strip())
        if not math.isfinite(value) or value <= -99:
            raise ValueError("French monthly Oil return is invalid")
        factor = 1.0 + value / 100.0
        if factor <= 0:
            raise ValueError("French monthly Oil factor must be positive")
        output.append((date(int(key[:4]), int(key[4:]), 1), factor))
    if len(output) < MIN_FACTOR_MONTHS:
        raise ValueError("French monthly Oil coverage is incomplete")
    if len({month for month, _ in output}) != len(output):
        raise ValueError("French monthly Oil period is duplicated")
    return tuple(output)


def _crack_margin(wti: float, gasoline: float, heating: float) -> float:
    return ((2.0 * gasoline + heating) * 42.0 - 3.0 * wti) / 3.0


def _zscore(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise ValueError("crack margin z-score requires two observations")
    deviation = statistics.stdev(values)
    return 0.0 if deviation <= 1e-12 else (values[-1] - statistics.mean(values)) / deviation


def load_energy_cross_market_bundle(
    eia_raw_by_series: dict[str, bytes],
    french_raw: bytes,
    cash_points: list[SeriesPoint],
    *,
    current_date: date,
) -> EnergyCrossMarketBundle:
    if set(eia_raw_by_series) != set(EIA_SERIES):
        raise ValueError("EIA energy cross-market bundle is incomplete")
    observations = {
        series_id: parse_eia_monthly_series(raw, series_id)
        for series_id, raw in eia_raw_by_series.items()
    }
    maps = {
        series_id: {item.period_month: item.value for item in rows}
        for series_id, rows in observations.items()
    }
    oil_returns = parse_french_oil_returns(french_raw)
    oil_map = dict(oil_returns)
    candidate_months: list[date] = []
    for target_month in sorted(oil_map):
        source_month = _shift_month(target_month, -2)
        if all(
            source_month in values and _shift_month(source_month, -12) in values
            for values in maps.values()
        ) and _latest_rate_before(cash_points, target_month) is not None:
            candidate_months.append(target_month)
    if len(candidate_months) < MIN_FACTOR_MONTHS:
        raise ValueError("energy cross-market alignment does not leave 301 factor months")

    features: dict[int, tuple[EnergyFeatureSnapshot, ...]] = {}
    for horizon in (6, 12):
        horizon_rows: list[EnergyFeatureSnapshot] = []
        for target_month in candidate_months:
            source_month = _shift_month(target_month, -2)
            prior_month = _shift_month(source_month, -horizon)

            def trailing(
                series_id: str,
                current: date = source_month,
                prior: date = prior_month,
            ) -> float:
                return maps[series_id][current] / maps[series_id][prior] - 1.0

            crack_history = [
                _crack_margin(
                    maps["RWTC"][_shift_month(source_month, -offset)],
                    maps["EER_EPMRU_PF4_RGC_DPG"][_shift_month(source_month, -offset)],
                    maps["EER_EPD2F_PF4_Y35NY_DPG"][_shift_month(source_month, -offset)],
                )
                for offset in range(horizon, -1, -1)
            ]
            horizon_rows.append(
                EnergyFeatureSnapshot(
                    target_month=target_month,
                    source_month=source_month,
                    horizon_months=horizon,
                    wti_return=trailing("RWTC"),
                    gasoline_return=trailing("EER_EPMRU_PF4_RGC_DPG"),
                    heating_return=trailing("EER_EPD2F_PF4_Y35NY_DPG"),
                    natural_gas_return=trailing("RNGWHHD"),
                    crack_margin=crack_history[-1],
                    crack_zscore=_zscore(crack_history),
                )
            )
        features[horizon] = tuple(horizon_rows)

    cash_rates = [_latest_rate_before(cash_points, month) for month in candidate_months]
    cash_factors = tuple(1.0 + float(value) / 1200.0 for value in cash_rates if value is not None)
    latest_eia = {
        series_id: rows[-1].period_month for series_id, rows in observations.items()
    }
    observed_cash = [point for point in cash_points if point.value is not None]
    cash_age = (
        current_date - date.fromisoformat(observed_cash[-1].date)
    ).days if observed_cash else 10_000
    french_latest = oil_returns[-1][0]
    eia_ages = {
        f"{series_id.lower()}_age_days": (
            current_date - _month_end(period)
        ).days
        for series_id, period in latest_eia.items()
    }
    french_age = (current_date - _month_end(french_latest)).days
    complete = bool(
        len(candidate_months) >= MIN_FACTOR_MONTHS
        and len(candidate_months) - DEVELOPMENT_MONTHS - EMBARGO_MONTHS
        >= MIN_HOLDOUT_MONTHS
        and len(cash_factors) == len(candidate_months)
        and all(0 <= age <= 45 for age in eia_ages.values())
        and 0 <= french_age <= 90
        and 0 <= cash_age <= 7
    )
    quality = {
        "complete": complete,
        "factor_months": len(candidate_months),
        "first_factor_month": candidate_months[0].isoformat(),
        "last_factor_month": candidate_months[-1].isoformat(),
        "publication_lag": "EIA month t first affects target return month t+2",
        "point_in_time": False,
        "revision_limitation": (
            "current EIA spot histories and reconstructed French industry returns are "
            "source-hashed but are not vintage archives"
        ),
        "french_source": {
            "url": FRENCH_URL,
            "digest": _content_digest(french_raw),
            "last_month": french_latest.isoformat(),
            "age_days": french_age,
            "research_proxy": "49-industry value-weighted Oil",
        },
        "eia_sources": {
            series_id: {
                "name": EIA_SERIES[series_id].name,
                "unit": EIA_SERIES[series_id].unit,
                "url": EIA_SERIES[series_id].url,
                "digest": rows[-1].content_digest,
                "first_month": rows[0].period_month.isoformat(),
                "last_month": rows[-1].period_month.isoformat(),
                "age_days": eia_ages[f"{series_id.lower()}_age_days"],
            }
            for series_id, rows in observations.items()
        },
        "cash_age_days": cash_age,
        "basis_risk": (
            "French Oil is not XLE; WTI and product hubs are not a matched refinery slate"
        ),
    }
    return EnergyCrossMarketBundle(
        factor_months=tuple(month.isoformat() for month in candidate_months),
        energy_factors=tuple(oil_map[month] for month in candidate_months),
        cash_factors=cash_factors,
        features=features,
        quality=quality,
    )


def generate_energy_cross_market_candidates() -> tuple[EnergyCrossMarketCandidate, ...]:
    output: list[EnergyCrossMarketCandidate] = []
    for family in FAMILIES:
        for horizon in (6, 12):
            for maximum in (Decimal("0.5"), Decimal("1.0")):
                policy = EnergyCrossMarketPolicy(family, horizon, maximum)
                digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": policy.as_dict()})
                output.append(
                    EnergyCrossMarketCandidate(
                        candidate_id=f"energy-cross-{family}-{digest[7:19]}",
                        trial_index=len(output) + 1,
                        policy=policy,
                        strategy_fingerprint=_fingerprint(
                            {
                                "objective": OBJECTIVE,
                                "research_proxy": "French49_Oil",
                                "intended_live_symbol": INTENDED_LIVE_SYMBOL,
                                "eia_series": sorted(EIA_SERIES),
                                "publication_lag_months": 2,
                                "costs_bps": [10, 25, 50],
                                "policy": policy.as_dict(),
                            }
                        ),
                    )
                )
    if len(output) != EXPECTED_CANDIDATES:
        raise RuntimeError("energy cross-market candidate count contract violated")
    if len({row.candidate_id for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("energy cross-market candidate ids are not unique")
    if len({row.strategy_fingerprint for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("energy cross-market strategy fingerprints are not unique")
    return tuple(output)


def validate_energy_cross_market_bundle(bundle: EnergyCrossMarketBundle) -> None:
    if bundle.quality.get("complete") is not True:
        raise ValueError("energy cross-market data is incomplete or stale")


def expanding_ridge_predictions(
    features: Sequence[Sequence[float]],
    targets: Sequence[float],
    *,
    min_train: int = RIDGE_MIN_TRAIN,
) -> tuple[list[float | None], list[dict[str, int | None]]]:
    if len(features) != len(targets):
        raise ValueError("ridge features and targets must align")
    if min_train < 2:
        raise ValueError("ridge minimum training count must be at least two")
    matrix = np.asarray(features, dtype=float)
    labels = np.asarray(targets, dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all() or not np.isfinite(labels).all():
        raise ValueError("ridge inputs must be finite two-dimensional data")
    predictions: list[float | None] = []
    chronology: list[dict[str, int | None]] = []
    for index in range(len(labels)):
        chronology.append(
            {
                "prediction_index": index,
                "latest_training_target_index": index - 1 if index >= min_train else None,
                "training_rows": index if index >= min_train else 0,
            }
        )
        if index < min_train:
            predictions.append(None)
            continue
        model = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
        model.fit(matrix[:index], labels[:index])
        prediction = float(model.predict(matrix[index : index + 1])[0])
        if not math.isfinite(prediction):
            raise ValueError("ridge produced a non-finite prediction")
        predictions.append(prediction)
    return predictions, chronology


def energy_target_weight(
    policy: EnergyCrossMarketPolicy,
    feature: EnergyFeatureSnapshot,
    *,
    ridge_prediction: float | None = None,
) -> Decimal:
    if policy.feature_horizon != feature.horizon_months:
        raise ValueError("energy policy and feature horizons differ")
    if policy.family == "wti_trend":
        active = feature.wti_return > 0
    elif policy.family == "refining_margin":
        active = feature.crack_zscore > 0
    elif policy.family == "market_breadth":
        active = sum(
            value > 0
            for value in (
                feature.wti_return,
                feature.gasoline_return,
                feature.heating_return,
                feature.natural_gas_return,
            )
        ) >= 3
    elif policy.family == "ridge_forecast":
        active = ridge_prediction is not None and ridge_prediction > 0
    else:
        raise ValueError(f"unknown energy cross-market family: {policy.family}")
    return policy.max_energy_weight if active else Decimal("0")


def _candidate_factors(
    candidate: EnergyCrossMarketCandidate,
    bundle: EnergyCrossMarketBundle,
    ridge_predictions: dict[int, list[float | None]],
    *,
    cost_bps: int,
) -> tuple[list[float], list[Decimal], float]:
    horizon = candidate.policy.feature_horizon
    features = bundle.features[horizon]
    if not (
        len(features)
        == len(bundle.energy_factors)
        == len(bundle.cash_factors)
        == len(ridge_predictions[horizon])
    ):
        raise ValueError("energy candidate inputs do not align")
    output: list[float] = []
    weights: list[Decimal] = []
    previous = Decimal("0")
    turnover_total = Decimal("0")
    for index, feature in enumerate(features):
        weight = energy_target_weight(
            candidate.policy,
            feature,
            ridge_prediction=ridge_predictions[horizon][index],
        )
        turnover = abs(weight - previous)
        gross = (
            float(weight) * bundle.energy_factors[index]
            + (1.0 - float(weight)) * bundle.cash_factors[index]
        )
        net = gross * (1.0 - float(turnover) * cost_bps / 10_000.0)
        if not math.isfinite(net) or net <= 0:
            raise ValueError("energy cost model produced a non-positive factor")
        output.append(net)
        weights.append(weight)
        turnover_total += turnover
        previous = weight
    return output, weights, float(turnover_total)


def _passive_energy_factors(values: Sequence[float], cost_bps: int = 25) -> list[float]:
    output = list(values)
    if output:
        output[0] *= 1.0 - cost_bps / 10_000.0
    return output


def _annualized_excess(candidate: Sequence[float], cash: Sequence[float]) -> float:
    if not candidate or len(candidate) != len(cash):
        raise ValueError("annualized excess factors must align")
    relative = math.prod(left / right for left, right in zip(candidate, cash, strict=True))
    return relative ** (12.0 / len(candidate)) - 1.0


def standalone_lane(
    candidate_factors_25bps: Sequence[float],
    cash_factors: Sequence[float],
    passive_energy_factors_25bps: Sequence[float],
    *,
    active_fraction: float,
    candidate_factors_50bps: Sequence[float] | None = None,
    paper: bool,
) -> dict[str, Any]:
    if not (
        len(candidate_factors_25bps)
        == len(cash_factors)
        == len(passive_energy_factors_25bps)
    ):
        raise ValueError("standalone lane factors must align")
    candidate50 = candidate_factors_50bps or candidate_factors_25bps
    excess_returns = [
        candidate / cash - 1.0
        for candidate, cash in zip(candidate_factors_25bps, cash_factors, strict=True)
    ]
    psr = probabilistic_sharpe(excess_returns)
    annual_excess = _annualized_excess(candidate50, cash_factors)
    candidate_stats = summarize(list(candidate_factors_25bps))
    passive_stats = summarize(list(passive_energy_factors_25bps))
    sharpe_improvement = candidate_stats.sharpe - passive_stats.sharpe
    if paper:
        thresholds = {
            "psr": PAPER_PSR_MIN,
            "annual": 0.0,
            "sharpe": 0.0,
            "drawdown": passive_stats.max_dd_pct * 1.20,
        }
    else:
        thresholds = {
            "psr": HOLDOUT_PSR_MIN,
            "annual": 0.02,
            "sharpe": 0.10,
            "drawdown": passive_stats.max_dd_pct,
        }

    def gate(passed: bool, actual: Any, required: str) -> dict[str, Any]:
        return {"passed": bool(passed), "actual": actual, "required": required}

    gates = {
        "holdout_cash_excess_psr": gate(
            psr is not None and psr >= Decimal(str(thresholds["psr"])),
            None if psr is None else str(psr),
            f">= {thresholds['psr']}",
        ),
        "annual_cash_excess_50bps": gate(
            annual_excess > thresholds["annual"]
            if paper
            else annual_excess >= thresholds["annual"],
            round(annual_excess, 8),
            "> 0" if paper else ">= 0.02",
        ),
        "energy_buyhold_sharpe_improvement": gate(
            sharpe_improvement >= thresholds["sharpe"],
            round(sharpe_improvement, 6),
            f">= {thresholds['sharpe']}",
        ),
        "energy_buyhold_drawdown": gate(
            candidate_stats.max_dd_pct <= thresholds["drawdown"],
            round(candidate_stats.max_dd_pct, 6),
            f"<= {thresholds['drawdown']:.6f}",
        ),
        "energy_exposure_diversity": gate(
            0.10 <= active_fraction <= 0.90,
            round(active_fraction, 6),
            "0.10 <= fraction <= 0.90",
        ),
    }
    return {
        "passed": all(value["passed"] for value in gates.values()),
        "paper": paper,
        "gates": gates,
        "metrics": {
            "psr_vs_cash": None if psr is None else str(psr),
            "annual_cash_excess_50bps": round(annual_excess, 8),
            "candidate_sharpe_25bps": candidate_stats.sharpe,
            "passive_energy_sharpe_25bps": passive_stats.sharpe,
            "sharpe_improvement": round(sharpe_improvement, 6),
            "candidate_max_drawdown_pct": candidate_stats.max_dd_pct,
            "passive_energy_max_drawdown_pct": passive_stats.max_dd_pct,
            "active_fraction": round(active_fraction, 6),
        },
    }


def _diversifier_lane(
    candidate: Sequence[float],
    candidate50: Sequence[float],
    cash: Sequence[float],
    incumbent: Sequence[float],
) -> dict[str, Any]:
    excess = [left / right - 1.0 for left, right in zip(candidate, cash, strict=True)]
    psr = probabilistic_sharpe(excess)
    annual_excess = _annualized_excess(candidate50, cash)
    incumbent_stats = summarize(list(incumbent))
    blend = [
        0.8 * left + 0.2 * right
        for left, right in zip(incumbent, candidate, strict=True)
    ]
    blend_stats = summarize(blend)
    corr = correlation(list(incumbent), list(candidate))
    corr = 1.0 if corr is None else corr
    improvement = blend_stats.sharpe - incumbent_stats.sharpe
    gates = {
        "holdout_excess_psr": psr is not None and psr >= Decimal(str(HOLDOUT_PSR_MIN)),
        "holdout_excess_50bps_positive": annual_excess > 0,
        "incumbent_correlation": corr < 0.80,
        "blend_sharpe_improvement": improvement >= 0.05,
        "blend_drawdown_non_worsening": (
            blend_stats.max_dd_pct <= incumbent_stats.max_dd_pct
        ),
    }
    return {
        "passed": all(gates.values()),
        "gates": gates,
        "metrics": {
            "psr_vs_cash": None if psr is None else str(psr),
            "annual_cash_excess_50bps": round(annual_excess, 8),
            "incumbent_correlation": corr,
            "incumbent_sharpe": incumbent_stats.sharpe,
            "blend_sharpe": blend_stats.sharpe,
            "blend_sharpe_improvement": round(improvement, 6),
            "incumbent_max_drawdown_pct": incumbent_stats.max_dd_pct,
            "blend_max_drawdown_pct": blend_stats.max_dd_pct,
        },
    }


def calibrate_standalone_family(
    holdout_months: int,
    *,
    repetitions: int = 500,
    seed: int = 16300,
) -> dict[str, Any]:
    if holdout_months < MIN_HOLDOUT_MONTHS:
        raise ValueError("standalone calibration requires the minimum holdout")
    if repetitions < 1:
        raise ValueError("standalone calibration repetitions must be positive")
    rng = random.Random(seed)
    null_passes = 0
    planted_passes = 0
    planted_selected = 0

    def returns(count: int, mean: float, sigma: float) -> list[float]:
        return [rng.gauss(mean, sigma) for _ in range(count)]

    for _ in range(repetitions):
        null_development = [returns(DEVELOPMENT_MONTHS, 0.0, 0.04) for _ in range(16)]
        null_winner = max(range(16), key=lambda index: annualized_sharpe(null_development[index]))
        null_holdout = returns(holdout_months, 0.0, 0.04)
        null_passive = returns(holdout_months, 0.0, 0.05)
        null_lane = standalone_lane(
            [1.0 + value for value in null_holdout],
            [1.0] * holdout_months,
            [1.0 + value for value in null_passive],
            active_fraction=0.5,
            paper=False,
        )
        null_passes += int(null_lane["passed"] and null_winner >= 0)

        planted_development = [returns(DEVELOPMENT_MONTHS, 0.0, 0.04) for _ in range(15)]
        planted_development.insert(0, returns(DEVELOPMENT_MONTHS, 0.010, 0.035))
        planted_winner = max(
            range(16), key=lambda index: annualized_sharpe(planted_development[index])
        )
        planted_selected += int(planted_winner == 0)
        if planted_winner == 0:
            planted_holdout = returns(holdout_months, 0.010, 0.035)
        else:
            planted_holdout = returns(holdout_months, 0.0, 0.04)
        planted_passive = returns(holdout_months, 0.004, 0.05)
        planted_lane = standalone_lane(
            [1.0 + value for value in planted_holdout],
            [1.0] * holdout_months,
            [1.0 + value for value in planted_passive],
            active_fraction=0.5,
            paper=False,
        )
        planted_passes += int(planted_lane["passed"])
    return {
        "method": "16-candidate development selection with independent holdout Monte Carlo",
        "seed": seed,
        "repetitions": repetitions,
        "holdout_months": holdout_months,
        "null_false_acceptance_rate": round(null_passes / repetitions, 6),
        "planted_edge_selection_rate": round(planted_selected / repetitions, 6),
        "planted_edge_detection_rate": round(planted_passes / repetitions, 6),
        "planted_monthly_mean": 0.010,
        "planted_monthly_volatility": 0.035,
        "passable": bool(
            null_passes / repetitions <= 0.05
            and planted_passes / repetitions >= 0.70
        ),
    }


def _segments(returns: list[float], count: int = 10) -> list[list[float]]:
    size = len(returns) // count
    if size < 2:
        return []
    return [
        returns[index * size : (index + 1) * size if index < count - 1 else len(returns)]
        for index in range(count)
    ]


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
    return [unique[key] for key in sorted(unique)][:EXPECTED_PRIOR_TRIALS]


def _full_controls_valid(payload: dict[str, Any], *, code_commit: str) -> bool:
    return bool(
        payload.get("verdict") == FULL_GATE_CONTROLS_VALID
        and payload.get("promotion_control_passed") is True
        and payload.get("code_commit") == code_commit
        and str(payload.get("control_fingerprint", "")).startswith("sha256:")
        and payload.get("positive_control", {}).get("passed") is True
        and payload.get("null_control", {}).get("passed") is False
    )


def _actual_holdout_power(holdout_months: int) -> dict[str, Any]:
    normal = NormalDist()
    critical = normal.inv_cdf(HOLDOUT_PSR_MIN)
    minimum_80 = critical + normal.inv_cdf(0.80)
    return {
        "holdout_months": holdout_months,
        "live_threshold": HOLDOUT_PSR_MIN,
        "null_false_positive_approx": round(1.0 - HOLDOUT_PSR_MIN, 6),
        "minimum_80pct_detectable_annual_sharpe_approx": round(
            minimum_80 / math.sqrt(holdout_months / 12.0), 6
        ),
    }


def _development_winner_index(records: Sequence[dict[str, Any]]) -> int:
    if not records:
        raise ValueError("energy development selection requires candidate records")
    return min(
        range(len(records)),
        key=lambda index: (
            -float(records[index]["development_sharpe_excess_25bps"]),
            float(records[index]["development_max_drawdown_25bps"]),
            str(records[index]["candidate_id"]),
        ),
    )


def run_energy_cross_market_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    bundle: EnergyCrossMarketBundle,
    *,
    prior_factory_payload: dict[str, Any],
    calibration_evidence: dict[str, Any],
    full_gate_controls: dict[str, Any],
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
    calibration_repetitions: int = 500,
) -> dict[str, Any]:
    factor_count = len(bundle.factor_months)
    if len(rows) != factor_count + 1 or len(gold_levels) != len(rows):
        raise ValueError("energy incumbent levels must have one pre-factor month")
    if [row.date[:7] for row in rows[1:]] != [value[:7] for value in bundle.factor_months]:
        raise ValueError("energy incumbent dates do not align with factor months")
    if not (
        factor_count
        == len(bundle.energy_factors)
        == len(bundle.cash_factors)
        == len(bundle.features[6])
        == len(bundle.features[12])
    ):
        raise ValueError("energy cross-market bundle lengths differ")
    holdout_start = DEVELOPMENT_MONTHS + EMBARGO_MONTHS
    holdout_months = factor_count - holdout_start
    if factor_count < MIN_FACTOR_MONTHS or holdout_months < MIN_HOLDOUT_MONTHS:
        raise ValueError("energy holdout must contain at least 180 months")

    candidates = generate_energy_cross_market_candidates()
    market = market_total_return_factors(rows)
    bond = bond_total_return_factors(rows)
    gold = gold_total_return_factors(gold_levels)
    incumbent = [sum(values) / 3.0 for values in zip(market, bond, gold, strict=True)]
    incumbent_holdout = incumbent[holdout_start:]
    passive25 = _passive_energy_factors(bundle.energy_factors, 25)
    target_excess = [
        energy / cash - 1.0
        for energy, cash in zip(bundle.energy_factors, bundle.cash_factors, strict=True)
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
    development_returns: list[list[float]] = []
    development_segments: list[list[float]] = []
    holdout_by_cost: list[dict[int, list[float]]] = []
    weights_by_candidate: list[list[Decimal]] = []
    for candidate in candidates:
        by_cost: dict[int, list[float]] = {}
        weights: list[Decimal] = []
        turnover = 0.0
        for cost in (10, 25, 50):
            factors, current_weights, current_turnover = _candidate_factors(
                candidate,
                bundle,
                ridge_predictions,
                cost_bps=cost,
            )
            by_cost[cost] = factors
            if cost == 25:
                weights = current_weights
                turnover = current_turnover
        development = [
            factor / cash - 1.0
            for factor, cash in zip(
                by_cost[25][:DEVELOPMENT_MONTHS],
                bundle.cash_factors[:DEVELOPMENT_MONTHS],
                strict=True,
            )
        ]
        development_stats = summarize(by_cost[25][:DEVELOPMENT_MONTHS])
        holdout25 = by_cost[25][holdout_start:]
        holdout50 = by_cost[50][holdout_start:]
        holdout_weights = weights[holdout_start:]
        active_fraction = sum(weight > 0 for weight in holdout_weights) / len(holdout_weights)
        standalone_live = standalone_lane(
            holdout25,
            bundle.cash_factors[holdout_start:],
            passive25[holdout_start:],
            active_fraction=active_fraction,
            candidate_factors_50bps=holdout50,
            paper=False,
        )
        standalone_paper = standalone_lane(
            holdout25,
            bundle.cash_factors[holdout_start:],
            passive25[holdout_start:],
            active_fraction=active_fraction,
            candidate_factors_50bps=holdout50,
            paper=True,
        )
        diversifier = _diversifier_lane(
            holdout25,
            holdout50,
            bundle.cash_factors[holdout_start:],
            incumbent_holdout,
        )
        holdout_stats = summarize(holdout25)
        development_returns.append(development)
        development_segments.append(
            [annualized_sharpe(segment) for segment in _segments(development)]
        )
        holdout_by_cost.append(
            {cost: factors[holdout_start:] for cost, factors in by_cost.items()}
        )
        weights_by_candidate.append(weights)
        records.append(
            {
                "candidate_id": candidate.candidate_id,
                "strategy_fingerprint": candidate.strategy_fingerprint,
                "status": "complete",
                "family": candidate.policy.family,
                "development_sharpe_excess_25bps": round(
                    annualized_sharpe(development), 6
                ),
                "development_max_drawdown_25bps": round(
                    development_stats.max_dd_pct, 6
                ),
                "holdout_cagr_25bps": round(holdout_stats.cagr_pct, 6),
                "holdout_max_drawdown_25bps": round(holdout_stats.max_dd_pct, 6),
                "holdout_psr_25bps": standalone_live["metrics"]["psr_vs_cash"],
                "holdout_cash_excess_annual_return_50bps": standalone_live["metrics"]
                ["annual_cash_excess_50bps"],
                "holdout_energy_buyhold_sharpe_improvement": standalone_live["metrics"]
                ["sharpe_improvement"],
                "holdout_active_fraction": round(active_fraction, 6),
                "posthoc_standalone_live_passed": standalone_live["passed"],
                "posthoc_standalone_paper_passed": standalone_paper["passed"],
                "posthoc_legacy_diversifier_passed": diversifier["passed"],
                "turnover": round(turnover, 6),
                "segment_sharpes": [
                    round(value, 6) for value in development_segments[-1]
                ],
            }
        )

    winner_index = _development_winner_index(records)
    winner = candidates[winner_index]
    winner25 = holdout_by_cost[winner_index][25]
    winner50 = holdout_by_cost[winner_index][50]
    winner_weights = weights_by_candidate[winner_index][holdout_start:]
    active_fraction = sum(weight > 0 for weight in winner_weights) / len(winner_weights)
    standalone_live = standalone_lane(
        winner25,
        bundle.cash_factors[holdout_start:],
        passive25[holdout_start:],
        active_fraction=active_fraction,
        candidate_factors_50bps=winner50,
        paper=False,
    )
    standalone_paper = standalone_lane(
        winner25,
        bundle.cash_factors[holdout_start:],
        passive25[holdout_start:],
        active_fraction=active_fraction,
        candidate_factors_50bps=winner50,
        paper=True,
    )
    diversifier = _diversifier_lane(
        winner25,
        winner50,
        bundle.cash_factors[holdout_start:],
        incumbent_holdout,
    )

    prior = _prior_records(prior_factory_payload)
    audit_records = prior + records
    identities = [
        str(record.get("strategy_fingerprint") or record.get("candidate_id"))
        for record in audit_records
    ]
    unique_audit = len(set(identities))
    calibration_passed = _calibration_valid(calibration_evidence, code_commit=code_commit)
    full_controls_passed = _full_controls_valid(full_gate_controls, code_commit=code_commit)
    objective_calibration = calibrate_standalone_family(
        holdout_months,
        repetitions=calibration_repetitions,
    )
    controls_passed = full_controls_passed and objective_calibration["passable"]
    common_gates = {
        "gate_calibration": calibration_passed,
        "full_gate_controls": full_controls_passed,
        "standalone_objective_calibration": objective_calibration["passable"],
        "complete_family_trials": len(records) == EXPECTED_CANDIDATES,
        "prior_audit_complete": len(prior) == EXPECTED_PRIOR_TRIALS,
        "global_audit_trials": len(audit_records) == EXPECTED_GLOBAL_AUDIT_TRIALS,
        "unique_audit_fingerprints": unique_audit == EXPECTED_GLOBAL_AUDIT_TRIALS,
        "energy_cross_market_data_complete": bundle.quality.get("complete") is True,
        "development_months": DEVELOPMENT_MONTHS == 120,
        "embargo_months": EMBARGO_MONTHS == 1,
        "holdout_months": holdout_months >= MIN_HOLDOUT_MONTHS,
        "ridge_chronology": all(
            row["latest_training_target_index"] is None
            or int(row["latest_training_target_index"]) < int(row["prediction_index"])
            for values in ridge_chronology.values()
            for row in values
        ),
    }
    live_passed = all(common_gates.values()) and standalone_live["passed"]
    paper_passed = all(common_gates.values()) and standalone_paper["passed"]
    verdict = FACTORY_EDGE if live_passed else PAPER_CHALLENGER if paper_passed else NO_FACTORY_EDGE

    effective_trials = effective_independent_trials(development_returns)
    trial_sharpes = [float(row["development_sharpe_excess_25bps"]) for row in records]
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index],
        trial_sharpes,
        effective_trial_count=effective_trials,
    )
    pbo = probability_of_backtest_overfitting(development_segments)
    best_holdout = max(
        records,
        key=lambda record: (
            float(record["holdout_psr_25bps"] or -1),
            float(record["holdout_cash_excess_annual_return_50bps"]),
        ),
    )
    posthoc_live = [
        str(record["candidate_id"])
        for record in records
        if record["posthoc_standalone_live_passed"]
    ]
    posthoc_paper = [
        str(record["candidate_id"])
        for record in records
        if record["posthoc_standalone_paper_passed"]
    ]
    feature = bundle.features[winner.policy.feature_horizon][-1]
    latest_prediction = ridge_predictions[winner.policy.feature_horizon][-1]
    latest_weight = energy_target_weight(
        winner.policy,
        feature,
        ridge_prediction=latest_prediction,
    )
    target_weights = {
        INTENDED_LIVE_SYMBOL: str(latest_weight),
        "USD": str(Decimal("1") - latest_weight),
    }
    split = {
        "development": [bundle.factor_months[0], bundle.factor_months[DEVELOPMENT_MONTHS - 1]],
        "embargo": bundle.factor_months[DEVELOPMENT_MONTHS],
        "holdout": [bundle.factor_months[holdout_start], bundle.factor_months[-1]],
    }
    data_fingerprint = _fingerprint(bundle.quality)
    split_fingerprint = _fingerprint(split)
    model_fingerprint = _fingerprint(
        {
            "model": "StandardScaler+Ridge",
            "alpha": RIDGE_ALPHA,
            "min_train": RIDGE_MIN_TRAIN,
            "feature_names": [
                "wti_return",
                "gasoline_return",
                "heating_return",
                "natural_gas_return",
                "crack_zscore",
            ],
            "chronology": "training target index < prediction index",
        }
    )
    batch_id = "energy-cross-market-" + _fingerprint(
        {
            "code": code_commit,
            "data": data_fingerprint,
            "controls": full_gate_controls.get("control_fingerprint"),
            "split": split,
            "model": model_fingerprint,
            "candidates": [candidate.candidate_id for candidate in candidates],
        }
    )[7:19]
    criterion_diagnosis = (
        "OBJECTIVE_OR_CONTROLS_INVALID"
        if not calibration_passed or not controls_passed
        else "OBJECTIVE_GATE_PASSABLE_CANDIDATE_CONFIRMED"
        if live_passed
        else "OBJECTIVE_GATE_PASSABLE_CANDIDATE_UNCONFIRMED"
    )
    failed_live = [
        gate_id
        for gate_id, result in standalone_live["gates"].items()
        if not result["passed"]
    ]
    common_gate_rows = [
        {
            "gate_id": gate_id,
            "passed": passed,
            "actual": str(passed),
            "required": "True",
            "stage": "control" if "calibration" in gate_id or "controls" in gate_id else "audit",
            "blocking": True,
        }
        for gate_id, passed in common_gates.items()
    ]
    live_gate_rows = [
        {
            "gate_id": gate_id,
            "passed": result["passed"],
            "actual": str(result["actual"]),
            "required": result["required"],
            "stage": "standalone_holdout",
            "blocking": True,
        }
        for gate_id, result in standalone_live["gates"].items()
    ]
    decision = {
        "verdict": verdict,
        "criterion_diagnosis": criterion_diagnosis,
        "diagnostic_classification": (
            "LIVE_IMPLEMENTATION_REQUIRED"
            if live_passed
            else "PAPER_READY"
            if paper_passed
            else "NO_CONFIRMED_STANDALONE_EDGE"
        ),
        "objective": OBJECTIVE,
        "provisional_best_candidate_id": winner.candidate_id,
        "confirmed_candidate_id": winner.candidate_id if live_passed else None,
        "selected_candidate_id": None,
        "paper_candidate_id": winner.candidate_id if paper_passed and not live_passed else None,
        "selected_strategy_fingerprint": None,
        "research_canary_eligible": False,
        "paper_forward_eligible": paper_passed and not live_passed,
        "live_implementation_available": LIVE_IMPLEMENTATION_AVAILABLE,
        "live_whitelist_authorized": LIVE_WHITELIST_AUTHORIZED,
        "selected_deploy_config": None,
        "gates": common_gate_rows + live_gate_rows,
        "paper_gates": standalone_paper["gates"],
        "legacy_diversifier_diagnostic": diversifier,
        "failed_standalone_live_gates": failed_live,
        "dsr": None if dsr is None else str(dsr),
        "pbo": None if pbo is None else str(pbo),
        "psr": standalone_live["metrics"]["psr_vs_cash"],
        "next_strategy_family": (
            "implement_xle_energy_cross_market"
            if live_passed
            else "forward_paper_energy_cross_market"
            if paper_passed
            else "independent_options_variance_risk_premium"
        ),
        "search_space_exhausted": verdict == NO_FACTORY_EDGE,
    }
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
        "energy_cross_market_data": bundle.quality,
        "energy_cross_market_data_fingerprint": data_fingerprint,
        "usda_crop_data_fingerprint": prior_factory_payload.get(
            "usda_crop_data_fingerprint"
        ),
        "model_fingerprint": model_fingerprint,
        "model_chronology": {
            "passed": common_gates["ridge_chronology"],
            "minimum_training_labels": RIDGE_MIN_TRAIN,
            "first_prediction_index": RIDGE_MIN_TRAIN,
            "latest_rows": {
                str(horizon): ridge_chronology[horizon][-1] for horizon in (6, 12)
            },
        },
        "full_gate_controls": full_gate_controls,
        "objective_gate_calibration": objective_calibration,
        "gate_power": {
            "preregistered_family_calibration": calibration_evidence.get(
                "family_calibrations", {}
            ).get("16", {}),
            "actual_holdout": _actual_holdout_power(holdout_months),
        },
        "split_fingerprint": split_fingerprint,
        "development_selection": {
            "window": split["development"],
            "months": DEVELOPMENT_MONTHS,
            "selected_candidate_id": winner.candidate_id,
            "selection_metric": "development excess Sharpe after 25bps",
        },
        "selection_sanity": {
            "development_winner_matches_best_holdout": (
                winner.candidate_id == best_holdout["candidate_id"]
            ),
            "best_holdout_candidate_id": best_holdout["candidate_id"],
            "best_holdout_psr_25bps": best_holdout["holdout_psr_25bps"],
            "best_holdout_cash_excess_annual_return_50bps": best_holdout[
                "holdout_cash_excess_annual_return_50bps"
            ],
            "posthoc_standalone_live_candidate_ids": posthoc_live,
            "posthoc_standalone_paper_candidate_ids": posthoc_paper,
            "promotion_allowed": False,
            "reason": "holdout-ranked candidates are descriptive only after inspection",
        },
        "holdout_confirmation": {
            "window": split["holdout"],
            "embargo_months": EMBARGO_MONTHS,
            "months": holdout_months,
            **standalone_live["metrics"],
        },
        "standalone_live_lane": standalone_live,
        "standalone_paper_lane": standalone_paper,
        "legacy_diversifier_lane": diversifier,
        "trial_records": records,
        "audit_records": audit_records,
        "development_returns": development_returns,
        "decision": decision,
        "research_candidate": winner.as_dict() if live_passed else None,
        "paper_candidate": winner.as_dict() if paper_passed and not live_passed else None,
        "research_live_parity": {
            "passed": False,
            "intended_symbol": INTENDED_LIVE_SYMBOL,
            "reason": (
                "XLE policy implementation, historical parity, whitelist authorization, "
                "deploy config, hardened canary, and exact fingerprint identity are missing"
            ),
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "target_weights": target_weights,
            "target_weights_digest": _fingerprint(target_weights),
        },
        "criterion_audit": {
            "standalone_question": "does the timed energy sleeve beat cash and passive energy?",
            "diversifier_question": (
                "does a 20% sleeve improve the incumbent SPY/IEF/GLD portfolio?"
            ),
            "threshold_change": False,
            "prior_candidate_reclassification": False,
        },
        "safety": [
            "research evidence only",
            "no broker API",
            "no orders",
            "no capital, cap, arming, whitelist, constitution, or kernel change",
        ],
    }


def render_energy_cross_market_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    holdout = payload["holdout_confirmation"]
    sanity = payload["selection_sanity"]
    legacy = payload["legacy_diversifier_lane"]
    return "\n".join(
        [
            "# 에너지 교차시장 독립 전략 공장",
            "",
            f"- 목적 관문 진단: `{decision['criterion_diagnosis']}`",
            f"- 전략 판정: `{decision['verdict']}`",
            f"- 개발 선택 후보: `{decision['provisional_best_candidate_id']}`",
            f"- 감사 시도: {payload['global_audit_trial_count']}회 (현재 가족 16회)",
            f"- 홀드아웃: {holdout['months']}개월, 현금 초과 PSR {holdout['psr_vs_cash']}",
            f"- 50bp 후 연 현금 초과수익: {holdout['annual_cash_excess_50bps']:.4%}",
            f"- 에너지 단순보유 대비 샤프 변화: {holdout['sharpe_improvement']:+.4f}",
            f"- 단독 수익 관문 통과: {payload['standalone_live_lane']['passed']}",
            f"- 기존 분산 관문 통과: {legacy['passed']}",
            f"- 사후 최상 후보: `{sanity['best_holdout_candidate_id']}` "
            f"(PSR {sanity['best_holdout_psr_25bps']}, 승격 불가)",
            f"- 사후 단독 수익 관문 통과 후보 수: "
            f"{len(sanity['posthoc_standalone_live_candidate_ids'])}",
            f"- 실패 단독 관문: {', '.join(decision['failed_standalone_live_gates']) or '없음'}",
            "- XLE 실거래 구현·허용목록 정합: False",
            "- 주문/자본/허용목록 변경: 0",
        ]
    )


__all__ = [
    "EIA_SERIES",
    "FRENCH_URL",
    "EnergyCrossMarketBundle",
    "EnergyCrossMarketPolicy",
    "EnergyFeatureSnapshot",
    "EnergyMarketObservation",
    "calibrate_standalone_family",
    "energy_target_weight",
    "expanding_ridge_predictions",
    "generate_energy_cross_market_candidates",
    "load_energy_cross_market_bundle",
    "parse_eia_monthly_series",
    "parse_french_oil_returns",
    "render_energy_cross_market_markdown",
    "run_energy_cross_market_factory",
    "standalone_lane",
    "validate_energy_cross_market_bundle",
]
