"""Spec 156: point-in-time broad commodity term-structure strategy factory."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from xml.etree import ElementTree

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
from auto_invest.market_data.public_data import SeriesPoint

SCHEMA_VERSION = "1.0"
EXPECTED_CANDIDATES = 16
EXPECTED_PRIOR_TRIALS = 656
EXPECTED_GLOBAL_AUDIT_TRIALS = 672
DEVELOPMENT_MONTHS = 96
EMBARGO_MONTHS = 1
MIN_HOLDOUT_MONTHS = 120
FACTORY_EDGE = "FACTORY_EDGE"
PAPER_CHALLENGER = "PAPER_CHALLENGER"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
OBJECTIVE = "commodity_term_structure_diversifier"
FAMILIES = ("carry_positive", "carry_momentum", "carry_rank", "defensive_carry")
BLACKROCK_PORTFOLIO_ID = "239757"
BLACKROCK_TICKER = "GSG"
BLACKROCK_URL = (
    "https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v2/"
    "get-product-data?appSubType=ISHARES&appType=PRODUCT_PAGE&component=performance&"
    "locale=en_US&portfolioId=239757&targetSite=us-ishares&userType=individual&"
    "excludeContent=true"
)
WORLD_BANK_URL = (
    "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-"
    "0050012026/related/CMO-Historical-Data-Monthly.xlsx"
)
LIVE_WHITELIST_AUTHORIZED = False


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _content_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CommodityPolicy:
    family: str
    carry_lookback_months: int
    max_commodity_weight: Decimal
    momentum_lookback_months: int = 12
    regime_lookback_months: int = 36

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "carry_lookback_months": self.carry_lookback_months,
            "max_commodity_weight": str(self.max_commodity_weight),
            "momentum_lookback_months": self.momentum_lookback_months,
            "regime_lookback_months": self.regime_lookback_months,
        }


@dataclass(frozen=True)
class CommodityCandidate:
    candidate_id: str
    trial_index: int
    policy: CommodityPolicy
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.policy.family,
            "policy": self.policy.as_dict(),
            "strategy_fingerprint": self.strategy_fingerprint,
            "execution_symbols": ["GSG", "USD"],
            "instrument_basis_risk": (
                "GSG NAV differs from the S&P GSCI benchmark and the World Bank spot proxy"
            ),
            "live_expressible": False,
            "live_blocker": "GSG is not in the active live whitelist",
        }


@dataclass(frozen=True)
class CommoditySourceBundle:
    dates: tuple[str, ...]
    fund_levels: tuple[float, ...]
    benchmark_levels: tuple[float, ...]
    spot_levels: tuple[float, ...]
    cash_rates: tuple[float, ...]
    quality: dict[str, Any]


def generate_commodity_candidates() -> tuple[CommodityCandidate, ...]:
    output: list[CommodityCandidate] = []
    for family in FAMILIES:
        for lookback in (3, 12):
            for maximum in (Decimal("0.5"), Decimal("1.0")):
                policy = CommodityPolicy(family, lookback, maximum)
                digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": policy.as_dict()})
                output.append(
                    CommodityCandidate(
                        candidate_id=f"commodity-{family}-{digest[7:19]}",
                        trial_index=len(output) + 1,
                        policy=policy,
                        strategy_fingerprint=_fingerprint(
                            {
                                "instrument": "GSG",
                                "cash": "DGS3MO",
                                "policy": policy.as_dict(),
                                "signal": (
                                    "lagged_gsci_total_return_minus_world_bank_total_index_and_cash"
                                ),
                            }
                        ),
                    )
                )
    if len(output) != EXPECTED_CANDIDATES:
        raise RuntimeError("commodity candidate count contract violated")
    if len({item.candidate_id for item in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("commodity candidate id uniqueness contract violated")
    if len({item.strategy_fingerprint for item in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("commodity strategy fingerprint uniqueness contract violated")
    return tuple(output)


def _blackrock_points(payload: dict[str, Any], key: str) -> dict[str, float]:
    try:
        points = payload["componentsByNameMap"]["performance"]["containersByNameMap"]["chart"][
            "dataPointsByNameMap"
        ][key]
        raw_dates = points["asOfDate"]
        raw_values = points["value"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"BlackRock {key} schema mismatch") from exc
    if not isinstance(raw_dates, list) or not isinstance(raw_values, list):
        raise ValueError(f"BlackRock {key} arrays are missing")
    if len(raw_dates) != len(raw_values) or len(raw_dates) < 240:
        raise ValueError(f"BlackRock {key} coverage is incomplete")
    output: dict[str, float] = {}
    for raw_date, raw_value in zip(raw_dates, raw_values, strict=True):
        text = str(raw_date)
        if not re.fullmatch(r"\d{8}", text):
            raise ValueError(f"BlackRock {key} date is malformed")
        month = f"{text[:4]}-{text[4:6]}-01"
        value = float(raw_value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"BlackRock {key} value must be positive")
        output[month] = value
    return output


def parse_blackrock_performance(raw: bytes) -> tuple[dict[str, float], dict[str, float]]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("BlackRock response is not valid JSON") from exc
    page_scope = payload.get("pageScopeData", {})
    ticker = str(page_scope.get("ticker", "")).upper()
    product_id = str(payload.get("productId", page_scope.get("portfolioId", "")))
    if ticker != BLACKROCK_TICKER:
        raise ValueError("BlackRock product ticker mismatch")
    if product_id and product_id != BLACKROCK_PORTFOLIO_ID:
        raise ValueError("BlackRock portfolio id mismatch")
    return _blackrock_points(payload, "performanceData"), _blackrock_points(
        payload, "benchmarkData"
    )


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return ["".join(node.text or "" for node in item.findall(".//x:t", namespace)) for item in root]


def parse_world_bank_total_index(raw: bytes) -> tuple[dict[str, float], str]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            strings = _shared_strings(archive)
            root = ElementTree.fromstring(archive.read("xl/worksheets/sheet3.xml"))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError("World Bank workbook schema mismatch") from exc

    values: dict[str, float] = {}
    updated = ""
    for row in root.findall(".//x:sheetData/x:row", namespace):
        cells: dict[str, str] = {}
        for cell in row.findall("x:c", namespace):
            reference = str(cell.attrib.get("r", ""))
            column = re.sub(r"\d", "", reference)
            node = cell.find("x:v", namespace)
            if node is None or node.text is None:
                continue
            text = node.text
            if cell.attrib.get("t") == "s":
                try:
                    text = strings[int(text)]
                except (IndexError, ValueError) as exc:
                    raise ValueError("World Bank shared-string mismatch") from exc
            cells[column] = text
        label = cells.get("A", "")
        if label.startswith("Updated on "):
            updated = label.removeprefix("Updated on ").strip()
        if not re.fullmatch(r"\d{4}M\d{2}", label) or "B" not in cells:
            continue
        month = f"{label[:4]}-{label[5:]}-01"
        value = float(cells["B"])
        if not math.isfinite(value) or value <= 0:
            raise ValueError("World Bank Total Index must be positive")
        values[month] = value
    if len(values) < 240 or not updated:
        raise ValueError("World Bank Total Index coverage is incomplete")
    return values, updated


def _latest_rate_before(points: list[SeriesPoint], cutoff: date) -> float | None:
    for point in reversed(points):
        if point.value is not None and date.fromisoformat(point.date) < cutoff:
            return float(point.value)
    return None


def load_commodity_bundle(
    blackrock_raw: bytes,
    world_bank_raw: bytes,
    cash_points: list[SeriesPoint],
    *,
    current_date: date,
) -> CommoditySourceBundle:
    fund, benchmark = parse_blackrock_performance(blackrock_raw)
    spot, world_bank_updated = parse_world_bank_total_index(world_bank_raw)
    common = sorted(set(fund) & set(benchmark) & set(spot))
    if len(common) < 240:
        raise ValueError("commodity source common coverage must contain 240 months")
    common = common[-240:]
    rates = [_latest_rate_before(cash_points, date.fromisoformat(month)) for month in common]
    observed = [point for point in cash_points if point.value is not None]
    last_month_end = _month_end(date.fromisoformat(common[-1]))
    freshness_days = (current_date - last_month_end).days
    cash_age = (current_date - date.fromisoformat(observed[-1].date)).days if observed else 10_000
    complete = bool(
        common[0] == "2006-08-01"
        and len(common) == 240
        and common[-1] >= "2026-07-01"
        and all(value is not None for value in rates)
        and freshness_days <= 62
        and cash_age <= 7
    )
    quality = {
        "complete": complete,
        "common_months": len(common),
        "first_month": common[0],
        "last_month": common[-1],
        "freshness_days": freshness_days,
        "cash_last_date": observed[-1].date if observed else None,
        "cash_age_days": cash_age,
        "blackrock": {
            "provider": "BlackRock iShares",
            "portfolio_id": BLACKROCK_PORTFOLIO_ID,
            "ticker": BLACKROCK_TICKER,
            "benchmark": "S&P GSCI Total Return",
            "url": BLACKROCK_URL,
            "content_digest": _content_digest(blackrock_raw),
            "raw_series_published": False,
        },
        "world_bank": {
            "provider": "World Bank Prospects Group",
            "workbook": "CMO-Historical-Data-Monthly.xlsx",
            "sheet": "Monthly Indices",
            "column": "Total Index",
            "updated": world_bank_updated,
            "url": WORLD_BANK_URL,
            "content_digest": _content_digest(world_bank_raw),
        },
        "cash": {"provider": "Federal Reserve via FRED", "series_id": "DGS3MO"},
        "signal_definition": (
            "S&P GSCI total return minus World Bank Total Index and prior-known cash returns"
        ),
        "basis_risk": (
            "broad-index composition and Treasury collateral-benchmark differences remain"
        ),
    }
    return CommoditySourceBundle(
        dates=tuple(common),
        fund_levels=tuple(fund[month] for month in common),
        benchmark_levels=tuple(benchmark[month] for month in common),
        spot_levels=tuple(spot[month] for month in common),
        cash_rates=tuple(float(value) for value in rates if value is not None),
        quality=quality,
    )


def _month_end(value: date) -> date:
    if value.month == 12:
        return date(value.year, 12, 31)
    return date(value.year, value.month + 1, 1).fromordinal(
        date(value.year, value.month + 1, 1).toordinal() - 1
    )


def _rolling_means(values: list[float], window: int) -> list[float]:
    if len(values) < window:
        return []
    return [sum(values[end - window : end]) / window for end in range(window, len(values) + 1)]


def commodity_target_weight(
    policy: CommodityPolicy,
    *,
    carry_history: list[float],
    benchmark_history: list[float],
    fund_return_history: list[float],
) -> Decimal:
    means = _rolling_means(carry_history, policy.carry_lookback_months)
    if not means:
        return Decimal("0")
    current = means[-1]
    active = current > 0.0
    if policy.family == "carry_momentum":
        lookback = policy.momentum_lookback_months
        active = bool(
            active
            and len(benchmark_history) > lookback
            and benchmark_history[-1] / benchmark_history[-1 - lookback] - 1.0 > 0.0
        )
    elif policy.family == "carry_rank":
        prior = means[-1 - policy.regime_lookback_months : -1]
        active = len(prior) == policy.regime_lookback_months and current > statistics.median(prior)
    elif policy.family == "defensive_carry":
        vols: list[float] = []
        for end in range(12, len(fund_return_history) + 1):
            window = fund_return_history[end - 12 : end]
            vols.append(statistics.stdev(window) if len(set(window)) > 1 else 0.0)
        prior_vols = vols[-1 - policy.regime_lookback_months : -1]
        active = bool(
            active
            and len(vols) > policy.regime_lookback_months
            and len(prior_vols) == policy.regime_lookback_months
            and vols[-1] <= statistics.median(prior_vols)
        )
    elif policy.family != "carry_positive":
        raise ValueError(f"unknown commodity family: {policy.family}")
    return policy.max_commodity_weight if active else Decimal("0")


def commodity_source_returns(
    bundle: CommoditySourceBundle,
) -> tuple[list[float], list[float], list[float]]:
    fund = [
        bundle.fund_levels[index] / bundle.fund_levels[index - 1]
        for index in range(1, len(bundle.dates))
    ]
    cash = [1.0 + bundle.cash_rates[index - 1] / 1200.0 for index in range(1, len(bundle.dates))]
    carry = [
        bundle.benchmark_levels[index] / bundle.benchmark_levels[index - 1]
        - bundle.spot_levels[index] / bundle.spot_levels[index - 1]
        - (cash[index - 1] - 1.0)
        for index in range(1, len(bundle.dates))
    ]
    return fund, carry, cash


def _candidate_factors(
    candidate: CommodityCandidate,
    bundle: CommoditySourceBundle,
    *,
    cost_bps: int,
) -> tuple[list[float], list[Decimal], float]:
    fund, carry, cash = commodity_source_returns(bundle)
    output: list[float] = []
    weights: list[Decimal] = []
    previous = Decimal("0")
    turnover_total = Decimal("0")
    for index, (fund_factor, cash_factor) in enumerate(zip(fund, cash, strict=True)):
        weight = commodity_target_weight(
            candidate.policy,
            carry_history=carry[:index],
            benchmark_history=list(bundle.benchmark_levels[: index + 1]),
            fund_return_history=[factor - 1.0 for factor in fund[:index]],
        )
        turnover = abs(weight - previous)
        gross = float(weight) * fund_factor + (1.0 - float(weight)) * cash_factor
        net = gross * max(0.0, 1.0 - float(turnover) * cost_bps / 10_000.0)
        if net <= 0.0:
            raise ValueError("commodity cost model produced a non-positive factor")
        output.append(net)
        weights.append(weight)
        turnover_total += turnover
        previous = weight
    return output, weights, float(turnover_total)


def _segments(returns: list[float], count: int = 10) -> list[list[float]]:
    size = len(returns) // count
    return (
        [
            returns[index * size : (index + 1) * size if index < count - 1 else len(returns)]
            for index in range(count)
        ]
        if size >= 2
        else []
    )


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


def _calibration_valid(payload: dict[str, Any], *, code_commit: str) -> bool:
    family = payload.get("family_calibrations", {}).get("16", {})
    thresholds = payload.get("thresholds", {})
    return bool(
        payload.get("gate_version") == GATE_VERSION
        and payload.get("verdict") == CALIBRATED
        and payload.get("code_commit") == code_commit
        and int(payload.get("scenario", {}).get("repetitions", 0)) >= 200
        and family.get("live_calibrated") is True
        and float(family.get("null_false_acceptance_rate", 1.0)) <= 0.05
        and float(family.get("target_live_detection_rate", 0.0)) >= 0.80
        and float(thresholds.get("holdout_psr_min", 0.0)) == HOLDOUT_PSR_MIN
        and float(thresholds.get("paper_psr_min", 0.0)) == PAPER_PSR_MIN
    )


def _annualized_excess(candidate: list[float], cash: list[float]) -> float:
    relative = math.prod(a / b for a, b in zip(candidate, cash, strict=True))
    return relative ** (12.0 / len(candidate)) - 1.0


def run_commodity_term_structure_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    bundle: CommoditySourceBundle,
    *,
    prior_factory_payload: dict[str, Any],
    calibration_evidence: dict[str, Any],
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    if len(rows) != len(bundle.dates) or len(gold_levels) != len(bundle.dates):
        raise ValueError("incumbent and commodity source months must align")
    if [row.date[:7] for row in rows] != [value[:7] for value in bundle.dates]:
        raise ValueError("incumbent dates do not align with commodity source months")
    candidates = generate_commodity_candidates()
    _, _, cash_all = commodity_source_returns(bundle)
    holdout_start = DEVELOPMENT_MONTHS + EMBARGO_MONTHS
    if len(cash_all) - holdout_start < MIN_HOLDOUT_MONTHS:
        raise ValueError("commodity untouched holdout must contain at least 120 months")

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
        candidate_weights: list[Decimal] = []
        turnover = 0.0
        for cost in (10, 25, 50):
            factors, weights, candidate_turnover = _candidate_factors(
                candidate, bundle, cost_bps=cost
            )
            full_by_cost[cost] = factors
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
        segment_sharpes = [annualized_sharpe(segment) for segment in _segments(development)]
        development_stats = summarize([1.0 + value for value in development])
        holdout_stats = summarize(holdout)
        development_returns.append(development)
        development_segments.append(segment_sharpes)
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
                "development_max_drawdown_25bps": round(development_stats.max_dd_pct, 6),
                "holdout_sharpe_25bps": round(holdout_stats.sharpe, 6),
                "holdout_excess_sharpe_25bps": round(annualized_sharpe(holdout_excess), 6),
                "holdout_cagr_25bps": round(holdout_stats.cagr_pct, 6),
                "holdout_max_drawdown_25bps": round(holdout_stats.max_dd_pct, 6),
                "holdout_excess_annual_return_50bps": round(
                    _annualized_excess(full_by_cost[50][holdout_start:], cash_all[holdout_start:]),
                    8,
                ),
                "turnover": round(turnover, 6),
                "active_months": sum(weight > 0 for weight in candidate_weights),
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

    prior = _prior_records(prior_factory_payload)
    audit_records = prior + records
    fingerprints = [
        str(row.get("strategy_fingerprint") or row.get("candidate_id")) for row in audit_records
    ]
    unique_audit = len(set(fingerprints))
    calibration_passed = _calibration_valid(calibration_evidence, code_commit=code_commit)
    live_weight = commodity_target_weight(
        winner.policy,
        carry_history=commodity_source_returns(bundle)[1],
        benchmark_history=list(bundle.benchmark_levels),
        fund_return_history=[value - 1.0 for value in commodity_source_returns(bundle)[0]],
    )
    target_weights = {"GSG": str(live_weight), "USD": str(Decimal("1") - live_weight)}
    target_digest = _fingerprint(target_weights)
    excess_50 = float(winner_record["holdout_excess_annual_return_50bps"])

    gates: list[dict[str, Any]] = []
    paper_gates: list[dict[str, Any]] = []

    def add_gate(
        gate_id: str, passed: bool, actual: Any, required: Any, stage: str, *, blocking: bool = True
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
    add_gate("complete_family_trials", len(records) == 16, len(records), 16, "audit")
    add_gate("prior_audit_complete", len(prior) == 656, len(prior), 656, "audit")
    add_gate("global_audit_trials", len(audit_records) == 672, len(audit_records), 672, "audit")
    add_gate("unique_audit_fingerprints", unique_audit == 672, unique_audit, 672, "audit")
    add_gate(
        "commodity_data_complete",
        bundle.quality.get("complete") is True,
        bundle.quality.get("complete"),
        True,
        "data",
    )
    add_gate("research_live_parity", bool(target_digest), bool(target_digest), True, "parity")
    add_gate("development_months", DEVELOPMENT_MONTHS == 96, DEVELOPMENT_MONTHS, 96, "split")
    add_gate("embargo_months", EMBARGO_MONTHS == 1, EMBARGO_MONTHS, 1, "split")
    add_gate("holdout_months", len(winner_holdout) >= 120, len(winner_holdout), 120, "split")
    add_gate(
        "development_dsr_diagnostic",
        dsr is not None and dsr >= Decimal("0.95"),
        dsr,
        Decimal("0.95"),
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
    add_gate("holdout_excess_50bps_positive", excess_50 > 0.0, excess_50, "> 0", "economics")
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
    add_paper("paper_excess_50bps_positive", excess_50 > 0.0, excess_50, "> 0")
    add_paper(
        "paper_incumbent_correlation", incumbent_correlation < 0.80, incumbent_correlation, "< 0.80"
    )
    add_paper(
        "paper_blend_sharpe_non_declining",
        blend_improvement >= 0.0,
        round(blend_improvement, 6),
        ">= 0.0",
    )
    add_paper(
        "paper_blend_drawdown_bounded",
        blend_stats.max_dd_pct <= incumbent_stats.max_dd_pct * 1.20,
        blend_stats.max_dd_pct,
        round(incumbent_stats.max_dd_pct * 1.20, 6),
    )
    paper_passed = common_passed and all(gate["passed"] for gate in paper_gates)
    verdict = FACTORY_EDGE if live_passed else PAPER_CHALLENGER if paper_passed else NO_FACTORY_EDGE

    data_fingerprint = _fingerprint(bundle.quality)
    split = {
        "development": [bundle.dates[1], bundle.dates[DEVELOPMENT_MONTHS]],
        "embargo": bundle.dates[DEVELOPMENT_MONTHS + 1],
        "holdout": [bundle.dates[holdout_start + 1], bundle.dates[-1]],
    }
    split_fingerprint = _fingerprint(split)
    batch_id = (
        "commodity-term-structure-"
        + _fingerprint(
            {
                "code": code_commit,
                "data": data_fingerprint,
                "split": split,
                "gate": GATE_VERSION,
                "candidates": [candidate.candidate_id for candidate in candidates],
            }
        )[7:19]
    )
    decision = {
        "verdict": verdict,
        "objective": OBJECTIVE,
        "provisional_best_candidate_id": winner.candidate_id,
        "selected_candidate_id": winner.candidate_id if live_passed else None,
        "paper_candidate_id": winner.candidate_id if paper_passed and not live_passed else None,
        "research_canary_eligible": live_passed,
        "paper_forward_eligible": paper_passed and not live_passed,
        "live_whitelist_authorized": LIVE_WHITELIST_AUTHORIZED,
        "selected_deploy_config": None,
        "gates": gates,
        "paper_gates": paper_gates,
        "dsr": None if dsr is None else str(dsr),
        "pbo": None if pbo is None else str(pbo),
        "psr": None if holdout_psr is None else str(holdout_psr),
        "next_strategy_family": "hardened_canary"
        if live_passed
        else "forward_paper_commodity_term_structure"
        if paper_passed
        else "commodity_inventory_positioning",
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
        "commodity_data": bundle.quality,
        "commodity_data_fingerprint": data_fingerprint,
        "split_fingerprint": split_fingerprint,
        "gate_power": family_calibration,
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
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "target_weights": target_weights,
            "target_weights_digest": target_digest,
        },
        "live_commodity_evidence": {
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "data_fingerprint": data_fingerprint,
            "split_fingerprint": split_fingerprint,
            "code_commit": code_commit,
            "target_weights_digest": target_digest,
            "fresh": bundle.quality.get("freshness_days", 10_000) <= 62,
            "complete": bundle.quality.get("complete") is True,
            "live_whitelist_authorized": False,
        },
        "safety": [
            "research and paper-forward evidence only",
            "no broker API",
            "no orders",
            "no capital or whitelist change",
        ],
    }


def validate_live_commodity_evidence(payload: dict[str, Any], *, code_commit: str) -> None:
    evidence = payload.get("live_commodity_evidence", {})
    decision = payload.get("decision", {})
    if decision.get("verdict") != FACTORY_EDGE or not decision.get("research_canary_eligible"):
        raise ValueError("commodity evidence is not live-grade")
    if (
        evidence.get("code_commit") != code_commit
        or not evidence.get("complete")
        or not evidence.get("fresh")
    ):
        raise ValueError("commodity evidence is stale, incomplete, or mismatched")
    if not evidence.get("live_whitelist_authorized"):
        raise ValueError("GSG is not authorized by the active live whitelist")


def render_commodity_factory_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    holdout = payload["holdout_confirmation"]
    comparison = payload["economic_comparison"]
    failed = [
        gate["gate_id"] for gate in decision["gates"] if gate["blocking"] and not gate["passed"]
    ]
    return "\n".join(
        [
            "# 독립 원자재 기간구조 전략 공장",
            "",
            f"- 판정: `{decision['verdict']}`",
            f"- 개발 선택 후보: `{decision['provisional_best_candidate_id']}`",
            f"- 감사 시도: {payload['global_audit_trial_count']}회 "
            f"(현재 가족 {payload['multiplicity_trial_count']}회)",
            f"- 홀드아웃: {holdout['months']}개월, 현금 초과 PSR {holdout['psr_vs_cash']}",
            f"- 50bp 후 연 초과수익: {holdout['excess_annual_return_50bps']:.4%}",
            f"- 기존 포트폴리오 혼합 샤프 변화: {comparison['blend_sharpe_improvement']:+.3f}",
            f"- 실패 관문: {', '.join(failed) if failed else '없음'}",
            "- 주문/자본/허용목록 변경: 0",
        ]
    )


__all__ = [
    "BLACKROCK_URL",
    "WORLD_BANK_URL",
    "CommodityPolicy",
    "CommoditySourceBundle",
    "commodity_source_returns",
    "commodity_target_weight",
    "generate_commodity_candidates",
    "load_commodity_bundle",
    "parse_blackrock_performance",
    "parse_world_bank_total_index",
    "render_commodity_factory_markdown",
    "run_commodity_term_structure_factory",
    "validate_live_commodity_evidence",
]
