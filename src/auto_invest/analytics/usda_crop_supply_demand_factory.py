"""Spec 162: point-in-time USDA crop supply-demand strategy factory."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from statistics import NormalDist
from typing import Any
from urllib.parse import urljoin

import xlrd

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
    CALIBRATED,
    GATE_VERSION,
    HOLDOUT_PSR_MIN,
    PAPER_PSR_MIN,
    PBO_DIAGNOSTIC_MAX,
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
EXPECTED_PRIOR_TRIALS = 704
EXPECTED_GLOBAL_AUDIT_TRIALS = 720
DEVELOPMENT_MONTHS = 60
EMBARGO_MONTHS = 1
MIN_HOLDOUT_MONTHS = 120
MIN_RELEASES = 190
FACTORY_EDGE = "FACTORY_EDGE"
PAPER_CHALLENGER = "PAPER_CHALLENGER"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
OBJECTIVE = "usda_crop_scarcity_inflation_diversifier"
ESMIS_BASE_URL = "https://esmis.nal.usda.gov"
ESMIS_INDEX_URL = (
    ESMIS_BASE_URL
    + "/publication/world-agricultural-supply-and-demand-estimates"
)
FIRST_XLS_RELEASE = date(2010, 7, 1)
FAMILIES = (
    "corn_tightening",
    "wheat_tightening",
    "soybean_tightening",
    "synchronized_tightening",
)
EXECUTION_SYMBOLS = ("GLD", "IEF")
LIVE_IMPLEMENTATION_AVAILABLE = False
LIVE_WHITELIST_AUTHORIZED = True


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _content_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def _calendar_months(start: date, end: date) -> list[date]:
    output: list[date] = []
    current = _month_start(start)
    final = _month_start(end)
    while current <= final:
        output.append(current)
        current = _next_month(current)
    return output


@dataclass(frozen=True)
class WasdeWorkbookRef:
    release_date: date
    url: str


@dataclass(frozen=True)
class WasdeCropObservation:
    release_date: date
    crop: str
    market_year: str
    ending_stocks: float
    total_use: float
    stocks_to_use: float
    source_url: str
    content_digest: str


@dataclass(frozen=True)
class CropRevisionSnapshot:
    release_date: date
    observations: dict[str, WasdeCropObservation]
    revisions: dict[int, dict[str, float]]


@dataclass(frozen=True)
class CropSupplyDemandPolicy:
    family: str
    revision_horizon: int
    max_gold_weight: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "revision_horizon": self.revision_horizon,
            "max_gold_weight": str(self.max_gold_weight),
        }


@dataclass(frozen=True)
class CropSupplyDemandCandidate:
    candidate_id: str
    trial_index: int
    policy: CropSupplyDemandPolicy
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.policy.family,
            "policy": self.policy.as_dict(),
            "strategy_fingerprint": self.strategy_fingerprint,
            "execution_symbols": list(EXECUTION_SYMBOLS),
            "live_expressible": LIVE_IMPLEMENTATION_AVAILABLE,
            "live_blocker": (
                None
                if LIVE_IMPLEMENTATION_AVAILABLE
                else "the live engine does not yet execute monthly USDA revision policies"
            ),
            "basis_risk": "crop-specific scarcity may not predict broad gold inflation exposure",
        }


@dataclass(frozen=True)
class CropSupplyDemandBundle:
    dates: tuple[str, ...]
    cash_rates: tuple[float, ...]
    revisions: dict[int, dict[str, tuple[float, ...]]]
    latest_revisions: dict[int, dict[str, float]]
    latest_release_date: date
    quality: dict[str, Any]


class _WasdeIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_row = False
        self._row_date: date | None = None
        self._row_urls: list[str] = []
        self.rows: list[tuple[date, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tr":
            self._inside_row = True
            self._row_date = None
            self._row_urls = []
        elif self._inside_row and tag == "time" and values.get("datetime"):
            raw = str(values["datetime"])
            try:
                self._row_date = date.fromisoformat(raw[:10])
            except ValueError:
                self._row_date = None
        elif self._inside_row and tag == "a" and values.get("href"):
            href = str(values["href"])
            if href.lower().endswith(".xls"):
                self._row_urls.append(urljoin(ESMIS_BASE_URL, href))

    def handle_endtag(self, tag: str) -> None:
        if tag != "tr" or not self._inside_row:
            return
        if self._row_date is not None and self._row_urls:
            self.rows.append((self._row_date, list(dict.fromkeys(self._row_urls))))
        self._inside_row = False


def parse_wasde_index_pages(pages: list[str]) -> tuple[WasdeWorkbookRef, ...]:
    refs: dict[date, WasdeWorkbookRef] = {}
    for page in pages:
        parser = _WasdeIndexParser()
        parser.feed(page)
        for release_date, urls in parser.rows:
            if release_date < FIRST_XLS_RELEASE:
                continue
            if len(urls) != 1:
                raise ValueError("WASDE release must have exactly one XLS workbook")
            candidate = WasdeWorkbookRef(release_date, urls[0])
            prior = refs.get(release_date)
            if prior is not None and prior != candidate:
                raise ValueError("WASDE release date has conflicting XLS workbooks")
            refs[release_date] = candidate
    ordered = tuple(refs[key] for key in sorted(refs))
    if len(ordered) < MIN_RELEASES:
        raise ValueError("WASDE archive does not provide the preregistered release depth")
    if ordered[0].release_date > date(2010, 7, 31):
        raise ValueError("WASDE archive starts after the preregistered first release")
    return ordered


def _normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _rightmost_numeric(sheet: xlrd.sheet.Sheet, row: int) -> tuple[int, float]:
    for column in range(sheet.ncols - 1, -1, -1):
        value = sheet.cell_value(row, column)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            if math.isfinite(number) and number > 0:
                return column, number
    raise ValueError("WASDE projected row has no positive numeric value")


def _find_sheet_and_row(
    workbook: xlrd.book.Book,
    *,
    title: str,
    section: str | None,
) -> tuple[xlrd.sheet.Sheet, int]:
    for sheet in workbook.sheets():
        title_rows = [
            row
            for row in range(sheet.nrows)
            if any(
                title in _normalized(sheet.cell_value(row, column))
                for column in range(sheet.ncols)
            )
        ]
        if not title_rows:
            continue
        if section is None:
            return sheet, title_rows[0]
        for row in range(title_rows[0], sheet.nrows):
            if any(
                _normalized(sheet.cell_value(row, column)) == section
                for column in range(sheet.ncols)
            ):
                return sheet, row
    raise ValueError(f"WASDE workbook is missing table: {title}")


def _find_metric_row(sheet: xlrd.sheet.Sheet, start: int, label: str) -> int:
    for row in range(start, sheet.nrows):
        if any(
            _normalized(sheet.cell_value(row, column)).lstrip().endswith(label)
            for column in range(sheet.ncols)
        ):
            return row
    raise ValueError(f"WASDE table is missing metric: {label}")


def _market_year_for_column(
    sheet: xlrd.sheet.Sheet,
    *,
    start: int,
    metric_row: int,
    column: int,
) -> str:
    pattern = re.compile(r"\b(\d{4}/\d{2})\b")
    for row in range(metric_row - 1, max(start - 1, -1), -1):
        match = pattern.search(_normalized(sheet.cell_value(row, column)))
        if match:
            return match.group(1)
    raise ValueError("WASDE projected market year does not align with metric column")


def _parse_crop_table(
    workbook: xlrd.book.Book,
    *,
    crop: str,
) -> tuple[str, float, float]:
    if crop == "corn":
        title = "U.S. Feed Grain and Corn Supply and Use"
        section = "CORN"
    elif crop == "wheat":
        title = "U.S. Wheat Supply and Use"
        section = None
    elif crop == "soybeans":
        title = "U.S. Soybeans and Products Supply and Use"
        section = "SOYBEANS"
    else:
        raise ValueError(f"unsupported WASDE crop: {crop}")
    sheet, start = _find_sheet_and_row(workbook, title=title, section=section)
    use_row = _find_metric_row(sheet, start, "Use, Total")
    stocks_row = _find_metric_row(sheet, start, "Ending Stocks")
    use_column, total_use = _rightmost_numeric(sheet, use_row)
    stocks_column, ending_stocks = _rightmost_numeric(sheet, stocks_row)
    if use_column != stocks_column:
        raise ValueError("WASDE ending stocks and total use projection columns differ")
    market_year = _market_year_for_column(
        sheet,
        start=start,
        metric_row=min(use_row, stocks_row),
        column=use_column,
    )
    return market_year, ending_stocks, total_use


def parse_wasde_workbook(
    raw: bytes,
    *,
    ref: WasdeWorkbookRef,
) -> dict[str, WasdeCropObservation]:
    try:
        workbook = xlrd.open_workbook(file_contents=raw)
    except xlrd.XLRDError as exc:
        raise ValueError("WASDE workbook schema mismatch") from exc
    digest = _content_digest(raw)
    output: dict[str, WasdeCropObservation] = {}
    for crop in ("corn", "wheat", "soybeans"):
        market_year, ending_stocks, total_use = _parse_crop_table(workbook, crop=crop)
        output[crop] = WasdeCropObservation(
            release_date=ref.release_date,
            crop=crop,
            market_year=market_year,
            ending_stocks=ending_stocks,
            total_use=total_use,
            stocks_to_use=ending_stocks / total_use,
            source_url=ref.url,
            content_digest=digest,
        )
    return output


def build_revision_snapshots(
    releases: list[dict[str, WasdeCropObservation]],
) -> tuple[CropRevisionSnapshot, ...]:
    if len(releases) < MIN_RELEASES:
        raise ValueError("WASDE releases are incomplete")
    ordered = sorted(releases, key=lambda item: item["corn"].release_date)
    dates = [item["corn"].release_date for item in ordered]
    if len(set(dates)) != len(dates):
        raise ValueError("WASDE release date is duplicated")
    output: list[CropRevisionSnapshot] = []
    for index, observations in enumerate(ordered):
        if set(observations) != {"corn", "wheat", "soybeans"}:
            raise ValueError("WASDE release crop coverage is incomplete")
        release_date = observations["corn"].release_date
        if any(value.release_date != release_date for value in observations.values()):
            raise ValueError("WASDE release crop dates do not align")
        revisions: dict[int, dict[str, float]] = {}
        for horizon in (1, 3):
            values: dict[str, float] = {}
            for crop, current in observations.items():
                if index < horizon:
                    values[crop] = 0.0
                    continue
                prior = ordered[index - horizon][crop]
                values[crop] = (
                    prior.stocks_to_use - current.stocks_to_use
                    if prior.market_year == current.market_year
                    else 0.0
                )
            revisions[horizon] = values
        output.append(CropRevisionSnapshot(release_date, observations, revisions))
    return tuple(output)


def load_crop_supply_demand_bundle(
    refs: tuple[WasdeWorkbookRef, ...],
    raw_by_url: dict[str, bytes],
    cash_points: list[SeriesPoint],
    *,
    current_date: date,
) -> CropSupplyDemandBundle:
    expected_urls = {ref.url for ref in refs}
    if set(raw_by_url) != expected_urls:
        raise ValueError("WASDE workbook bundle is incomplete")
    releases = [parse_wasde_workbook(raw_by_url[ref.url], ref=ref) for ref in refs]
    snapshots = build_revision_snapshots(releases)
    latest_complete_month = _next_month(_month_start(current_date)) - timedelta(days=1)
    if latest_complete_month >= current_date:
        latest_complete_month = _month_start(current_date) - timedelta(days=1)
    months = _calendar_months(snapshots[0].release_date, latest_complete_month)
    dates = [month.isoformat() for month in months]
    release_by_month = {_month_start(item.release_date): item for item in snapshots}
    active = snapshots[0]
    aligned: list[CropRevisionSnapshot] = []
    missing_release_months: list[str] = []
    for month in months:
        released = release_by_month.get(month)
        if released is not None:
            active = released
        else:
            missing_release_months.append(month.strftime("%Y-%m"))
        aligned.append(active)
    cash_rates = [_latest_rate_before(cash_points, month) for month in months]
    observed_cash = [point for point in cash_points if point.value is not None]
    latest_release = snapshots[-1]
    latest_age = (current_date - latest_release.release_date).days
    cash_age = (
        current_date - date.fromisoformat(observed_cash[-1].date)
    ).days if observed_cash else 10_000
    complete = bool(
        len(snapshots) >= MIN_RELEASES
        and len(months) - 1 >= DEVELOPMENT_MONTHS + EMBARGO_MONTHS + MIN_HOLDOUT_MONTHS
        and all(value is not None for value in cash_rates)
        and 0 <= latest_age <= 45
        and 0 <= cash_age <= 7
    )
    sources = [
        {
            "release_date": item.release_date.isoformat(),
            "url": item.observations["corn"].source_url,
            "content_digest": item.observations["corn"].content_digest,
        }
        for item in snapshots
    ]
    quality = {
        "complete": complete,
        "provider": "USDA Economics, Statistics, and Market Information System",
        "index_url": ESMIS_INDEX_URL,
        "release_count": len(snapshots),
        "first_release_date": snapshots[0].release_date.isoformat(),
        "last_release_date": latest_release.release_date.isoformat(),
        "latest_release_age_days": latest_age,
        "cash_age_days": cash_age,
        "months": len(months),
        "missing_release_months": missing_release_months,
        "release_sources": sources,
        "point_in_time": True,
        "revision_policy": "each archived workbook is used exactly as released",
        "basis_risk": "crop scarcity may not predict broad gold inflation exposure",
    }

    def series(horizon: int, crop: str) -> tuple[float, ...]:
        return tuple(item.revisions[horizon][crop] for item in aligned)

    return CropSupplyDemandBundle(
        dates=tuple(dates),
        cash_rates=tuple(float(value) for value in cash_rates if value is not None),
        revisions={
            horizon: {
                crop: series(horizon, crop) for crop in ("corn", "wheat", "soybeans")
            }
            for horizon in (1, 3)
        },
        latest_revisions=latest_release.revisions,
        latest_release_date=latest_release.release_date,
        quality=quality,
    )


def generate_crop_supply_demand_candidates() -> tuple[CropSupplyDemandCandidate, ...]:
    output: list[CropSupplyDemandCandidate] = []
    for family in FAMILIES:
        for horizon in (1, 3):
            for maximum in (Decimal("0.5"), Decimal("1.0")):
                policy = CropSupplyDemandPolicy(family, horizon, maximum)
                digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": policy.as_dict()})
                output.append(
                    CropSupplyDemandCandidate(
                        candidate_id=f"usda-crop-{family}-{digest[7:19]}",
                        trial_index=len(output) + 1,
                        policy=policy,
                        strategy_fingerprint=_fingerprint(
                            {
                                "signals": "USDA_WASDE_same_marketing_year_stocks_to_use_revision",
                                "execution_symbols": list(EXECUTION_SYMBOLS),
                                "decision_timing": (
                                    "release_month_signal_applies_next_monthly_factor"
                                ),
                                "policy": policy.as_dict(),
                            }
                        ),
                    )
                )
    if len(output) != EXPECTED_CANDIDATES:
        raise RuntimeError("USDA crop candidate count contract violated")
    if len({item.candidate_id for item in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("USDA crop candidate ids are not unique")
    if len({item.strategy_fingerprint for item in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("USDA crop strategy fingerprints are not unique")
    return tuple(output)


def crop_target_gold_weight(
    policy: CropSupplyDemandPolicy,
    revisions: dict[str, float],
) -> Decimal:
    if policy.family == "corn_tightening":
        active = revisions["corn"] > 0
    elif policy.family == "wheat_tightening":
        active = revisions["wheat"] > 0
    elif policy.family == "soybean_tightening":
        active = revisions["soybeans"] > 0
    elif policy.family == "synchronized_tightening":
        active = all(revisions[crop] > 0 for crop in ("corn", "wheat", "soybeans"))
    else:
        raise ValueError(f"unknown USDA crop family: {policy.family}")
    return policy.max_gold_weight if active else Decimal("0")


def _candidate_factors(
    candidate: CropSupplyDemandCandidate,
    bundle: CropSupplyDemandBundle,
    gold_factors: list[float],
    bond_factors: list[float],
    *,
    cost_bps: int,
) -> tuple[list[float], list[Decimal], float, list[float]]:
    if len(gold_factors) != len(bundle.dates) - 1 or len(bond_factors) != len(gold_factors):
        raise ValueError("USDA crop asset factors do not align with release months")
    horizon = candidate.policy.revision_horizon
    output: list[float] = []
    weights: list[Decimal] = []
    cash_output: list[float] = []
    previous = Decimal("0")
    turnover_total = Decimal("0")
    for index, (gold_factor, bond_factor) in enumerate(
        zip(gold_factors, bond_factors, strict=True)
    ):
        revisions = {
            crop: bundle.revisions[horizon][crop][index]
            for crop in ("corn", "wheat", "soybeans")
        }
        gold_weight = crop_target_gold_weight(candidate.policy, revisions)
        turnover = abs(gold_weight - previous)
        gross = float(gold_weight) * gold_factor + (1.0 - float(gold_weight)) * bond_factor
        net = gross * (1.0 - float(turnover) * cost_bps / 10_000.0)
        if net <= 0:
            raise ValueError("USDA crop cost model produced a non-positive factor")
        output.append(net)
        weights.append(gold_weight)
        cash_output.append(1.0 + bundle.cash_rates[index] / 1200.0)
        turnover_total += turnover
        previous = gold_weight
    return output, weights, float(turnover_total), cash_output


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


def _annualized_excess(candidate: list[float], cash: list[float]) -> float:
    relative = math.prod(left / right for left, right in zip(candidate, cash, strict=True))
    return relative ** (12.0 / len(candidate)) - 1.0


def _full_controls_valid(payload: dict[str, Any], *, code_commit: str) -> bool:
    return bool(
        payload.get("verdict") == FULL_GATE_CONTROLS_VALID
        and payload.get("promotion_control_passed") is True
        and payload.get("code_commit") == code_commit
        and str(payload.get("control_fingerprint", "")).startswith("sha256:")
    )


def actual_holdout_psr_power(holdout_months: int) -> dict[str, Any]:
    if holdout_months < 2:
        raise ValueError("holdout power requires at least two months")
    normal = NormalDist()
    critical = normal.inv_cdf(HOLDOUT_PSR_MIN)
    curve: dict[str, float] = {}
    for annual_sharpe in (0.2, 0.4, 0.6, 0.8, 1.0, 1.5):
        noncentrality = annual_sharpe * math.sqrt(holdout_months / 12.0)
        curve[f"{annual_sharpe:.1f}"] = round(normal.cdf(noncentrality - critical), 6)
    minimum_80 = critical + normal.inv_cdf(0.80)
    return {
        "method": "normal approximation for one-sided PSR threshold",
        "holdout_months": holdout_months,
        "live_threshold": HOLDOUT_PSR_MIN,
        "null_false_positive_approx": round(1.0 - HOLDOUT_PSR_MIN, 6),
        "detection_by_true_annual_sharpe": curve,
        "minimum_80pct_detectable_annual_sharpe_approx": round(
            minimum_80 / math.sqrt(holdout_months / 12.0), 6
        ),
        "limitation": "full economic gates and development winner selection can reduce power",
    }


def run_usda_crop_supply_demand_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    bundle: CropSupplyDemandBundle,
    *,
    prior_factory_payload: dict[str, Any],
    calibration_evidence: dict[str, Any],
    full_gate_controls: dict[str, Any],
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    if len(rows) != len(bundle.dates) or len(gold_levels) != len(bundle.dates):
        raise ValueError("incumbent and USDA crop source months must align")
    if [row.date[:7] for row in rows] != [value[:7] for value in bundle.dates]:
        raise ValueError("incumbent dates do not align with USDA crop months")
    candidates = generate_crop_supply_demand_candidates()
    holdout_start = DEVELOPMENT_MONTHS + EMBARGO_MONTHS
    factor_count = len(bundle.dates) - 1
    if factor_count - holdout_start < MIN_HOLDOUT_MONTHS:
        raise ValueError("USDA crop holdout must contain at least 120 months")

    market_factors = market_total_return_factors(rows)
    bond_factors = bond_total_return_factors(rows)
    gold_factors = gold_total_return_factors(gold_levels)
    incumbent_all = [
        sum(values) / 3.0
        for values in zip(market_factors, bond_factors, gold_factors, strict=True)
    ]
    incumbent_holdout = incumbent_all[holdout_start:]
    incumbent_stats = summarize(incumbent_holdout)

    records: list[dict[str, Any]] = []
    development_returns: list[list[float]] = []
    development_segments: list[list[float]] = []
    holdout_by_cost: list[dict[int, list[float]]] = []
    cash_all: list[float] = []
    for candidate in candidates:
        full_by_cost: dict[int, list[float]] = {}
        candidate_weights: list[Decimal] = []
        turnover = 0.0
        for cost in (10, 25, 50):
            factors, weights, candidate_turnover, cash = _candidate_factors(
                candidate,
                bundle,
                gold_factors,
                bond_factors,
                cost_bps=cost,
            )
            full_by_cost[cost] = factors
            cash_all = cash
            if cost == 25:
                candidate_weights, turnover = weights, candidate_turnover
        development = [
            factor / cash - 1.0
            for factor, cash in zip(
                full_by_cost[25][:DEVELOPMENT_MONTHS],
                cash_all[:DEVELOPMENT_MONTHS],
                strict=True,
            )
        ]
        holdout = full_by_cost[25][holdout_start:]
        holdout_excess = [
            factor / cash - 1.0
            for factor, cash in zip(holdout, cash_all[holdout_start:], strict=True)
        ]
        segments = [annualized_sharpe(segment) for segment in _segments(development)]
        development_stats = summarize([1.0 + value for value in development])
        holdout_stats = summarize(holdout)
        development_returns.append(development)
        development_segments.append(segments)
        holdout_by_cost.append(
            {cost: values[holdout_start:] for cost, values in full_by_cost.items()}
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
                "holdout_excess_sharpe_25bps": round(annualized_sharpe(holdout_excess), 6),
                "holdout_cagr_25bps": round(holdout_stats.cagr_pct, 6),
                "holdout_max_drawdown_25bps": round(holdout_stats.max_dd_pct, 6),
                "holdout_excess_annual_return_50bps": round(
                    _annualized_excess(
                        full_by_cost[50][holdout_start:], cash_all[holdout_start:]
                    ),
                    8,
                ),
                "turnover": round(turnover, 6),
                "gold_active_months": sum(weight > 0 for weight in candidate_weights),
                "segment_sharpes": [round(value, 6) for value in segments],
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
        development_returns[winner_index],
        trial_sharpes,
        effective_trial_count=effective_trials,
    )
    pbo = probability_of_backtest_overfitting(development_segments)
    winner_holdout = holdout_by_cost[winner_index][25]
    winner_excess = [
        factor / cash - 1.0
        for factor, cash in zip(winner_holdout, cash_all[holdout_start:], strict=True)
    ]
    holdout_psr = probabilistic_sharpe(winner_excess)
    blend = [
        0.8 * incumbent + 0.2 * candidate
        for incumbent, candidate in zip(incumbent_holdout, winner_holdout, strict=True)
    ]
    blend_stats = summarize(blend)
    incumbent_correlation = correlation(incumbent_holdout, winner_holdout)
    if incumbent_correlation is None:
        incumbent_correlation = 1.0
    blend_improvement = blend_stats.sharpe - incumbent_stats.sharpe
    excess_50 = float(winner_record["holdout_excess_annual_return_50bps"])

    prior = _prior_records(prior_factory_payload)
    audit_records = prior + records
    identities = [
        str(row.get("strategy_fingerprint") or row.get("candidate_id"))
        for row in audit_records
    ]
    unique_audit = len(set(identities))
    calibration_passed = _calibration_valid(calibration_evidence, code_commit=code_commit)
    controls_passed = _full_controls_valid(full_gate_controls, code_commit=code_commit)

    latest_revisions = bundle.latest_revisions[winner.policy.revision_horizon]
    latest_gold_weight = crop_target_gold_weight(winner.policy, latest_revisions)
    target_weights = {
        "GLD": str(latest_gold_weight),
        "IEF": str(Decimal("1") - latest_gold_weight),
    }
    target_digest = _fingerprint(target_weights)
    gates: list[dict[str, Any]] = []
    paper_gates: list[dict[str, Any]] = []

    def add_gate(
        gate_id: str,
        passed: bool,
        actual: Any,
        required: Any,
        stage: str,
        *,
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

    def add_paper(gate_id: str, passed: bool, actual: Any, required: Any) -> None:
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
        "calibration",
    )
    add_gate(
        "full_gate_controls",
        controls_passed,
        full_gate_controls.get("verdict"),
        FULL_GATE_CONTROLS_VALID,
        "calibration",
    )
    add_gate("complete_family_trials", len(records) == 16, len(records), 16, "audit")
    add_gate(
        "prior_audit_complete",
        len(prior) == EXPECTED_PRIOR_TRIALS,
        len(prior),
        EXPECTED_PRIOR_TRIALS,
        "audit",
    )
    add_gate(
        "global_audit_trials",
        len(audit_records) == EXPECTED_GLOBAL_AUDIT_TRIALS,
        len(audit_records),
        EXPECTED_GLOBAL_AUDIT_TRIALS,
        "audit",
    )
    add_gate(
        "unique_audit_fingerprints",
        unique_audit == EXPECTED_GLOBAL_AUDIT_TRIALS,
        unique_audit,
        EXPECTED_GLOBAL_AUDIT_TRIALS,
        "audit",
    )
    add_gate(
        "usda_point_in_time_data_complete",
        bundle.quality.get("complete") is True,
        bundle.quality.get("complete"),
        True,
        "data",
    )
    add_gate("development_months", DEVELOPMENT_MONTHS == 60, DEVELOPMENT_MONTHS, 60, "split")
    add_gate("embargo_months", EMBARGO_MONTHS == 1, EMBARGO_MONTHS, 1, "split")
    add_gate("holdout_months", len(winner_holdout) >= 120, len(winner_holdout), 120, "split")
    add_gate(
        "development_dsr_diagnostic",
        dsr is not None and dsr >= Decimal("0.95"),
        dsr,
        0.95,
        "discovery",
        blocking=False,
    )
    add_gate(
        "development_pbo_diagnostic",
        pbo is not None and pbo <= PBO_DIAGNOSTIC_MAX,
        pbo,
        PBO_DIAGNOSTIC_MAX,
        "discovery",
        blocking=False,
    )
    add_gate(
        "holdout_excess_psr",
        holdout_psr is not None and holdout_psr >= Decimal(str(HOLDOUT_PSR_MIN)),
        holdout_psr,
        HOLDOUT_PSR_MIN,
        "holdout",
    )
    add_gate("holdout_excess_50bps_positive", excess_50 > 0, excess_50, "> 0", "economics")
    add_gate(
        "incumbent_correlation",
        incumbent_correlation < 0.80,
        incumbent_correlation,
        "< 0.80",
        "economics",
    )
    add_gate(
        "blend_sharpe_improvement",
        blend_improvement >= 0.05,
        round(blend_improvement, 6),
        ">= 0.05",
        "economics",
    )
    add_gate(
        "blend_drawdown_non_worsening",
        blend_stats.max_dd_pct <= incumbent_stats.max_dd_pct,
        blend_stats.max_dd_pct,
        incumbent_stats.max_dd_pct,
        "economics",
    )
    add_gate(
        "live_implementation_parity",
        LIVE_IMPLEMENTATION_AVAILABLE,
        LIVE_IMPLEMENTATION_AVAILABLE,
        True,
        "parity",
        blocking=False,
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
    add_paper(
        "paper_holdout_psr",
        holdout_psr is not None and holdout_psr >= Decimal(str(PAPER_PSR_MIN)),
        holdout_psr,
        PAPER_PSR_MIN,
    )
    add_paper("paper_excess_50bps_positive", excess_50 > 0, excess_50, "> 0")
    add_paper(
        "paper_incumbent_correlation",
        incumbent_correlation < 0.80,
        incumbent_correlation,
        "< 0.80",
    )
    add_paper(
        "paper_blend_sharpe_non_declining",
        blend_improvement >= 0,
        round(blend_improvement, 6),
        ">= 0",
    )
    add_paper(
        "paper_blend_drawdown_bounded",
        blend_stats.max_dd_pct <= incumbent_stats.max_dd_pct * 1.20,
        blend_stats.max_dd_pct,
        round(incumbent_stats.max_dd_pct * 1.20, 6),
    )
    paper_passed = common_passed and all(gate["passed"] for gate in paper_gates)
    verdict = FACTORY_EDGE if live_passed else PAPER_CHALLENGER if paper_passed else NO_FACTORY_EDGE
    implementation_ready = bool(
        live_passed and LIVE_IMPLEMENTATION_AVAILABLE and LIVE_WHITELIST_AUTHORIZED
    )
    economic_gates_passed = all(
        gate["passed"] for gate in gates if gate["blocking"] and gate["stage"] == "economics"
    )
    criterion_diagnosis = (
        "CRITERIA_OR_CONTROLS_INVALID"
        if not calibration_passed or not controls_passed
        else "PASSABLE_AND_CANDIDATE_CONFIRMED"
        if live_passed
        else "PASSABLE_BUT_CANDIDATE_UNCONFIRMED"
    )
    diagnostic_classification = (
        "LIVE_IMPLEMENTATION_REQUIRED"
        if live_passed and not implementation_ready
        else "PROMOTION_READY"
        if implementation_ready
        else "PAPER_READY"
        if paper_passed
        else "ECONOMICALLY_PROMISING_STATISTICALLY_UNCONFIRMED"
        if common_passed and economic_gates_passed and holdout_psr is not None
        else "NO_CONFIRMED_EDGE"
    )
    split = {
        "development": [bundle.dates[0], bundle.dates[DEVELOPMENT_MONTHS]],
        "embargo": bundle.dates[DEVELOPMENT_MONTHS + 1],
        "holdout": [bundle.dates[holdout_start + 1], bundle.dates[-1]],
    }
    data_fingerprint = _fingerprint(bundle.quality)
    split_fingerprint = _fingerprint(split)
    batch_id = "usda-crop-supply-demand-" + _fingerprint(
        {
            "code": code_commit,
            "data": data_fingerprint,
            "controls": full_gate_controls.get("control_fingerprint"),
            "split": split,
            "candidates": [candidate.candidate_id for candidate in candidates],
        }
    )[7:19]
    decision = {
        "verdict": verdict,
        "criterion_diagnosis": criterion_diagnosis,
        "diagnostic_classification": diagnostic_classification,
        "objective": OBJECTIVE,
        "provisional_best_candidate_id": winner.candidate_id,
        "confirmed_candidate_id": winner.candidate_id if live_passed else None,
        "selected_candidate_id": winner.candidate_id if implementation_ready else None,
        "paper_candidate_id": winner.candidate_id if paper_passed and not live_passed else None,
        "selected_strategy_fingerprint": (
            winner.strategy_fingerprint if implementation_ready else None
        ),
        "research_canary_eligible": implementation_ready,
        "paper_forward_eligible": paper_passed and not live_passed,
        "live_implementation_available": LIVE_IMPLEMENTATION_AVAILABLE,
        "live_whitelist_authorized": LIVE_WHITELIST_AUTHORIZED,
        "selected_deploy_config": None,
        "gates": gates,
        "paper_gates": paper_gates,
        "dsr": None if dsr is None else str(dsr),
        "pbo": None if pbo is None else str(pbo),
        "psr": None if holdout_psr is None else str(holdout_psr),
        "next_strategy_family": (
            "implement_live_usda_crop_regime"
            if live_passed
            else "forward_paper_usda_crop_supply_demand"
            if paper_passed
            else "independent_energy_cross_market"
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
        "usda_crop_data": bundle.quality,
        "usda_crop_data_fingerprint": data_fingerprint,
        "supply_demand_data_fingerprint": prior_factory_payload.get(
            "supply_demand_data_fingerprint"
        ),
        "full_gate_controls": full_gate_controls,
        "gate_power": {
            "preregistered_family_calibration": family_calibration,
            "actual_holdout": actual_holdout_psr_power(len(winner_holdout)),
        },
        "split_fingerprint": split_fingerprint,
        "development_selection": {
            "window": split["development"],
            "months": DEVELOPMENT_MONTHS,
            "selected_candidate_id": winner.candidate_id,
            "selection_metric": "development excess Sharpe after 25bps",
        },
        "holdout_confirmation": {
            "window": split["holdout"],
            "embargo_months": EMBARGO_MONTHS,
            "months": len(winner_holdout),
            "psr_vs_cash": None if holdout_psr is None else str(holdout_psr),
            "excess_annual_return_50bps": excess_50,
        },
        "economic_comparison": {
            "incumbent_correlation": incumbent_correlation,
            "incumbent_sharpe": incumbent_stats.sharpe,
            "blend_sharpe": blend_stats.sharpe,
            "blend_sharpe_improvement": round(blend_improvement, 6),
            "incumbent_max_drawdown_pct": incumbent_stats.max_dd_pct,
            "blend_max_drawdown_pct": blend_stats.max_dd_pct,
        },
        "trial_records": records,
        "audit_records": audit_records,
        "development_returns": development_returns,
        "decision": decision,
        "research_candidate": winner.as_dict() if live_passed else None,
        "paper_candidate": winner.as_dict() if paper_passed and not live_passed else None,
        "research_live_parity": {
            "passed": implementation_ready,
            "reason": (
                None
                if implementation_ready
                else "monthly USDA revision policy is not implemented in the live engine"
            ),
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "target_weights": target_weights,
            "target_weights_digest": target_digest,
            "latest_release_date": bundle.latest_release_date.isoformat(),
        },
        "safety": [
            "research and paper-forward evidence only",
            "no broker API",
            "no orders",
            "no capital, cap, arming, or whitelist change",
        ],
    }


def render_usda_crop_factory_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    holdout = payload["holdout_confirmation"]
    economics = payload["economic_comparison"]
    power = payload["gate_power"]["actual_holdout"]
    failed = [
        gate["gate_id"]
        for gate in decision["gates"]
        if gate["blocking"] and not gate["passed"]
    ]
    return "\n".join(
        [
            "# USDA 작물 수급 독립 전략 공장",
            "",
            f"- 기준 진단: `{decision['criterion_diagnosis']}`",
            f"- 전략 판정: `{decision['verdict']}`",
            f"- 실패 유형: `{decision['diagnostic_classification']}`",
            f"- 개발 선택 후보: `{decision['provisional_best_candidate_id']}`",
            f"- 감사 시도: {payload['global_audit_trial_count']}회 (현재 가족 16회)",
            f"- 홀드아웃: {holdout['months']}개월, 현금 초과 PSR {holdout['psr_vs_cash']}",
            f"- 50bp 후 연 초과수익: {holdout['excess_annual_return_50bps']:.4%}",
            f"- 기존 포트폴리오 상관: {economics['incumbent_correlation']:.4f}",
            f"- 80% 검출 최소 연 샤프 근사: "
            f"{power['minimum_80pct_detectable_annual_sharpe_approx']:.3f}",
            f"- 실패 관문: {', '.join(failed) if failed else '없음'}",
            f"- 실거래 구현 정합: {decision['live_implementation_available']}",
            "- 주문/자본/허용목록 변경: 0",
        ]
    )


__all__ = [
    "ESMIS_INDEX_URL",
    "CropRevisionSnapshot",
    "CropSupplyDemandBundle",
    "CropSupplyDemandPolicy",
    "WasdeWorkbookRef",
    "actual_holdout_psr_power",
    "build_revision_snapshots",
    "crop_target_gold_weight",
    "generate_crop_supply_demand_candidates",
    "load_crop_supply_demand_bundle",
    "parse_wasde_index_pages",
    "parse_wasde_workbook",
    "render_usda_crop_factory_markdown",
    "run_usda_crop_supply_demand_factory",
]
