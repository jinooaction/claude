"""Spec 173: preregistered U.S. equity turn-of-month research factory.

The module is deliberately research-only.  It reads public factor returns, builds
the frozen 4 x 4 calendar family, and emits evidence without broker or live
configuration access.
"""

from __future__ import annotations

import hashlib
import json
import math
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
from auto_invest.analytics.options_variance_risk_premium_factory import (
    FRENCH_DAILY_URL,
    FrenchDailyFactor,
)
from auto_invest.analytics.research_family_audit import (
    annotate_research_families,
    build_research_family_audit,
)

SCHEMA_VERSION = "1.0"
GATE_VERSION = "3.1"
FAMILY_ID = "equity-calendar-turn-of-month"
EXPECTED_CANDIDATES = 16
EXPECTED_CENTRAL_PRIOR_TRIALS = 752
EXPECTED_RESTORED_REGIME_TRIALS = 16
EXPECTED_PRIOR_TRIALS = 768
EXPECTED_GLOBAL_AUDIT_TRIALS = 784
EXPECTED_PROGRAM_FAMILIES = 19
DEVELOPMENT_START = date(1926, 7, 1)
DEVELOPMENT_END = date(2005, 12, 31)
EMBARGO_START = date(2006, 1, 1)
EMBARGO_END = date(2006, 12, 31)
HOLDOUT_START = date(2007, 1, 1)
PRIMARY_ONE_WAY_BPS = 10
STRESS_ONE_WAY_BPS = (25, 50)
ANNUAL_FIXED_BPS = 50
PLACEBO_SHIFT_SESSIONS = 10
FACTORY_EDGE = "FACTORY_EDGE"
PAPER_CHALLENGER = "PAPER_CHALLENGER"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True)
class CalendarPolicy:
    last_sessions: int
    first_sessions: int
    one_way_cost_bps: int = PRIMARY_ONE_WAY_BPS
    annual_fixed_cost_bps: int = ANNUAL_FIXED_BPS

    def as_dict(self) -> dict[str, object]:
        return {
            "last_sessions": self.last_sessions,
            "first_sessions": self.first_sessions,
            "one_way_cost_bps": self.one_way_cost_bps,
            "annual_fixed_cost_bps": self.annual_fixed_cost_bps,
            "signal": "market_on_month_boundary_else_cash",
        }


@dataclass(frozen=True)
class CalendarCandidate:
    candidate_id: str
    trial_index: int
    policy: CalendarPolicy
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "policy": self.policy.as_dict(),
            "strategy_fingerprint": self.strategy_fingerprint,
            "research_proxy": "Kenneth French U.S. market factor",
            "intended_signal_instrument": "SPY",
            "current_broker_proxy": "SCHX",
            "live_expressible": False,
            "live_blocker": (
                "research index to executable instrument parity, calendar scheduler, "
                "order policy, and canary evidence are not implemented"
            ),
        }


@dataclass(frozen=True)
class FrenchDailyBundle:
    rows: tuple[FrenchDailyFactor, ...]
    quality: dict[str, object]


def generate_calendar_candidates() -> tuple[CalendarCandidate, ...]:
    output: list[CalendarCandidate] = []
    for last_sessions in range(1, 5):
        for first_sessions in range(1, 5):
            policy = CalendarPolicy(last_sessions, first_sessions)
            digest = _fingerprint(
                {
                    "schema_version": SCHEMA_VERSION,
                    "family_id": FAMILY_ID,
                    "policy": policy.as_dict(),
                    "data": "Fama-French daily Mkt-RF plus RF",
                    "split": {
                        "development_end": DEVELOPMENT_END.isoformat(),
                        "embargo": "2006",
                        "holdout_start": HOLDOUT_START.isoformat(),
                    },
                    "stress_one_way_bps": STRESS_ONE_WAY_BPS,
                    "placebo_shift_sessions": PLACEBO_SHIFT_SESSIONS,
                }
            )
            output.append(
                CalendarCandidate(
                    candidate_id=(
                        f"calendar-turn-last{last_sessions}-first{first_sessions}-"
                        f"{digest[7:19]}"
                    ),
                    trial_index=len(output) + 1,
                    policy=policy,
                    strategy_fingerprint=digest,
                )
            )
    if len(output) != EXPECTED_CANDIDATES:
        raise RuntimeError("turn-of-month candidate count contract violated")
    if len({row.candidate_id for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("turn-of-month candidate ids are not unique")
    if len({row.strategy_fingerprint for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("turn-of-month fingerprints are not unique")
    return tuple(output)


def build_french_daily_bundle(
    rows: Sequence[FrenchDailyFactor],
    *,
    content_digest: str,
    current_date: date,
) -> FrenchDailyBundle:
    """Validate chronology and drop the current, necessarily incomplete month."""

    if not content_digest.startswith("sha256:"):
        raise ValueError("Fama-French content digest must be SHA-256")
    dates = [row.observed_date for row in rows]
    if len(set(dates)) != len(dates):
        raise ValueError("Fama-French daily date is duplicated")
    if dates != sorted(dates):
        raise ValueError("Fama-French daily dates must increase")
    current_month = _month_key(current_date)
    complete_rows = tuple(row for row in rows if _month_key(row.observed_date) != current_month)
    if len(complete_rows) < 2:
        raise ValueError("Fama-French daily coverage is incomplete")
    if complete_rows[0].observed_date > DEVELOPMENT_START:
        raise ValueError("Fama-French daily development coverage is incomplete")
    if complete_rows[-1].observed_date < HOLDOUT_START:
        raise ValueError("Fama-French daily holdout coverage is incomplete")
    if any(
        not math.isfinite(value) or value <= -1.0
        for row in complete_rows
        for value in (row.market_return, row.cash_return)
    ):
        raise ValueError("Fama-French daily returns must be finite and greater than -1")
    dropped = current_month if len(complete_rows) != len(rows) else None
    quality: dict[str, object] = {
        "complete": True,
        "chronology_passed": True,
        "schema_passed": True,
        "source_url": FRENCH_DAILY_URL,
        "content_digest": content_digest,
        "row_count": len(complete_rows),
        "first_date": complete_rows[0].observed_date.isoformat(),
        "last_date": complete_rows[-1].observed_date.isoformat(),
        "latest_complete_month": _month_key(complete_rows[-1].observed_date),
        "dropped_incomplete_month": dropped,
        "point_in_time": False,
        "revision_limitation": "current public history is source-hashed, not a vintage archive",
    }
    return FrenchDailyBundle(complete_rows, quality)


def _active_sessions(
    rows: Sequence[FrenchDailyFactor], policy: CalendarPolicy
) -> list[bool]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[_month_key(row.observed_date)].append(index)
    active = [False] * len(rows)
    for indexes in grouped.values():
        for local_index, global_index in enumerate(indexes):
            active[global_index] = bool(
                local_index < policy.first_sessions
                or local_index >= len(indexes) - policy.last_sessions
            )
    return active


def _monthly_factors(
    rows: Sequence[FrenchDailyFactor],
    active: Sequence[bool],
    *,
    one_way_cost_bps: int,
) -> dict[str, dict[str, float]]:
    if len(rows) != len(active):
        raise ValueError("turn-of-month signal and daily rows must align")
    output: dict[str, dict[str, float]] = {}
    previous = False
    transition_cost = one_way_cost_bps / 10_000.0
    daily_fixed_cost = ANNUAL_FIXED_BPS / 10_000.0 / 252.0
    for row, is_active in zip(rows, active, strict=True):
        month = _month_key(row.observed_date)
        bucket = output.setdefault(
            month,
            {"strategy_factor": 1.0, "cash_factor": 1.0, "market_factor": 1.0},
        )
        factor = 1.0 + (row.market_return if is_active else row.cash_return)
        if is_active:
            factor *= 1.0 - daily_fixed_cost
        if is_active != previous:
            factor *= 1.0 - transition_cost
        if factor <= 0 or not math.isfinite(factor):
            raise ValueError("turn-of-month cost model produced a non-positive factor")
        bucket["strategy_factor"] *= factor
        bucket["cash_factor"] *= 1.0 + row.cash_return
        bucket["market_factor"] *= 1.0 + row.market_return
        previous = is_active
    return output


def _shifted(active: Sequence[bool], sessions: int) -> list[bool]:
    return [False if index < sessions else active[index - sessions] for index in range(len(active))]


def _segments(returns: Sequence[float], count: int = 10) -> list[list[float]]:
    size = len(returns) // count
    if size < 2:
        return []
    return [
        list(returns[index * size : (index + 1) * size if index < count - 1 else len(returns)])
        for index in range(count)
    ]


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


def _restore_regime_rows(payload: Mapping[str, object]) -> list[dict[str, object]]:
    family_id = str(payload.get("family_id", ""))
    registry = payload.get("candidate_registry")
    if (
        not family_id.startswith("regime-adaptive-stock-bond-joint-weakness")
        or payload.get("candidate_count") != EXPECTED_RESTORED_REGIME_TRIALS
        or not isinstance(registry, list)
        or len(registry) != EXPECTED_RESTORED_REGIME_TRIALS
    ):
        raise ValueError("released regime result must contain exactly 16 registered candidates")
    restored: list[dict[str, object]] = []
    for row in registry:
        if not isinstance(row, Mapping):
            raise ValueError("released regime candidate registry is invalid")
        candidate_id = row.get("candidate_id")
        fingerprint = row.get("strategy_fingerprint") or row.get("candidate_fingerprint")
        if not isinstance(candidate_id, str) or not isinstance(fingerprint, str):
            raise ValueError("released regime candidate identity is incomplete")
        restored.append(
            {
                "candidate_id": candidate_id,
                "strategy_fingerprint": fingerprint,
                "status": "EXPLORATORY_REJECTED",
                "restored_from_released_result": True,
            }
        )
    return restored


def _validate_prior(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if len(rows) != EXPECTED_CENTRAL_PRIOR_TRIALS:
        raise ValueError("central prior audit must contain exactly 752 rows")
    output = [dict(row) for row in rows]
    for row in output:
        if row.get("status") not in {"complete", "EXPLORATORY_REJECTED"}:
            raise ValueError("central prior audit contains an incomplete row")
        if not row.get("candidate_id") or not row.get("strategy_fingerprint"):
            raise ValueError("central prior audit identity is incomplete")
    return output


def run_turn_of_month_equity_factory(
    *,
    bundle: FrenchDailyBundle,
    prior_audit_records: Sequence[Mapping[str, object]],
    released_regime_result: Mapping[str, object],
    calibration: Mapping[str, object],
    code_commit: str,
    generated_at: str,
) -> dict[str, object]:
    if bundle.quality.get("complete") is not True:
        raise ValueError("Fama-French daily bundle is incomplete")
    candidates = generate_calendar_candidates()
    months = sorted({_month_key(row.observed_date) for row in bundle.rows})
    development_months = [month for month in months if "1926-07" <= month <= "2005-12"]
    embargo_months = [month for month in months if "2006-01" <= month <= "2006-12"]
    holdout_months = [month for month in months if month >= "2007-01"]
    if len(development_months) < 900 or len(embargo_months) != 12 or len(holdout_months) < 120:
        raise ValueError("turn-of-month development, embargo, or holdout split is incomplete")

    analyses: list[dict[str, object]] = []
    development_returns: list[list[float]] = []
    development_segments: list[list[float]] = []
    for candidate in candidates:
        active = _active_sessions(bundle.rows, candidate.policy)
        primary = _monthly_factors(
            bundle.rows,
            active,
            one_way_cost_bps=PRIMARY_ONE_WAY_BPS,
        )
        stress25 = _monthly_factors(bundle.rows, active, one_way_cost_bps=25)
        stress50 = _monthly_factors(bundle.rows, active, one_way_cost_bps=50)
        placebo = _monthly_factors(
            bundle.rows,
            _shifted(active, PLACEBO_SHIFT_SESSIONS),
            one_way_cost_bps=PRIMARY_ONE_WAY_BPS,
        )
        dev_excess = [
            primary[month]["strategy_factor"] / primary[month]["cash_factor"] - 1.0
            for month in development_months
        ]
        segment_sharpes = [annualized_sharpe(row) for row in _segments(dev_excess)]
        if len(segment_sharpes) != 10:
            raise ValueError("turn-of-month development needs ten complete segments")
        development_returns.append(dev_excess)
        development_segments.append(segment_sharpes)
        analyses.append(
            {
                "candidate": candidate,
                "primary": primary,
                "stress25": stress25,
                "stress50": stress50,
                "placebo": placebo,
                "development_excess": dev_excess,
                "development_sharpe": annualized_sharpe(dev_excess),
                "segment_sharpes": segment_sharpes,
            }
        )

    winner_index = max(
        range(len(analyses)),
        key=lambda index: (float(analyses[index]["development_sharpe"]), -index),
    )
    winner = analyses[winner_index]
    winner_candidate = winner["candidate"]
    assert isinstance(winner_candidate, CalendarCandidate)
    trial_sharpes = [float(row["development_sharpe"]) for row in analyses]
    pbo = probability_of_backtest_overfitting(development_segments)
    effective_trials = effective_independent_trials(development_returns)
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index],
        trial_sharpes,
        effective_trial_count=effective_trials,
    )

    primary = winner["primary"]
    stress25 = winner["stress25"]
    stress50 = winner["stress50"]
    placebo = winner["placebo"]
    assert all(isinstance(row, Mapping) for row in (primary, stress25, stress50, placebo))
    holdout_strategy = [float(primary[month]["strategy_factor"]) for month in holdout_months]
    holdout_cash = [float(primary[month]["cash_factor"]) for month in holdout_months]
    holdout_market = [float(primary[month]["market_factor"]) for month in holdout_months]
    holdout_excess = [
        strategy / cash - 1.0
        for strategy, cash in zip(holdout_strategy, holdout_cash, strict=True)
    ]
    holdout_psr = probabilistic_sharpe(holdout_excess)
    annual_excess = _annualized_excess(holdout_strategy, holdout_cash)

    era_ranges = (
        ("2007-01", "2010-12"),
        ("2011-01", "2015-12"),
        ("2016-01", "2020-12"),
        ("2021-01", "9999-12"),
    )
    era_excess: dict[str, float] = {}
    for start, end in era_ranges:
        indexes = [index for index, month in enumerate(holdout_months) if start <= month <= end]
        era_excess[f"{start[:4]}-{end[:4]}"] = _annualized_excess(
            [holdout_strategy[index] for index in indexes],
            [holdout_cash[index] for index in indexes],
        )
    positive_eras = sum(value > 0 for value in era_excess.values())

    recent_indexes = list(range(max(0, len(holdout_months) - 108), len(holdout_months)))
    recent_wins: list[float] = []
    if len(recent_indexes) == 108:
        for start in range(0, 108, 36):
            indexes = recent_indexes[start : start + 36]
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
    market_drawdown = _max_drawdown(holdout_market)

    stress25_strategy = [float(stress25[month]["strategy_factor"]) for month in holdout_months]
    stress25_cash = [float(stress25[month]["cash_factor"]) for month in holdout_months]
    stress25_excess = _annualized_excess(stress25_strategy, stress25_cash)
    stress50_excess = _annualized_excess(
        [float(stress50[month]["strategy_factor"]) for month in holdout_months],
        [float(stress50[month]["cash_factor"]) for month in holdout_months],
    )
    placebo_strategy = [float(placebo[month]["strategy_factor"]) for month in holdout_months]
    placebo_cash = [float(placebo[month]["cash_factor"]) for month in holdout_months]
    placebo_excess_returns = [
        strategy / cash - 1.0
        for strategy, cash in zip(placebo_strategy, placebo_cash, strict=True)
    ]
    placebo_psr = probabilistic_sharpe(placebo_excess_returns)
    placebo_annual_excess = _annualized_excess(placebo_strategy, placebo_cash)
    placebo_core_passed = bool(
        placebo_psr is not None
        and placebo_psr >= Decimal("0.95")
        and placebo_annual_excess >= 0.005
    )

    trial_records: list[dict[str, object]] = []
    for index, analysis in enumerate(analyses):
        candidate = analysis["candidate"]
        assert isinstance(candidate, CalendarCandidate)
        candidate_primary = analysis["primary"]
        assert isinstance(candidate_primary, Mapping)
        candidate_holdout_excess = [
            float(candidate_primary[month]["strategy_factor"])
            / float(candidate_primary[month]["cash_factor"])
            - 1.0
            for month in holdout_months
        ]
        record = candidate.as_dict()
        record.update(
            {
                "status": "complete",
                "development_sharpe": analysis["development_sharpe"],
                "segment_sharpes": analysis["segment_sharpes"],
                "holdout_psr": _decimal(probabilistic_sharpe(candidate_holdout_excess)),
                "holdout_inspected_after_selection": True,
                "selected_by_development": index == winner_index,
            }
        )
        trial_records.append(record)

    prior = _validate_prior(prior_audit_records)
    restored_regime = _restore_regime_rows(released_regime_result)
    audit_records = annotate_research_families(prior + restored_regime + trial_records)
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
        raise ValueError("global research audit must contain 784 unique identities")
    if len(family_audit) != EXPECTED_PROGRAM_FAMILIES:
        raise ValueError("global research audit must reconstruct exactly 19 families")

    calibration_passed = _calibration_valid(calibration, code_commit=code_commit)
    gates = [
        _gate("complete_family_trials", True, 16, 16),
        _gate("prior_audit_complete", True, 768, 768),
        _gate("global_audit_trials", True, 784, 784),
        _gate("unique_audit_fingerprints", True, 784, 784),
        _gate("program_research_families", True, 19, 19),
        _gate("program_false_acceptance_bound", True, 0.19, "<=0.20"),
        _gate("repository_calibration", calibration_passed, calibration_passed, True),
        _gate("family_pbo", pbo is not None and pbo <= Decimal("0.25"), pbo, "<=0.25"),
        _gate(
            "holdout_excess_psr",
            holdout_psr is not None and holdout_psr >= Decimal("0.95"),
            holdout_psr,
            ">=0.95",
        ),
        _gate("holdout_annual_excess", annual_excess >= 0.005, annual_excess, ">=0.005"),
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
        _gate(
            "max_drawdown_vs_market",
            strategy_drawdown <= market_drawdown,
            strategy_drawdown,
            f"<={market_drawdown}",
        ),
        _gate("stress_25bps_positive", stress25_excess > 0, stress25_excess, ">0"),
        _gate(
            "shifted_placebo_fails_core",
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
        and stress25_excess > 0
        and not placebo_core_passed
    )
    if historical_passed:
        verdict = FACTORY_EDGE
    elif paper_passed:
        verdict = PAPER_CHALLENGER
    else:
        verdict = NO_FACTORY_EDGE
    selected_candidate_id = winner_candidate.candidate_id if historical_passed else None
    selected_fingerprint = winner_candidate.strategy_fingerprint if historical_passed else None

    return {
        "schema_version": SCHEMA_VERSION,
        "gate_version": GATE_VERSION,
        "family_id": FAMILY_ID,
        "code_commit": code_commit,
        "generated_at": generated_at,
        "timestamp_utc": generated_at,
        "batch_id": (
            "turn-of-month-"
            f"{str(bundle.quality.get('content_digest', 'unknown')).removeprefix('sha256:')[:12]}-"
            f"{code_commit[:12]}"
        ),
        "turn_of_month_data_fingerprint": bundle.quality.get("content_digest"),
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
            "program_false_acceptance_bound": "0.19",
            "program_false_acceptance_budget": "0.20",
        },
        "data_quality": bundle.quality,
        "split": {
            "development_start": DEVELOPMENT_START.isoformat(),
            "development_end": DEVELOPMENT_END.isoformat(),
            "embargo_start": EMBARGO_START.isoformat(),
            "embargo_end": EMBARGO_END.isoformat(),
            "holdout_start": HOLDOUT_START.isoformat(),
            "holdout_end": holdout_months[-1],
            "development_months": len(development_months),
            "embargo_months": len(embargo_months),
            "holdout_months": len(holdout_months),
        },
        "candidate_registry": [row.as_dict() for row in candidates],
        "trial_records": trial_records,
        "audit_records": audit_records,
        "research_family_audit": family_audit,
        "development_returns": development_returns,
        "development_segment_sharpes": development_segments,
        "development_selection": {
            "method": "maximum_primary_cost_active_sharpe_on_development_only",
            "selected_candidate_id": winner_candidate.candidate_id,
            "selected_strategy_fingerprint": winner_candidate.strategy_fingerprint,
            "selected_trial_index": winner_candidate.trial_index,
            "holdout_used_for_selection": False,
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
            "annual_cash_excess": annual_excess,
            "era_annual_excess": era_excess,
            "positive_eras": positive_eras,
            "recent_36m_annual_excess": recent_wins,
            "recent_36m_wins": positive_recent,
            "single_year_positive_contribution": year_concentration,
            "top_five_month_positive_contribution": month_concentration,
            "strategy_max_drawdown": strategy_drawdown,
            "market_max_drawdown": market_drawdown,
            "stress_25bps_annual_cash_excess": stress25_excess,
            "stress_50bps_annual_cash_excess": stress50_excess,
            "shifted_10_session_placebo_psr": _decimal(placebo_psr),
            "shifted_10_session_placebo_annual_cash_excess": placebo_annual_excess,
            "shifted_10_session_placebo_core_passed": placebo_core_passed,
        },
        "research_live_parity": {
            "passed": False,
            "candidate_id": selected_candidate_id,
            "strategy_fingerprint": selected_fingerprint,
            "reason": (
                "research index, SPY, and SCHX execution parity plus a live calendar "
                "scheduler and canary evidence are not implemented"
            ),
        },
        "promotion_allowed": False,
        "decision": {
            "verdict": verdict,
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
            "next_strategy_family": "accounting-cross-sectional-factors",
            "search_space_exhausted": False,
        },
        "safety": {
            "orders_submitted": 0,
            "capital_changed": False,
            "live_strategy_changed": False,
        },
    }


def render_turn_of_month_markdown(payload: Mapping[str, object]) -> str:
    decision = payload.get("decision")
    holdout = payload.get("holdout")
    data = payload.get("data_quality")
    if not isinstance(decision, Mapping) or not isinstance(holdout, Mapping):
        raise ValueError("turn-of-month result is incomplete")
    data = data if isinstance(data, Mapping) else {}
    failed = decision.get("failed_gates")
    failed_text = ", ".join(str(value) for value in failed) if isinstance(failed, list) else ""
    return "\n".join(
        [
            "# 월말·월초 독립 전략 연구 결과",
            "",
            f"- 판정: `{decision.get('verdict')}`",
            f"- 개발 선택 후보: `{decision.get('provisional_best_candidate_id')}`",
            f"- 홀드아웃 현금 초과 PSR: `{holdout.get('psr')}`",
            f"- 홀드아웃 연 현금 초과수익: `{holdout.get('annual_cash_excess')}`",
            f"- 가족 PBO: `{decision.get('pbo')}`",
            f"- 실패 관문: `{failed_text or '없음'}`",
            f"- 자료 범위: `{data.get('first_date')} ~ {data.get('last_date')}`",
            "- 실거래 승격: `금지` (실행 동등성과 캐너리 증거 없음)",
            "- 주문·자본·라이브 전략 변경: `0건`",
            "",
        ]
    )


__all__ = [
    "EXPECTED_GLOBAL_AUDIT_TRIALS",
    "EXPECTED_PROGRAM_FAMILIES",
    "FrenchDailyBundle",
    "build_french_daily_bundle",
    "generate_calendar_candidates",
    "render_turn_of_month_markdown",
    "run_turn_of_month_equity_factory",
]
