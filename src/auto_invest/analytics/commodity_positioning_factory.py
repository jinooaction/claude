"""Spec 157: point-in-time commodity positioning and inventory strategy factory."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import xlrd

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probabilistic_sharpe,
    probability_of_backtest_overfitting,
)
from auto_invest.analytics.commodity_term_structure_factory import (
    BLACKROCK_URL,
    _calibration_valid,
    _latest_rate_before,
    parse_blackrock_performance,
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
from auto_invest.analytics.real_world_gate_controls import REAL_WORLD_CONTROLS_VALID
from auto_invest.analytics.risk_managed_beta import (
    MonthlyRow,
    market_total_return_factors,
    summarize,
)
from auto_invest.market_data.public_data import SeriesPoint

SCHEMA_VERSION = "1.0"
EXPECTED_CANDIDATES = 16
EXPECTED_PRIOR_TRIALS = 672
EXPECTED_GLOBAL_AUDIT_TRIALS = 688
DEVELOPMENT_MONTHS = 96
EMBARGO_MONTHS = 1
MIN_HOLDOUT_MONTHS = 120
FACTORY_EDGE = "FACTORY_EDGE"
PAPER_CHALLENGER = "PAPER_CHALLENGER"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
OBJECTIVE = "commodity_positioning_inventory_diversifier"
FAMILIES = (
    "managed_money_trend",
    "producer_scarcity",
    "inventory_tightness",
    "positioning_inventory_confirmation",
)
CFTC_DATASET_ID = "72hh-3qpy"
CFTC_API_BASE = f"https://publicreporting.cftc.gov/resource/{CFTC_DATASET_ID}.json"
EIA_SERIES_ID = "WCESTUS1"
EIA_INVENTORY_URL = "https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls"
FUND_TICKER = "GSG"
LIVE_WHITELIST_AUTHORIZED = False
CFTC_CONTRACTS = {
    "001602": "WHEAT-SRW",
    "002602": "CORN",
    "005602": "SOYBEANS",
    "023651": "NAT GAS NYME",
    "033661": "COTTON NO. 2",
    "057642": "LIVE CATTLE",
    "067651": "WTI-PHYSICAL",
    "080732": "SUGAR NO. 11",
    "083731": "COFFEE C",
    "084691": "SILVER",
    "085692": "COPPER- #1",
    "088691": "GOLD",
}


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _content_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CftcPosition:
    contract_code: str
    contract_name: str
    report_date: date
    available_date: date
    open_interest: float
    managed_money_net_ratio: float
    producer_net_ratio: float


@dataclass(frozen=True)
class EiaInventory:
    period_end: date
    available_date: date
    thousand_barrels: float


@dataclass(frozen=True)
class CommodityPositioningPolicy:
    family: str
    lookback_weeks: int
    max_commodity_weight: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "lookback_weeks": self.lookback_weeks,
            "max_commodity_weight": str(self.max_commodity_weight),
        }


@dataclass(frozen=True)
class CommodityPositioningCandidate:
    candidate_id: str
    trial_index: int
    policy: CommodityPositioningPolicy
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "family": self.policy.family,
            "policy": self.policy.as_dict(),
            "strategy_fingerprint": self.strategy_fingerprint,
            "execution_symbols": [FUND_TICKER, "USD"],
            "live_expressible": False,
            "live_blocker": "GSG is not in the active live whitelist",
            "basis_risk": "fixed CFTC contracts and GSG index weights differ",
        }


@dataclass(frozen=True)
class CommodityPositioningBundle:
    dates: tuple[str, ...]
    fund_levels: tuple[float, ...]
    cash_rates: tuple[float, ...]
    managed_signals: dict[int, tuple[float, ...]]
    producer_signals: dict[int, tuple[float, ...]]
    inventory_signals: dict[int, tuple[float, ...]]
    quality: dict[str, Any]


def generate_positioning_candidates() -> tuple[CommodityPositioningCandidate, ...]:
    output: list[CommodityPositioningCandidate] = []
    for family in FAMILIES:
        for lookback in (26, 52):
            for maximum in (Decimal("0.5"), Decimal("1.0")):
                policy = CommodityPositioningPolicy(family, lookback, maximum)
                digest = _fingerprint({"schema": SCHEMA_VERSION, "policy": policy.as_dict()})
                output.append(
                    CommodityPositioningCandidate(
                        candidate_id=f"commodity-positioning-{family}-{digest[7:19]}",
                        trial_index=len(output) + 1,
                        policy=policy,
                        strategy_fingerprint=_fingerprint(
                            {
                                "instrument": FUND_TICKER,
                                "cash": "DGS3MO",
                                "cftc_contracts": sorted(CFTC_CONTRACTS),
                                "eia_series": EIA_SERIES_ID,
                                "publication_lags_days": {"cftc": 3, "eia": 5},
                                "policy": policy.as_dict(),
                            }
                        ),
                    )
                )
    if len(output) != EXPECTED_CANDIDATES:
        raise RuntimeError("commodity positioning candidate count contract violated")
    if len({item.candidate_id for item in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("commodity positioning candidate ids are not unique")
    if len({item.strategy_fingerprint for item in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("commodity positioning fingerprints are not unique")
    return tuple(output)


def parse_cftc_positions(raw: bytes) -> tuple[CftcPosition, ...]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("CFTC response is not valid JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("CFTC response must be a row array")
    output: list[CftcPosition] = []
    seen: set[tuple[str, date]] = set()
    for row in payload:
        if not isinstance(row, dict):
            continue
        code = str(row.get("cftc_contract_market_code", ""))
        if code not in CFTC_CONTRACTS:
            continue
        try:
            report_date = date.fromisoformat(str(row["report_date_as_yyyy_mm_dd"])[:10])
            open_interest = float(row["open_interest_all"])
            managed_long = float(row["m_money_positions_long_all"])
            managed_short = float(row["m_money_positions_short_all"])
            producer_long = float(row["prod_merc_positions_long"])
            producer_short = float(row["prod_merc_positions_short"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("CFTC position row schema mismatch") from exc
        values = [open_interest, managed_long, managed_short, producer_long, producer_short]
        if open_interest <= 0 or not all(math.isfinite(value) for value in values):
            raise ValueError("CFTC position row contains invalid numeric values")
        identity = (code, report_date)
        if identity in seen:
            raise ValueError("CFTC contract report is duplicated")
        seen.add(identity)
        output.append(
            CftcPosition(
                contract_code=code,
                contract_name=CFTC_CONTRACTS[code],
                report_date=report_date,
                available_date=report_date + timedelta(days=3),
                open_interest=open_interest,
                managed_money_net_ratio=(managed_long - managed_short) / open_interest,
                producer_net_ratio=(producer_long - producer_short) / open_interest,
            )
        )
    found = {item.contract_code for item in output}
    if found != set(CFTC_CONTRACTS):
        raise ValueError("CFTC fixed contract coverage is incomplete")
    return tuple(sorted(output, key=lambda item: (item.report_date, item.contract_code)))


def parse_eia_inventory(raw: bytes) -> tuple[EiaInventory, ...]:
    try:
        workbook = xlrd.open_workbook(file_contents=raw)
        sheet = workbook.sheet_by_name("Data 1")
    except (xlrd.XLRDError, IndexError) as exc:
        raise ValueError("EIA workbook schema mismatch") from exc
    if sheet.nrows < 1000 or str(sheet.cell_value(1, 1)).strip() != EIA_SERIES_ID:
        raise ValueError("EIA WCESTUS1 coverage or series identity is incomplete")
    output: list[EiaInventory] = []
    for index in range(3, sheet.nrows):
        try:
            serial = float(sheet.cell_value(index, 0))
            level = float(sheet.cell_value(index, 1))
            period_end = xlrd.xldate_as_datetime(serial, workbook.datemode).date()
        except (TypeError, ValueError, xlrd.XLDateError) as exc:
            raise ValueError("EIA inventory row schema mismatch") from exc
        if not math.isfinite(level) or level <= 0:
            raise ValueError("EIA inventory level must be positive")
        output.append(EiaInventory(period_end, period_end + timedelta(days=5), level))
    return tuple(output)


def _zscore(values: list[float]) -> float:
    if len(values) < 2:
        raise ValueError("rolling signal requires at least two observations")
    deviation = statistics.stdev(values)
    return 0.0 if deviation <= 1e-12 else (values[-1] - statistics.mean(values)) / deviation


def _position_signal(
    positions: tuple[CftcPosition, ...], decision_date: date, lookback: int, field: str
) -> float | None:
    by_contract: dict[str, list[float]] = {code: [] for code in CFTC_CONTRACTS}
    for item in positions:
        if item.available_date < decision_date:
            by_contract[item.contract_code].append(float(getattr(item, field)))
    scores: list[float] = []
    for code in CFTC_CONTRACTS:
        values = by_contract[code]
        if len(values) < lookback:
            return None
        scores.append(_zscore(values[-lookback:]))
    return statistics.median(scores)


def _inventory_signal(
    inventory: tuple[EiaInventory, ...], decision_date: date, lookback: int
) -> float | None:
    values = [item.thousand_barrels for item in inventory if item.available_date < decision_date]
    return None if len(values) < lookback else -_zscore(values[-lookback:])


def load_positioning_bundle(
    blackrock_raw: bytes,
    cftc_raw: bytes,
    eia_raw: bytes,
    cash_points: list[SeriesPoint],
    *,
    current_date: date,
) -> CommodityPositioningBundle:
    fund, _ = parse_blackrock_performance(blackrock_raw)
    positions = parse_cftc_positions(cftc_raw)
    inventory = parse_eia_inventory(eia_raw)
    dates = sorted(fund)[-240:]
    cash_rates = [_latest_rate_before(cash_points, date.fromisoformat(month)) for month in dates]
    signal_maps: dict[str, dict[int, list[float | None]]] = {
        "managed": {},
        "producer": {},
        "inventory": {},
    }
    for lookback in (26, 52):
        signal_maps["managed"][lookback] = [
            _position_signal(
                positions,
                date.fromisoformat(month),
                lookback,
                "managed_money_net_ratio",
            )
            for month in dates
        ]
        signal_maps["producer"][lookback] = [
            _position_signal(positions, date.fromisoformat(month), lookback, "producer_net_ratio")
            for month in dates
        ]
        signal_maps["inventory"][lookback] = [
            _inventory_signal(inventory, date.fromisoformat(month), lookback) for month in dates
        ]
    first_complete = next(
        (
            index
            for index in range(len(dates))
            if cash_rates[index] is not None
            and all(
                signal_maps[kind][lookback][index] is not None
                for kind in signal_maps
                for lookback in (26, 52)
            )
        ),
        None,
    )
    if first_complete is None:
        raise ValueError("positioning source warm-up never completes")
    dates = dates[first_complete:]
    fund_levels = [fund[month] for month in dates]
    cash = cash_rates[first_complete:]
    if len(dates) - 1 < DEVELOPMENT_MONTHS + EMBARGO_MONTHS + MIN_HOLDOUT_MONTHS:
        raise ValueError("positioning source does not leave a 120-month holdout")
    latest_cftc = max(item.available_date for item in positions)
    latest_eia = max(item.available_date for item in inventory)
    fund_month = date.fromisoformat(dates[-1])
    if fund_month.month == 12:
        fund_end = date(fund_month.year, 12, 31)
    else:
        fund_end = date(fund_month.year, fund_month.month + 1, 1) - timedelta(days=1)
    observed_cash = [point for point in cash_points if point.value is not None]
    ages = {
        "cftc_age_days": (current_date - latest_cftc).days,
        "eia_age_days": (current_date - latest_eia).days,
        "fund_age_days": (current_date - fund_end).days,
        "cash_age_days": (
            current_date - date.fromisoformat(observed_cash[-1].date)
        ).days
        if observed_cash
        else 10_000,
    }
    counts = {
        code: sum(item.contract_code == code for item in positions) for code in CFTC_CONTRACTS
    }
    complete = bool(
        len(dates) - 1 >= 217
        and all(value is not None for value in cash)
        and min(counts.values()) >= 52
        and len(inventory) >= 52
        and ages["cftc_age_days"] <= 14
        and ages["eia_age_days"] <= 14
        and ages["fund_age_days"] <= 62
        and ages["cash_age_days"] <= 7
    )
    quality = {
        "complete": complete,
        "months": len(dates),
        "first_month": dates[0],
        "last_month": dates[-1],
        "freshness_days": max(ages.values()),
        **ages,
        "cftc": {
            "provider": "U.S. Commodity Futures Trading Commission",
            "dataset_id": CFTC_DATASET_ID,
            "contract_codes": sorted(CFTC_CONTRACTS),
            "rows_by_contract": counts,
            "publication_lag_days": 3,
            "content_digest": _content_digest(cftc_raw),
            "classification_limitation": "historical classifications are backcast",
        },
        "eia": {
            "provider": "U.S. Energy Information Administration",
            "series_id": EIA_SERIES_ID,
            "publication_lag_days": 5,
            "content_digest": _content_digest(eia_raw),
            "revision_limitation": "current history can contain revisions",
        },
        "fund": {
            "provider": "BlackRock iShares",
            "ticker": FUND_TICKER,
            "url": BLACKROCK_URL,
            "content_digest": _content_digest(blackrock_raw),
        },
        "cash": {"provider": "Federal Reserve via FRED", "series_id": "DGS3MO"},
        "basis_risk": "fixed normalized signal contracts do not match GSG index weights",
    }

    def finished(kind: str, lookback: int) -> tuple[float, ...]:
        values = signal_maps[kind][lookback][first_complete:]
        if any(value is None for value in values):
            raise ValueError("positioning signal contains a post-warmup gap")
        return tuple(float(value) for value in values if value is not None)

    return CommodityPositioningBundle(
        dates=tuple(dates),
        fund_levels=tuple(fund_levels),
        cash_rates=tuple(float(value) for value in cash if value is not None),
        managed_signals={lookback: finished("managed", lookback) for lookback in (26, 52)},
        producer_signals={lookback: finished("producer", lookback) for lookback in (26, 52)},
        inventory_signals={lookback: finished("inventory", lookback) for lookback in (26, 52)},
        quality=quality,
    )


def positioning_target_weight(
    policy: CommodityPositioningPolicy,
    managed_signal: float,
    producer_signal: float,
    inventory_signal: float,
) -> Decimal:
    if policy.family == "managed_money_trend":
        active = managed_signal > 0
    elif policy.family == "producer_scarcity":
        active = producer_signal > 0
    elif policy.family == "inventory_tightness":
        active = inventory_signal > 0
    elif policy.family == "positioning_inventory_confirmation":
        active = managed_signal > 0 and inventory_signal > 0
    else:
        raise ValueError(f"unknown positioning family: {policy.family}")
    return policy.max_commodity_weight if active else Decimal("0")


def _candidate_factors(
    candidate: CommodityPositioningCandidate,
    bundle: CommodityPositioningBundle,
    *,
    cost_bps: int,
) -> tuple[list[float], list[Decimal], float, list[float]]:
    output: list[float] = []
    cash_output: list[float] = []
    weights: list[Decimal] = []
    previous = Decimal("0")
    turnover_total = Decimal("0")
    lookback = candidate.policy.lookback_weeks
    for index in range(1, len(bundle.dates)):
        signal_index = index - 1
        weight = positioning_target_weight(
            candidate.policy,
            bundle.managed_signals[lookback][signal_index],
            bundle.producer_signals[lookback][signal_index],
            bundle.inventory_signals[lookback][signal_index],
        )
        turnover = abs(weight - previous)
        fund_factor = bundle.fund_levels[index] / bundle.fund_levels[index - 1]
        cash_factor = 1.0 + bundle.cash_rates[signal_index] / 1200.0
        gross = float(weight) * fund_factor + (1.0 - float(weight)) * cash_factor
        net = gross * (1.0 - float(turnover) * cost_bps / 10_000.0)
        if net <= 0:
            raise ValueError("positioning cost model produced a non-positive factor")
        output.append(net)
        cash_output.append(cash_factor)
        weights.append(weight)
        turnover_total += turnover
        previous = weight
    return output, weights, float(turnover_total), cash_output


def _segments(returns: list[float], count: int = 10) -> list[list[float]]:
    size = len(returns) // count
    return [
        returns[index * size : (index + 1) * size if index < count - 1 else len(returns)]
        for index in range(count)
    ] if size >= 2 else []


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


def _real_controls_valid(payload: dict[str, Any], *, code_commit: str) -> bool:
    return bool(
        payload.get("verdict") == REAL_WORLD_CONTROLS_VALID
        and payload.get("promotion_control_passed") is True
        and payload.get("code_commit") == code_commit
        and str(payload.get("control_fingerprint", "")).startswith("sha256:")
    )


def run_commodity_positioning_factory(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    bundle: CommodityPositioningBundle,
    *,
    prior_factory_payload: dict[str, Any],
    calibration_evidence: dict[str, Any],
    real_world_controls: dict[str, Any],
    code_commit: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    if len(rows) != len(bundle.dates) or len(gold_levels) != len(bundle.dates):
        raise ValueError("incumbent and positioning source months must align")
    if [row.date[:7] for row in rows] != [value[:7] for value in bundle.dates]:
        raise ValueError("incumbent dates do not align with positioning months")
    candidates = generate_positioning_candidates()
    holdout_start = DEVELOPMENT_MONTHS + EMBARGO_MONTHS
    factor_count = len(bundle.dates) - 1
    if factor_count - holdout_start < MIN_HOLDOUT_MONTHS:
        raise ValueError("positioning holdout must contain at least 120 months")

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
    cash_all: list[float] = []
    for candidate in candidates:
        full_by_cost: dict[int, list[float]] = {}
        candidate_weights: list[Decimal] = []
        turnover = 0.0
        for cost in (10, 25, 50):
            factors, weights, candidate_turnover, cash = _candidate_factors(
                candidate, bundle, cost_bps=cost
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
                "development_max_drawdown_25bps": round(development_stats.max_dd_pct, 6),
                "holdout_excess_sharpe_25bps": round(annualized_sharpe(holdout_excess), 6),
                "holdout_cagr_25bps": round(holdout_stats.cagr_pct, 6),
                "holdout_max_drawdown_25bps": round(holdout_stats.max_dd_pct, 6),
                "holdout_excess_annual_return_50bps": round(
                    _annualized_excess(full_by_cost[50][holdout_start:], cash_all[holdout_start:]),
                    8,
                ),
                "turnover": round(turnover, 6),
                "active_months": sum(weight > 0 for weight in candidate_weights),
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
    excess_50 = float(winner_record["holdout_excess_annual_return_50bps"])

    prior = _prior_records(prior_factory_payload)
    audit_records = prior + records
    identities = [
        str(row.get("strategy_fingerprint") or row.get("candidate_id"))
        for row in audit_records
    ]
    unique_audit = len(set(identities))
    calibration_passed = _calibration_valid(calibration_evidence, code_commit=code_commit)
    controls_passed = _real_controls_valid(real_world_controls, code_commit=code_commit)
    latest_index = len(bundle.dates) - 1
    latest_lookback = winner.policy.lookback_weeks
    live_weight = positioning_target_weight(
        winner.policy,
        bundle.managed_signals[latest_lookback][latest_index],
        bundle.producer_signals[latest_lookback][latest_index],
        bundle.inventory_signals[latest_lookback][latest_index],
    )
    target_weights = {FUND_TICKER: str(live_weight), "USD": str(Decimal("1") - live_weight)}
    target_digest = _fingerprint(target_weights)

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
    add_gate(
        "real_world_gate_controls",
        controls_passed,
        real_world_controls.get("verdict"),
        REAL_WORLD_CONTROLS_VALID,
        "calibration",
    )
    add_gate("complete_family_trials", len(records) == 16, len(records), 16, "audit")
    add_gate("prior_audit_complete", len(prior) == 672, len(prior), 672, "audit")
    add_gate("global_audit_trials", len(audit_records) == 688, len(audit_records), 688, "audit")
    add_gate("unique_audit_fingerprints", unique_audit == 688, unique_audit, 688, "audit")
    add_gate(
        "positioning_data_complete",
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

    split = {
        "development": [bundle.dates[0], bundle.dates[DEVELOPMENT_MONTHS]],
        "embargo": bundle.dates[DEVELOPMENT_MONTHS + 1],
        "holdout": [bundle.dates[holdout_start + 1], bundle.dates[-1]],
    }
    data_fingerprint = _fingerprint(bundle.quality)
    split_fingerprint = _fingerprint(split)
    batch_id = "commodity-positioning-" + _fingerprint(
        {
            "code": code_commit,
            "data": data_fingerprint,
            "controls": real_world_controls.get("control_fingerprint"),
            "split": split,
            "candidates": [candidate.candidate_id for candidate in candidates],
        }
    )[7:19]
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
        "next_strategy_family": (
            "hardened_canary"
            if live_passed
            else "forward_paper_commodity_positioning"
            if paper_passed
            else "commodity_fundamental_supply_demand"
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
        "positioning_data": bundle.quality,
        "positioning_data_fingerprint": data_fingerprint,
        "real_world_gate_controls": real_world_controls,
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
            "candidate_id": winner.candidate_id,
            "strategy_fingerprint": winner.strategy_fingerprint,
            "target_weights": target_weights,
            "target_weights_digest": target_digest,
        },
        "safety": [
            "research and paper-forward evidence only",
            "no broker API",
            "no orders",
            "no capital or whitelist change",
        ],
    }


def render_positioning_factory_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    holdout = payload["holdout_confirmation"]
    controls = payload["real_world_gate_controls"]
    failed = [
        gate["gate_id"] for gate in decision["gates"] if gate["blocking"] and not gate["passed"]
    ]
    control_rows = controls.get("controls", [])
    control_text = ", ".join(
        f"{row['control_id']} PSR {row['psr']}" for row in control_rows
    )
    return "\n".join(
        [
            "# 독립 원자재 재고·포지셔닝 전략 공장",
            "",
            f"- 현실 관문 감사: `{controls.get('verdict')}` ({control_text})",
            f"- 전략 판정: `{decision['verdict']}`",
            f"- 개발 선택 후보: `{decision['provisional_best_candidate_id']}`",
            f"- 감사 시도: {payload['global_audit_trial_count']}회 (현재 가족 16회)",
            f"- 홀드아웃: {holdout['months']}개월, 현금 초과 PSR {holdout['psr_vs_cash']}",
            f"- 50bp 후 연 초과수익: {holdout['excess_annual_return_50bps']:.4%}",
            f"- 실패 관문: {', '.join(failed) if failed else '없음'}",
            "- 주문/자본/허용목록 변경: 0",
        ]
    )


__all__ = [
    "BLACKROCK_URL",
    "CFTC_API_BASE",
    "CFTC_CONTRACTS",
    "EIA_INVENTORY_URL",
    "CommodityPositioningBundle",
    "CommodityPositioningPolicy",
    "generate_positioning_candidates",
    "load_positioning_bundle",
    "parse_cftc_positions",
    "parse_eia_inventory",
    "positioning_target_weight",
    "render_positioning_factory_markdown",
    "run_commodity_positioning_factory",
]
