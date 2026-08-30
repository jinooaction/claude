"""Spec 174: preregistered accounting cross-sectional factor research.

This module is research-only.  It uses two official Fama-French data vintages,
selects one of sixteen frozen accounting-factor sleeves on development data, and
keeps every broker, order, capital, and live-configuration path closed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from auto_invest.analytics.backtest_overfitting import (
    annualized_sharpe,
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probabilistic_sharpe,
    probability_of_backtest_overfitting,
)
from auto_invest.analytics.research_family_audit import (
    annotate_research_families,
    build_research_family_audit,
)

SCHEMA_VERSION = "1.0"
GATE_VERSION = "3.1"
FAMILY_ID = "equity-accounting-cross-sectional-factors"
EXPECTED_CANDIDATES = 16
EXPECTED_PRIOR_TRIALS = 784
EXPECTED_GLOBAL_AUDIT_TRIALS = 800
EXPECTED_PRIOR_FAMILIES = 19
EXPECTED_PROGRAM_FAMILIES = 20
DEVELOPMENT_START = "1963-07"
DEVELOPMENT_END = "2013-12"
EMBARGO_START = "2014-01"
EMBARGO_END = "2014-12"
HOLDOUT_START = "2015-01"
PRIMARY_ANNUAL_BPS = 150
STRESS_ANNUAL_BPS = (300, 500)
FACTORY_EDGE = "FACTORY_EDGE"
PAPER_CHALLENGER = "PAPER_CHALLENGER"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"
ARCHIVE_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/"
    "Historical_Archives/08%202015%20Update/ftp/"
    "F-F_Research_Data_5_Factors_2x3_CSV.zip"
)
CURRENT_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_CSV.zip"
)

_PROFILES: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("hml", (1.0, 0.0, 0.0)),
    ("rmw", (0.0, 1.0, 0.0)),
    ("cma", (0.0, 0.0, 1.0)),
    ("hml-rmw", (0.5, 0.5, 0.0)),
    ("hml-cma", (0.5, 0.0, 0.5)),
    ("rmw-cma", (0.0, 0.5, 0.5)),
    ("equal-three", (0.333333333333, 0.333333333333, 0.333333333334)),
    ("defensive-three", (0.2, 0.4, 0.4)),
)


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _expected_months(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    output: list[str] = []
    while (year, month) <= (end_year, end_month):
        output.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return output


@dataclass(frozen=True)
class AccountingFactorMonth:
    observed_month: date
    market_excess: float
    size: float
    value: float
    profitability: float
    investment: float
    cash: float


@dataclass(frozen=True)
class AccountingFactorPolicy:
    profile: str
    weights: tuple[float, float, float]
    sleeve_scale: float
    annual_cost_bps: int = PRIMARY_ANNUAL_BPS

    def as_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "weights": {
                "HML": self.weights[0],
                "RMW": self.weights[1],
                "CMA": self.weights[2],
            },
            "sleeve_scale": self.sleeve_scale,
            "annual_cost_bps": self.annual_cost_bps,
            "signal": "cash_plus_self_financing_accounting_factor_sleeve",
        }


@dataclass(frozen=True)
class AccountingFactorCandidate:
    candidate_id: str
    trial_index: int
    policy: AccountingFactorPolicy
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "policy": self.policy.as_dict(),
            "strategy_fingerprint": self.strategy_fingerprint,
            "research_proxy": "Kenneth French HML, RMW, and CMA factor returns",
            "live_expressible": False,
            "live_blocker": (
                "point-in-time constituents, position sizes, short borrow, integer-share "
                "implementation, execution parity, and forward canary evidence are absent"
            ),
        }


@dataclass(frozen=True)
class AccountingFactorBundle:
    development: tuple[AccountingFactorMonth, ...]
    embargo: tuple[AccountingFactorMonth, ...]
    holdout: tuple[AccountingFactorMonth, ...]
    quality: dict[str, object]


def generate_accounting_factor_candidates() -> tuple[AccountingFactorCandidate, ...]:
    output: list[AccountingFactorCandidate] = []
    for profile, weights in _PROFILES:
        for scale in (0.5, 1.0):
            policy = AccountingFactorPolicy(profile, weights, scale)
            digest = _fingerprint(
                {
                    "schema_version": SCHEMA_VERSION,
                    "family_id": FAMILY_ID,
                    "policy": policy.as_dict(),
                    "data": "Fama-French monthly HML RMW CMA",
                    "split": {
                        "development": f"{DEVELOPMENT_START}..{DEVELOPMENT_END}",
                        "embargo": f"{EMBARGO_START}..{EMBARGO_END}",
                        "holdout_start": HOLDOUT_START,
                    },
                    "stress_annual_bps": STRESS_ANNUAL_BPS,
                    "placebo": "sign_flip_accounting_factor_sleeve",
                }
            )
            output.append(
                AccountingFactorCandidate(
                    candidate_id=(
                        f"accounting-factor-{profile}-scale{int(scale * 100):03d}-"
                        f"{digest[7:19]}"
                    ),
                    trial_index=len(output) + 1,
                    policy=policy,
                    strategy_fingerprint=digest,
                )
            )
    if len(output) != EXPECTED_CANDIDATES:
        raise RuntimeError("accounting factor candidate count contract violated")
    if len({row.candidate_id for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("accounting factor candidate ids are not unique")
    if len({row.strategy_fingerprint for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("accounting factor fingerprints are not unique")
    return tuple(output)


def parse_fama_french_five_factor_zip(raw: bytes) -> tuple[AccountingFactorMonth, ...]:
    """Parse only the monthly table from the official five-factor ZIP."""

    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError("Fama-French ZIP must contain exactly one CSV")
            content = archive.read(names[0])
    except zipfile.BadZipFile as exc:
        raise ValueError("Fama-French payload is not a valid ZIP") from exc
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    records = list(csv.reader(io.StringIO(text)))
    required = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    header_index: int | None = None
    positions: list[int] = []
    for index, record in enumerate(records):
        normalized = [cell.strip() for cell in record]
        if all(name in normalized for name in required):
            header_index = index
            positions = [normalized.index(name) for name in required]
            break
    if header_index is None or len(positions) != len(required):
        raise ValueError("Fama-French required columns are missing")

    rows: list[AccountingFactorMonth] = []
    for record in records[header_index + 1 :]:
        if not record:
            if rows:
                break
            continue
        month_token = record[0].strip()
        if not re.fullmatch(r"\d{6}", month_token):
            if rows:
                break
            continue
        if max(positions) >= len(record):
            raise ValueError("Fama-French monthly row has missing columns")
        try:
            raw_values = [float(record[position].strip()) for position in positions]
        except ValueError as exc:
            raise ValueError("Fama-French monthly values must be finite numbers") from exc
        if any(value in {-99.99, -999.0} for value in raw_values):
            raise ValueError("Fama-French monthly row contains a missing sentinel")
        if not all(math.isfinite(value) for value in raw_values):
            raise ValueError("Fama-French monthly values must be finite")
        year, month = int(month_token[:4]), int(month_token[4:])
        if month < 1 or month > 12:
            raise ValueError("Fama-French monthly date is invalid")
        values = [value / 100.0 for value in raw_values]
        if any(value <= -1.0 for value in values):
            raise ValueError("Fama-French monthly returns must be greater than -1")
        rows.append(AccountingFactorMonth(date(year, month, 1), *values))
    if not rows:
        raise ValueError("Fama-French monthly table is empty")
    months = [row.observed_month for row in rows]
    if len(set(months)) != len(months):
        raise ValueError("Fama-French monthly date is duplicated")
    if months != sorted(months):
        raise ValueError("Fama-French monthly dates must increase")
    return tuple(rows)


def _validate_rows(rows: Sequence[AccountingFactorMonth], *, label: str) -> None:
    if not rows:
        raise ValueError(f"{label} monthly rows are empty")
    months = [row.observed_month for row in rows]
    if len(set(months)) != len(months):
        raise ValueError(f"{label} monthly date is duplicated")
    if months != sorted(months):
        raise ValueError(f"{label} monthly dates must increase")
    if any(
        not math.isfinite(value) or value <= -1.0
        for row in rows
        for value in (
            row.market_excess,
            row.size,
            row.value,
            row.profitability,
            row.investment,
            row.cash,
        )
    ):
        raise ValueError(f"{label} monthly returns must be finite and greater than -1")


def build_accounting_factor_bundle(
    archive_rows: Sequence[AccountingFactorMonth],
    current_rows: Sequence[AccountingFactorMonth],
    *,
    archive_digest: str,
    current_digest: str,
    current_date: date,
) -> AccountingFactorBundle:
    if not archive_digest.startswith("sha256:") or not current_digest.startswith("sha256:"):
        raise ValueError("accounting factor data digests must be SHA-256")
    _validate_rows(archive_rows, label="archive")
    _validate_rows(current_rows, label="current")
    current_month = current_date.strftime("%Y-%m")
    complete_current = tuple(
        row for row in current_rows if _month_key(row.observed_month) != current_month
    )
    dropped = current_month if len(complete_current) != len(current_rows) else None
    archive_by_month = {_month_key(row.observed_month): row for row in archive_rows}
    current_by_month = {_month_key(row.observed_month): row for row in complete_current}
    expected_development = _expected_months(DEVELOPMENT_START, DEVELOPMENT_END)
    expected_embargo = _expected_months(EMBARGO_START, EMBARGO_END)
    archive_dev = [month for month in expected_development if month in archive_by_month]
    current_dev = [month for month in expected_development if month in current_by_month]
    if archive_dev != expected_development or current_dev != expected_development:
        raise ValueError("archive and current development month set must be complete and identical")
    if any(month not in archive_by_month for month in expected_embargo):
        raise ValueError("archive embargo month set is incomplete")
    holdout_months = sorted(month for month in current_by_month if month >= HOLDOUT_START)
    if len(holdout_months) < 120:
        raise ValueError("current holdout month set is incomplete")

    revision_count = 0
    max_abs_revision = 0.0
    for month in expected_development:
        archive = archive_by_month[month]
        current = current_by_month[month]
        differences = [
            abs(left - right)
            for left, right in zip(
                (
                    archive.market_excess,
                    archive.size,
                    archive.value,
                    archive.profitability,
                    archive.investment,
                    archive.cash,
                ),
                (
                    current.market_excess,
                    current.size,
                    current.value,
                    current.profitability,
                    current.investment,
                    current.cash,
                ),
                strict=True,
            )
        ]
        month_max = max(differences)
        if month_max > 0:
            revision_count += 1
            max_abs_revision = max(max_abs_revision, month_max)

    development = tuple(archive_by_month[month] for month in expected_development)
    embargo = tuple(archive_by_month[month] for month in expected_embargo)
    holdout = tuple(current_by_month[month] for month in holdout_months)
    quality: dict[str, object] = {
        "complete": True,
        "chronology_passed": True,
        "schema_passed": True,
        "archive_source_url": ARCHIVE_URL,
        "current_source_url": CURRENT_URL,
        "archive_content_digest": archive_digest,
        "current_content_digest": current_digest,
        "archive_row_count": len(archive_rows),
        "current_complete_row_count": len(complete_current),
        "development_revision_count": revision_count,
        "development_max_abs_revision": max_abs_revision,
        "development_month_sets_identical": True,
        "latest_complete_month": holdout_months[-1],
        "dropped_incomplete_month": dropped,
        "point_in_time_factor_returns": True,
        "point_in_time_constituents": False,
        "revision_limitation": (
            "development selection uses the July 2015 vintage; current holdout uses the "
            "latest file, while constituent membership is not exposed"
        ),
    }
    return AccountingFactorBundle(development, embargo, holdout, quality)


def _segments(returns: Sequence[float], count: int = 10) -> list[list[float]]:
    size = len(returns) // count
    if size < 2:
        return []
    return [
        list(returns[index * size : (index + 1) * size if index < count - 1 else len(returns)])
        for index in range(count)
    ]


def _monthly_factors(
    rows: Sequence[AccountingFactorMonth],
    policy: AccountingFactorPolicy,
    *,
    annual_cost_bps: int,
    sign: float = 1.0,
) -> dict[str, list[float] | list[str]]:
    strategy: list[float] = []
    cash: list[float] = []
    market: list[float] = []
    excess: list[float] = []
    months: list[str] = []
    monthly_cost = annual_cost_bps / 10_000.0 / 12.0
    for row in rows:
        sleeve = policy.sleeve_scale * sign * sum(
            weight * factor
            for weight, factor in zip(
                policy.weights,
                (row.value, row.profitability, row.investment),
                strict=True,
            )
        )
        strategy_factor = 1.0 + row.cash + sleeve - monthly_cost
        cash_factor = 1.0 + row.cash
        market_factor = 1.0 + row.cash + row.market_excess
        if min(strategy_factor, cash_factor, market_factor) <= 0:
            raise ValueError("accounting factor cost model produced a non-positive factor")
        months.append(_month_key(row.observed_month))
        strategy.append(strategy_factor)
        cash.append(cash_factor)
        market.append(market_factor)
        excess.append(strategy_factor / cash_factor - 1.0)
    return {
        "months": months,
        "strategy": strategy,
        "cash": cash,
        "market": market,
        "excess": excess,
    }


def _annualized_excess(strategy: Sequence[float], cash: Sequence[float]) -> float:
    if not strategy or len(strategy) != len(cash):
        return -1.0
    relative = math.prod(a / b for a, b in zip(strategy, cash, strict=True))
    return relative ** (12.0 / len(strategy)) - 1.0 if relative > 0 else -1.0


def _max_drawdown(factors: Sequence[float]) -> float:
    peak = 1.0
    level = 1.0
    worst = 0.0
    for factor in factors:
        level *= factor
        peak = max(peak, level)
        worst = min(worst, level / peak - 1.0)
    return abs(worst)


def _concentration_by_year(months: Sequence[str], excess: Sequence[float]) -> float:
    yearly: dict[str, float] = defaultdict(float)
    for month, value in zip(months, excess, strict=True):
        yearly[month[:4]] += value
    positive = [value for value in yearly.values() if value > 0]
    return max(positive) / sum(positive) if positive else 1.0


def _top_month_concentration(excess: Sequence[float]) -> float:
    positive = sorted((value for value in excess if value > 0), reverse=True)
    return sum(positive[:5]) / sum(positive) if positive else 1.0


def _gate(
    gate_id: str,
    passed: bool,
    actual: object,
    required: object,
    *,
    blocking: bool = True,
) -> dict[str, object]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "actual": str(actual),
        "required": str(required),
        "blocking": blocking,
    }


def _calibration_valid(payload: Mapping[str, object], *, code_commit: str) -> bool:
    scenario = payload.get("scenario")
    thresholds = payload.get("thresholds")
    required = payload.get("required")
    families = payload.get("family_calibrations")
    if not all(isinstance(row, Mapping) for row in (scenario, thresholds, required, families)):
        return False
    family16 = families.get("16")
    family64 = families.get("64")
    if not isinstance(family16, Mapping) or not isinstance(family64, Mapping):
        return False
    try:
        return bool(
            payload.get("research_entry_gate_version") == GATE_VERSION
            and payload.get("verdict") == "CALIBRATED"
            and payload.get("code_commit") == code_commit
            and int(scenario.get("seed", -1)) == 60_000
            and int(scenario.get("repetitions", 0)) >= 500
            and float(thresholds.get("holdout_psr_min", -1)) == 0.95
            and float(thresholds.get("research_entry_pbo_max", -1)) == 0.25
            and float(required.get("family_false_acceptance_max", -1)) == 0.01
            and float(required.get("detection_min", -1)) >= 0.80
            and float(required.get("program_false_acceptance_budget", -1)) == 0.20
            and int(required.get("maximum_research_families", -1)) == 20
            and all(
                row.get("research_entry_calibrated") is True
                and float(row.get("null_research_entry_acceptance_rate", 1)) <= 0.01
                and float(row.get("target_research_entry_detection_rate", 0)) >= 0.80
                for row in (family16, family64)
            )
        )
    except (TypeError, ValueError):
        return False


def _validate_prior(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if len(rows) != EXPECTED_PRIOR_TRIALS:
        raise ValueError("prior audit must contain exactly 784 rows")
    output = [dict(row) for row in rows]
    identities: list[tuple[str, str]] = []
    for row in output:
        if row.get("status") not in {"complete", "EXPLORATORY_REJECTED"}:
            raise ValueError("prior audit contains an incomplete row")
        candidate_id = row.get("candidate_id")
        fingerprint = row.get("strategy_fingerprint")
        if not isinstance(candidate_id, str) or not isinstance(fingerprint, str):
            raise ValueError("prior audit identity is incomplete")
        identities.append((candidate_id, fingerprint))
    if len(set(identities)) != len(identities) or len({row[1] for row in identities}) != len(rows):
        raise ValueError("prior audit identities and fingerprints must be unique")
    family_audit = build_research_family_audit(output)
    if len(family_audit) != EXPECTED_PRIOR_FAMILIES:
        raise ValueError("prior audit must reconstruct exactly 19 research families")
    return output


def run_accounting_factor_factory(
    *,
    bundle: AccountingFactorBundle,
    prior_audit_records: Sequence[Mapping[str, object]],
    calibration: Mapping[str, object],
    code_commit: str,
    generated_at: str,
) -> dict[str, object]:
    if bundle.quality.get("complete") is not True:
        raise ValueError("accounting factor bundle is incomplete")
    candidates = generate_accounting_factor_candidates()
    if len(bundle.development) != 606 or len(bundle.embargo) != 12 or len(bundle.holdout) < 120:
        raise ValueError("accounting factor development, embargo, or holdout split is incomplete")

    analyses: list[dict[str, object]] = []
    development_returns: list[list[float]] = []
    development_segments: list[list[float]] = []
    for candidate in candidates:
        development = _monthly_factors(
            bundle.development,
            candidate.policy,
            annual_cost_bps=PRIMARY_ANNUAL_BPS,
        )
        development_excess = [float(value) for value in development["excess"]]
        segment_sharpes = [annualized_sharpe(row) for row in _segments(development_excess)]
        if len(segment_sharpes) != 10:
            raise ValueError("accounting factor development needs ten complete segments")
        development_returns.append(development_excess)
        development_segments.append(segment_sharpes)
        analyses.append(
            {
                "candidate": candidate,
                "development_excess": development_excess,
                "development_sharpe": annualized_sharpe(development_excess),
                "segment_sharpes": segment_sharpes,
            }
        )

    winner_index = max(
        range(len(analyses)),
        key=lambda index: (float(analyses[index]["development_sharpe"]), -index),
    )
    winner = analyses[winner_index]
    winner_candidate = winner["candidate"]
    assert isinstance(winner_candidate, AccountingFactorCandidate)
    trial_sharpes = [float(row["development_sharpe"]) for row in analyses]
    pbo = probability_of_backtest_overfitting(development_segments)
    effective_trials = effective_independent_trials(development_returns)
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index],
        trial_sharpes,
        effective_trial_count=effective_trials,
    )

    primary = _monthly_factors(
        bundle.holdout,
        winner_candidate.policy,
        annual_cost_bps=PRIMARY_ANNUAL_BPS,
    )
    stress300 = _monthly_factors(
        bundle.holdout,
        winner_candidate.policy,
        annual_cost_bps=300,
    )
    stress500 = _monthly_factors(
        bundle.holdout,
        winner_candidate.policy,
        annual_cost_bps=500,
    )
    placebo = _monthly_factors(
        bundle.holdout,
        winner_candidate.policy,
        annual_cost_bps=PRIMARY_ANNUAL_BPS,
        sign=-1.0,
    )
    holdout_months = [str(value) for value in primary["months"]]
    holdout_strategy = [float(value) for value in primary["strategy"]]
    holdout_cash = [float(value) for value in primary["cash"]]
    holdout_excess = [float(value) for value in primary["excess"]]
    holdout_psr = probabilistic_sharpe(holdout_excess)
    annual_excess = _annualized_excess(holdout_strategy, holdout_cash)

    era_ranges = (
        ("2015-01", "2017-12"),
        ("2018-01", "2020-12"),
        ("2021-01", "2023-12"),
        ("2024-01", "9999-12"),
    )
    era_excess: dict[str, float] = {}
    for start, end in era_ranges:
        indexes = [index for index, month in enumerate(holdout_months) if start <= month <= end]
        era_excess[f"{start[:4]}-{end[:4]}"] = _annualized_excess(
            [holdout_strategy[index] for index in indexes],
            [holdout_cash[index] for index in indexes],
        )
    positive_eras = sum(value > 0 for value in era_excess.values())

    recent_wins: list[float] = []
    if len(holdout_months) >= 108:
        first = len(holdout_months) - 108
        for offset in range(0, 108, 36):
            indexes = list(range(first + offset, first + offset + 36))
            recent_wins.append(
                _annualized_excess(
                    [holdout_strategy[index] for index in indexes],
                    [holdout_cash[index] for index in indexes],
                )
            )
    positive_recent = sum(value > 0 for value in recent_wins)
    year_concentration = _concentration_by_year(holdout_months, holdout_excess)
    month_concentration = _top_month_concentration(holdout_excess)
    strategy_drawdown = _max_drawdown(holdout_strategy)
    stress300_excess = _annualized_excess(
        [float(value) for value in stress300["strategy"]],
        [float(value) for value in stress300["cash"]],
    )
    stress500_excess = _annualized_excess(
        [float(value) for value in stress500["strategy"]],
        [float(value) for value in stress500["cash"]],
    )
    placebo_excess = [float(value) for value in placebo["excess"]]
    placebo_psr = probabilistic_sharpe(placebo_excess)
    placebo_annual_excess = _annualized_excess(
        [float(value) for value in placebo["strategy"]],
        [float(value) for value in placebo["cash"]],
    )
    placebo_core_passed = bool(
        placebo_psr is not None
        and placebo_psr >= Decimal("0.95")
        and placebo_annual_excess >= 0.01
    )

    trial_records: list[dict[str, object]] = []
    for index, analysis in enumerate(analyses):
        candidate = analysis["candidate"]
        assert isinstance(candidate, AccountingFactorCandidate)
        candidate_holdout = _monthly_factors(
            bundle.holdout,
            candidate.policy,
            annual_cost_bps=PRIMARY_ANNUAL_BPS,
        )
        record = candidate.as_dict()
        record.update(
            {
                "status": "complete",
                "development_sharpe": analysis["development_sharpe"],
                "segment_sharpes": analysis["segment_sharpes"],
                "holdout_psr": _decimal(
                    probabilistic_sharpe([float(value) for value in candidate_holdout["excess"]])
                ),
                "selected_by_development": index == winner_index,
                "holdout_inspected_after_selection": True,
                "archive_data_fingerprint": bundle.quality.get("archive_content_digest"),
                "current_data_fingerprint": bundle.quality.get("current_content_digest"),
            }
        )
        trial_records.append(record)

    prior = _validate_prior(prior_audit_records)
    audit_records = annotate_research_families(prior + trial_records)
    trial_records = audit_records[-EXPECTED_CANDIDATES:]
    family_audit = build_research_family_audit(audit_records)
    identities = [
        (str(row["candidate_id"]), str(row["strategy_fingerprint"]))
        for row in audit_records
    ]
    if (
        len(audit_records) != EXPECTED_GLOBAL_AUDIT_TRIALS
        or len(set(identities)) != EXPECTED_GLOBAL_AUDIT_TRIALS
        or len({fingerprint for _, fingerprint in identities}) != EXPECTED_GLOBAL_AUDIT_TRIALS
    ):
        raise ValueError("global research audit must contain 800 unique identities")
    if len(family_audit) != EXPECTED_PROGRAM_FAMILIES:
        raise ValueError("global research audit must reconstruct exactly 20 families")

    calibration_passed = _calibration_valid(calibration, code_commit=code_commit)
    gates = [
        _gate("complete_family_trials", True, 16, 16),
        _gate("prior_audit_complete", True, 784, 784),
        _gate("global_audit_trials", True, 800, 800),
        _gate("unique_audit_fingerprints", True, 800, 800),
        _gate("program_research_families", True, 20, 20),
        _gate("program_false_acceptance_bound", True, 0.20, "<=0.20"),
        _gate("repository_calibration", calibration_passed, calibration_passed, True),
        _gate("family_pbo", pbo is not None and pbo <= Decimal("0.25"), pbo, "<=0.25"),
        _gate(
            "holdout_excess_psr",
            holdout_psr is not None and holdout_psr >= Decimal("0.95"),
            holdout_psr,
            ">=0.95",
        ),
        _gate("holdout_annual_excess", annual_excess >= 0.01, annual_excess, ">=0.01"),
        _gate("positive_eras", positive_eras >= 3, positive_eras, ">=3/4"),
        _gate("recent_36m_wins", positive_recent >= 2, positive_recent, ">=2/3"),
        _gate(
            "single_year_concentration",
            year_concentration <= 0.25,
            year_concentration,
            "<=0.25",
        ),
        _gate(
            "top_five_month_concentration",
            month_concentration <= 0.50,
            month_concentration,
            "<=0.50",
        ),
        _gate("max_drawdown", strategy_drawdown <= 0.30, strategy_drawdown, "<=0.30"),
        _gate("stress_300bps_positive", stress300_excess > 0, stress300_excess, ">0"),
        _gate(
            "sign_flipped_placebo_fails_core",
            not placebo_core_passed,
            placebo_core_passed,
            False,
        ),
    ]
    historical_passed = all(bool(row["passed"]) for row in gates)
    paper_passed = bool(
        calibration_passed
        and pbo is not None
        and pbo <= Decimal("0.25")
        and holdout_psr is not None
        and holdout_psr >= Decimal("0.80")
        and annual_excess > 0
        and stress300_excess > 0
        and not placebo_core_passed
    )
    verdict = (
        FACTORY_EDGE
        if historical_passed
        else PAPER_CHALLENGER
        if paper_passed
        else NO_FACTORY_EDGE
    )
    selected_candidate_id = winner_candidate.candidate_id if historical_passed else None
    selected_fingerprint = winner_candidate.strategy_fingerprint if historical_passed else None
    data_fingerprint = _fingerprint(
        {
            "archive": bundle.quality.get("archive_content_digest"),
            "current": bundle.quality.get("current_content_digest"),
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_version": GATE_VERSION,
        "family_id": FAMILY_ID,
        "code_commit": code_commit,
        "generated_at": generated_at,
        "timestamp_utc": generated_at,
        "batch_id": f"accounting-factor-{data_fingerprint[7:19]}-{code_commit[:12]}",
        "accounting_factor_data_fingerprint": data_fingerprint,
        "candidate_count": EXPECTED_CANDIDATES,
        "complete_trial_count": EXPECTED_CANDIDATES,
        "multiplicity_trial_count": EXPECTED_CANDIDATES,
        "prior_trial_count": EXPECTED_PRIOR_TRIALS,
        "global_audit_trial_count": EXPECTED_GLOBAL_AUDIT_TRIALS,
        "unique_trial_fingerprint_count": EXPECTED_GLOBAL_AUDIT_TRIALS,
        "program_research_family_count": EXPECTED_PROGRAM_FAMILIES,
        "program_multiplicity": {
            "method": "calibrated-family-risk-budget-v1",
            "per_family_false_acceptance_max": "0.01",
            "program_false_acceptance_bound": "0.20",
            "program_false_acceptance_budget": "0.20",
            "maximum_research_families": 20,
            "next_family_requires_recalibration": True,
        },
        "data_quality": bundle.quality,
        "split": {
            "development_start": DEVELOPMENT_START,
            "development_end": DEVELOPMENT_END,
            "embargo_start": EMBARGO_START,
            "embargo_end": EMBARGO_END,
            "holdout_start": HOLDOUT_START,
            "holdout_end": holdout_months[-1],
            "development_months": len(bundle.development),
            "embargo_months": len(bundle.embargo),
            "holdout_months": len(bundle.holdout),
        },
        "candidate_registry": [row.as_dict() for row in candidates],
        "trial_records": trial_records,
        "audit_records": audit_records,
        "research_family_audit": family_audit,
        "development_returns": development_returns,
        "development_segment_sharpes": development_segments,
        "development_selection": {
            "method": "maximum_primary_cost_sharpe_on_archive_development_only",
            "selected_candidate_id": winner_candidate.candidate_id,
            "selected_strategy_fingerprint": winner_candidate.strategy_fingerprint,
            "selected_trial_index": winner_candidate.trial_index,
            "holdout_used_for_selection": False,
            "archive_vintage": "July 2015 data cut released August 2015",
        },
        "repository_gate_calibration": dict(calibration),
        "criterion_audit": {
            "threshold_change_after_results": False,
            "prior_candidate_reclassification": False,
            "historical_reuse": False,
            "public_history_point_in_time": False,
            "benchmark_execution_parity": False,
        },
        "holdout": {
            "psr": _decimal(holdout_psr),
            "primary_150bps_annual_cash_excess": annual_excess,
            "annual_cash_excess": annual_excess,
            "era_annual_excess": era_excess,
            "positive_eras": positive_eras,
            "recent_36m_annual_excess": recent_wins,
            "recent_36m_wins": positive_recent,
            "single_year_positive_contribution": year_concentration,
            "top_five_month_positive_contribution": month_concentration,
            "strategy_max_drawdown": strategy_drawdown,
            "stress_300bps_annual_cash_excess": stress300_excess,
            "stress_500bps_annual_cash_excess": stress500_excess,
            "sign_flipped_placebo_psr": _decimal(placebo_psr),
            "sign_flipped_placebo_annual_cash_excess": placebo_annual_excess,
            "sign_flipped_placebo_core_passed": placebo_core_passed,
        },
        "research_live_parity": {
            "passed": False,
            "candidate_id": selected_candidate_id,
            "strategy_fingerprint": selected_fingerprint,
            "reason": (
                "official factor returns do not provide point-in-time constituents, exact "
                "sizes, short-borrow feasibility, integer-share orders, or broker execution parity"
            ),
        },
        "promotion_allowed": False,
        "decision": {
            "verdict": verdict,
            "historical_edge_passed": historical_passed,
            "provisional_best_candidate_id": winner_candidate.candidate_id,
            "selected_candidate_id": selected_candidate_id,
            "selected_strategy_fingerprint": selected_fingerprint,
            "selected_deploy_config": None,
            "research_canary_eligible": False,
            "promotion_allowed": False,
            "psr": _decimal(holdout_psr),
            "dsr": _decimal(dsr),
            "pbo": _decimal(pbo),
            "gates": gates,
            "failed_gates": [str(row["gate_id"]) for row in gates if not row["passed"]],
            "paper_gates_passed": paper_passed,
            "next_strategy_family": "post-earnings-announcement-drift-after-recalibration",
            "search_space_exhausted": False,
        },
        "safety": {
            "orders_submitted": 0,
            "capital_changed": False,
            "live_strategy_changed": False,
        },
    }


def render_accounting_factor_markdown(payload: Mapping[str, object]) -> str:
    decision = payload.get("decision")
    holdout = payload.get("holdout")
    data = payload.get("data_quality")
    if not isinstance(decision, Mapping) or not isinstance(holdout, Mapping):
        raise ValueError("accounting factor result is incomplete")
    data = data if isinstance(data, Mapping) else {}
    failed = decision.get("failed_gates")
    failed_text = ", ".join(str(value) for value in failed) if isinstance(failed, list) else ""
    return "\n".join(
        [
            "# 자동 전략 공장 - 회계 기반 횡단면 팩터",
            "",
            f"- 역사 판정: `{decision.get('verdict')}`",
            f"- 개발 선택 후보: `{decision.get('provisional_best_candidate_id')}`",
            f"- 역사 전체 합격: `{decision.get('historical_edge_passed')}`",
            f"- 연구 캐너리 적격: `{decision.get('research_canary_eligible')}`",
            f"- 현재 실자본 승격: `{decision.get('promotion_allowed')}`",
            f"- PBO: `{decision.get('pbo')}`",
            f"- 홀드아웃 PSR: `{decision.get('psr')}`",
            f"- 연 1.5% 비용 후 현금 초과수익: `{holdout.get('annual_cash_excess')}`",
            f"- 연 3% 비용 후 현금 초과수익: `{holdout.get('stress_300bps_annual_cash_excess')}`",
            f"- 실패 관문: `{failed_text or '없음'}`",
            f"- 보관본 SHA-256: `{data.get('archive_content_digest')}`",
            f"- 최신본 SHA-256: `{data.get('current_content_digest')}`",
            f"- 과거값 재구성 월 수: `{data.get('development_revision_count')}`",
            "- 안전: 주문 0건, 자본 변경 없음, 라이브 전략 변경 없음",
            "- 주의: 역사 합격과 현재 계좌 실행 가능성은 다른 상태입니다.",
        ]
    )


__all__ = [
    "ARCHIVE_URL",
    "CURRENT_URL",
    "EXPECTED_CANDIDATES",
    "EXPECTED_GLOBAL_AUDIT_TRIALS",
    "EXPECTED_PROGRAM_FAMILIES",
    "AccountingFactorBundle",
    "AccountingFactorCandidate",
    "AccountingFactorMonth",
    "AccountingFactorPolicy",
    "build_accounting_factor_bundle",
    "generate_accounting_factor_candidates",
    "parse_fama_french_five_factor_zip",
    "render_accounting_factor_markdown",
    "run_accounting_factor_factory",
]
