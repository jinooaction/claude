"""Preregistered, research-only post-earnings-announcement drift evaluation."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
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
GATE_VERSION = "3.2"
FAMILY_ID = "equity-post-earnings-announcement-drift"
DATA_RELEASE = "2025-10"
DATA_URL = "https://drive.google.com/uc?id=1g7w-yQ6Cg2qbMEkER9Q3vgns4JszXQo6"
SIGNALS = ("AnnouncementReturn", "EarningsSurprise")
EXPECTED_CANDIDATES = 16
EXPECTED_PRIOR_TRIALS = 800
EXPECTED_GLOBAL_TRIALS = 816
EXPECTED_PRIOR_FAMILIES = 20
EXPECTED_GLOBAL_FAMILIES = 21
DEVELOPMENT_END = "1996-12"
EMBARGO_START = "1997-01"
EMBARGO_END = "1997-12"
POST_PUBLICATION_START = "1998-01"
POST_PUBLICATION_END = "2015-12"
RECENT_START = "2016-01"
REQUIRED_LAST_MONTH = "2024-12"
PRIMARY_ANNUAL_BPS = 150
STRESS_ANNUAL_BPS = (300, 500)
PUBLISHED_EDGE = "PUBLISHED_EDGE"
PAPER_CHALLENGER = "PAPER_CHALLENGER"
NO_FACTORY_EDGE = "NO_FACTORY_EDGE"


def _fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


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


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True)
class PeadMonth:
    signal_name: str
    observed_month: date
    return_decimal: float
    long_count: int
    short_count: int


@dataclass(frozen=True)
class PeadPair:
    observed_month: date
    announcement_return: float
    surprise_return: float
    announcement_long_count: int
    announcement_short_count: int
    surprise_long_count: int
    surprise_short_count: int


@dataclass(frozen=True)
class PeadPolicy:
    announcement_weight: float
    sleeve_scale: float
    annual_cost_bps: int = PRIMARY_ANNUAL_BPS

    def as_dict(self) -> dict[str, object]:
        return {
            "announcement_weight": self.announcement_weight,
            "earnings_surprise_weight": 1.0 - self.announcement_weight,
            "sleeve_scale": self.sleeve_scale,
            "annual_cost_bps": self.annual_cost_bps,
            "signal": "public_equal_weighted_pead_long_short_sleeve",
        }


@dataclass(frozen=True)
class PeadCandidate:
    candidate_id: str
    trial_index: int
    policy: PeadPolicy
    strategy_fingerprint: str

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "trial_index": self.trial_index,
            "policy": self.policy.as_dict(),
            "strategy_fingerprint": self.strategy_fingerprint,
            "research_proxy": "Open Source Asset Pricing PEAD long-short portfolios",
            "live_expressible": False,
            "live_blocker": (
                "point-in-time constituents, delisting-adjusted prices, short borrow, "
                "integer-share execution, current-account costs, and forward evidence are absent"
            ),
        }


@dataclass(frozen=True)
class PeadBundle:
    development: tuple[PeadPair, ...]
    embargo: tuple[PeadPair, ...]
    post_publication_pre_recent: tuple[PeadPair, ...]
    recent: tuple[PeadPair, ...]
    quality: dict[str, object]


def parse_open_asset_pricing_csv(raw: bytes) -> tuple[PeadMonth, ...]:
    """Read only the two preregistered LS signal rows from the public CSV."""

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Open Asset Pricing CSV must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {"signalname", "port", "date", "ret", "Nlong", "Nshort"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("Open Asset Pricing CSV required columns are missing")
    output: list[PeadMonth] = []
    seen: set[tuple[str, str]] = set()
    for row in reader:
        signal = row.get("signalname", "").strip()
        if signal not in SIGNALS or row.get("port", "").strip() != "LS":
            continue
        try:
            observed = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
            month = date(observed.year, observed.month, 1)
            value = float(row["ret"].strip()) / 100.0
            long_count = int(row["Nlong"].strip())
            short_count = int(row["Nshort"].strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("Open Asset Pricing PEAD row is malformed") from exc
        if not math.isfinite(value) or value <= -1.0:
            raise ValueError("Open Asset Pricing PEAD returns must be finite and greater than -1")
        if long_count <= 0 or short_count <= 0:
            raise ValueError("Open Asset Pricing PEAD rows require positive long and short counts")
        identity = (signal, _month_key(month))
        if identity in seen:
            raise ValueError("Open Asset Pricing PEAD monthly row is duplicated")
        seen.add(identity)
        output.append(PeadMonth(signal, month, value, long_count, short_count))
    if not output:
        raise ValueError("Open Asset Pricing PEAD rows are empty")
    output.sort(key=lambda row: (row.signal_name, row.observed_month))
    for signal in SIGNALS:
        months = [row.observed_month for row in output if row.signal_name == signal]
        if not months or months != sorted(months):
            raise ValueError(f"{signal} monthly dates must increase")
    return tuple(output)


def build_pead_bundle(
    rows: Sequence[PeadMonth],
    *,
    data_digest: str,
    release: str,
) -> PeadBundle:
    if release != DATA_RELEASE:
        raise ValueError("PEAD data release does not match preregistration")
    if not data_digest.startswith("sha256:") or len(data_digest) != 71:
        raise ValueError("PEAD data digest must be a complete SHA-256")
    by_signal: dict[str, dict[str, PeadMonth]] = {signal: {} for signal in SIGNALS}
    for row in rows:
        if row.signal_name not in by_signal:
            raise ValueError("PEAD bundle contains an unregistered signal")
        month = _month_key(row.observed_month)
        if month in by_signal[row.signal_name]:
            raise ValueError("PEAD bundle contains a duplicated signal month")
        if (
            not math.isfinite(row.return_decimal)
            or row.return_decimal <= -1.0
            or row.long_count <= 0
            or row.short_count <= 0
        ):
            raise ValueError("PEAD bundle contains invalid returns or position counts")
        by_signal[row.signal_name][month] = row
    month_sets = [set(by_signal[signal]) for signal in SIGNALS]
    if not month_sets[0] or month_sets[0] != month_sets[1]:
        raise ValueError("PEAD signals must have complete common monthly history")
    common_months = sorted(month_sets[0])
    expected = _expected_months(common_months[0], REQUIRED_LAST_MONTH)
    if common_months != expected:
        raise ValueError("PEAD signals must have complete common monthly history through 2024-12")
    pairs: list[PeadPair] = []
    for month in common_months:
        announcement = by_signal["AnnouncementReturn"][month]
        surprise = by_signal["EarningsSurprise"][month]
        pairs.append(
            PeadPair(
                announcement.observed_month,
                announcement.return_decimal,
                surprise.return_decimal,
                announcement.long_count,
                announcement.short_count,
                surprise.long_count,
                surprise.short_count,
            )
        )
    development = tuple(row for row in pairs if _month_key(row.observed_month) <= DEVELOPMENT_END)
    embargo = tuple(
        row for row in pairs if EMBARGO_START <= _month_key(row.observed_month) <= EMBARGO_END
    )
    pre_recent = tuple(
        row
        for row in pairs
        if POST_PUBLICATION_START <= _month_key(row.observed_month) <= POST_PUBLICATION_END
    )
    recent = tuple(row for row in pairs if _month_key(row.observed_month) >= RECENT_START)
    if len(development) != 304 or len(embargo) != 12 or len(pre_recent) != 216:
        raise ValueError("PEAD development, embargo, or post-publication split is incomplete")
    if len(recent) != 108:
        raise ValueError("PEAD recent split must contain exactly 108 months")
    quality: dict[str, object] = {
        "complete": True,
        "provider": "Open Source Asset Pricing",
        "release": release,
        "source_url": DATA_URL,
        "content_digest": data_digest,
        "signals": list(SIGNALS),
        "portfolio": "LS",
        "common_start_month": common_months[0],
        "latest_month": common_months[-1],
        "common_month_count": len(common_months),
        "all_long_short_counts_positive": True,
        "signal_definitions": {
            "AnnouncementReturn": {
                "source_paper": "Chan, Jegadeesh, and Lakonishok (1996)",
                "definition": "abnormal return from day -1 through day +2 around earnings",
                "original_sample": "1977-1992",
            },
            "EarningsSurprise": {
                "source_paper": "Foster, Olsen, and Shevlin (1984)",
                "definition": (
                    "seasonal EPS change less drift, scaled by historical standard deviation"
                ),
                "original_sample": "1974-1981",
            },
        },
        "point_in_time_constituents": False,
    }
    return PeadBundle(development, embargo, pre_recent, recent, quality)


def generate_pead_candidates() -> tuple[PeadCandidate, ...]:
    output: list[PeadCandidate] = []
    for index in range(8):
        announcement_weight = index / 7
        for scale in (0.5, 1.0):
            policy = PeadPolicy(announcement_weight, scale)
            digest = _fingerprint(
                {
                    "schema_version": SCHEMA_VERSION,
                    "family_id": FAMILY_ID,
                    "policy": policy.as_dict(),
                    "data_release": DATA_RELEASE,
                    "signals": SIGNALS,
                    "split": {
                        "development_end": DEVELOPMENT_END,
                        "embargo": f"{EMBARGO_START}..{EMBARGO_END}",
                        "post_publication_start": POST_PUBLICATION_START,
                        "recent_start": RECENT_START,
                    },
                    "stress_annual_bps": STRESS_ANNUAL_BPS,
                    "placebo": "sign_flip_pead_sleeve",
                }
            )
            output.append(
                PeadCandidate(
                    candidate_id=(
                        f"pead-ann{index:02d}of07-scale{int(scale * 100):03d}-{digest[7:19]}"
                    ),
                    trial_index=len(output) + 1,
                    policy=policy,
                    strategy_fingerprint=digest,
                )
            )
    if len(output) != EXPECTED_CANDIDATES:
        raise RuntimeError("PEAD candidate count contract violated")
    if len({row.candidate_id for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("PEAD candidate ids are not unique")
    if len({row.strategy_fingerprint for row in output}) != EXPECTED_CANDIDATES:
        raise RuntimeError("PEAD candidate fingerprints are not unique")
    return tuple(output)


def _segments(values: Sequence[float], count: int = 10) -> list[list[float]]:
    size = len(values) // count
    if size < 2:
        return []
    return [
        list(values[index * size : (index + 1) * size if index < count - 1 else len(values)])
        for index in range(count)
    ]


def _policy_returns(
    rows: Sequence[PeadPair],
    policy: PeadPolicy,
    *,
    annual_cost_bps: int,
    sign: float = 1.0,
) -> dict[str, list[float] | list[str]]:
    monthly_cost = annual_cost_bps / 10_000.0 / 12.0
    excess: list[float] = []
    factors: list[float] = []
    months: list[str] = []
    for row in rows:
        raw = policy.sleeve_scale * sign * (
            policy.announcement_weight * row.announcement_return
            + (1.0 - policy.announcement_weight) * row.surprise_return
        )
        net = raw - monthly_cost
        factor = 1.0 + net
        if factor <= 0:
            raise ValueError("PEAD cost model produced a non-positive factor")
        months.append(_month_key(row.observed_month))
        excess.append(net)
        factors.append(factor)
    return {"months": months, "excess": excess, "factors": factors}


def _annualized(factors: Sequence[float]) -> float:
    if not factors or any(value <= 0 for value in factors):
        return -1.0
    return math.prod(factors) ** (12.0 / len(factors)) - 1.0


def _max_drawdown(factors: Sequence[float]) -> float:
    level = 1.0
    peak = 1.0
    worst = 0.0
    for factor in factors:
        level *= factor
        peak = max(peak, level)
        worst = min(worst, level / peak - 1.0)
    return abs(worst)


def _year_concentration(months: Sequence[str], excess: Sequence[float]) -> float:
    yearly: dict[str, float] = defaultdict(float)
    for month, value in zip(months, excess, strict=True):
        yearly[month[:4]] += value
    positive = [value for value in yearly.values() if value > 0]
    return max(positive) / sum(positive) if positive else 1.0


def _top_five_concentration(excess: Sequence[float]) -> float:
    positive = sorted((value for value in excess if value > 0), reverse=True)
    return sum(positive[:5]) / sum(positive) if positive else 1.0


def _gate(gate_id: str, passed: bool, actual: object, required: object) -> dict[str, object]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "actual": str(actual),
        "required": str(required),
        "blocking": True,
    }


def _validate_preregistration(payload: Mapping[str, object]) -> None:
    if (
        payload.get("family_id") != FAMILY_ID
        or payload.get("diagnostic_gate_version") != GATE_VERSION
    ):
        raise ValueError("PEAD preregistration identity is invalid")
    candidates = payload.get("candidates")
    split = payload.get("split")
    safety = payload.get("safety")
    if not all(isinstance(value, Mapping) for value in (candidates, split, safety)):
        raise ValueError("PEAD preregistration is incomplete")
    weights = candidates.get("announcement_weights")
    if not isinstance(weights, list) or len(weights) != 8:
        raise ValueError("PEAD preregistration candidate weights are invalid")
    expected_weights = [index / 7 for index in range(8)]
    if any(
        abs(float(left) - right) > 1e-11
        for left, right in zip(weights, expected_weights, strict=True)
    ):
        raise ValueError("PEAD preregistration candidate weights are invalid")
    if (
        split.get("development_end") != DEVELOPMENT_END
        or split.get("embargo_start") != EMBARGO_START
        or split.get("embargo_end") != EMBARGO_END
        or split.get("post_publication_start") != POST_PUBLICATION_START
        or split.get("post_publication_end") != POST_PUBLICATION_END
        or split.get("recent_start") != RECENT_START
        or int(split.get("recent_required_months", 0)) != 108
    ):
        raise ValueError("PEAD preregistration split is invalid")
    if safety != {
        "research_only": True,
        "research_canary_eligible": False,
        "promotion_allowed": False,
        "capital_allocation_fraction": 0.0,
        "orders_submitted": 0,
        "selected_deploy_config": None,
    }:
        raise ValueError("PEAD preregistration safety contract is invalid")


def _validate_calibration(payload: Mapping[str, object], *, code_commit: str) -> dict[str, object]:
    scenario = payload.get("scenario")
    families = payload.get("family_calibrations")
    extension = payload.get("program_extension")
    if not all(isinstance(value, Mapping) for value in (scenario, families, extension)):
        raise ValueError("PEAD program calibration is incomplete")
    family16 = families.get("16")
    family64 = families.get("64")
    if not isinstance(family16, Mapping) or not isinstance(family64, Mapping):
        raise ValueError("PEAD program calibration families are incomplete")
    expected = {
        "gate_version": GATE_VERSION,
        "method": "family-size-bonferroni-v2",
        "family_caps": {"16": 0.01, "64": 0.009},
        "family_mix": {"16": 11, "64": 10},
        "conservative_upper_bound": 0.2,
        "false_acceptance_budget": 0.2,
        "planted_sharpe_annual": 0.6,
        "detection_min": 0.8,
        "minimum_repetitions": 500,
        "calibrated": True,
        "capital_entry_eligible": False,
    }
    try:
        valid = bool(
            payload.get("code_commit") == code_commit
            and int(scenario.get("seed", -1)) == 60_000
            and int(scenario.get("repetitions", 0)) >= 500
            and all(extension.get(key) == value for key, value in expected.items())
            and float(family16.get("null_research_entry_acceptance_rate", 1)) <= 0.01
            and float(family64.get("null_research_entry_acceptance_rate", 1)) <= 0.009
            and float(family16.get("target_research_entry_detection_rate", 0)) >= 0.8
            and float(family64.get("target_research_entry_detection_rate", 0)) >= 0.8
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("PEAD program calibration does not match preregistration")
    return dict(extension)


def _validate_prior(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if len(rows) != EXPECTED_PRIOR_TRIALS:
        raise ValueError("prior audit must contain exactly 800 rows")
    output = [dict(row) for row in rows]
    candidate_ids: list[str] = []
    fingerprints: list[str] = []
    for row in output:
        candidate_id = row.get("candidate_id")
        fingerprint = row.get("strategy_fingerprint")
        if (
            row.get("status") not in {"complete", "EXPLORATORY_REJECTED"}
            or not isinstance(candidate_id, str)
            or not isinstance(fingerprint, str)
        ):
            raise ValueError("prior audit identity is incomplete")
        candidate_ids.append(candidate_id)
        fingerprints.append(fingerprint)
    if len(set(candidate_ids)) != 800 or len(set(fingerprints)) != 800:
        raise ValueError("prior audit must contain 800 unique identities")
    families = build_research_family_audit(output)
    sizes = Counter(int(row["candidate_count"]) for row in families)
    if len(families) != EXPECTED_PRIOR_FAMILIES or sizes != Counter({16: 10, 64: 10}):
        raise ValueError("prior audit must reconstruct 20 preregistered family sizes")
    return output


def run_pead_factory(
    *,
    bundle: PeadBundle,
    prior_audit_records: Sequence[Mapping[str, object]],
    calibration: Mapping[str, object],
    preregistration: Mapping[str, object],
    code_commit: str,
    generated_at: str,
) -> dict[str, object]:
    _validate_preregistration(preregistration)
    program_calibration = _validate_calibration(calibration, code_commit=code_commit)
    prior = _validate_prior(prior_audit_records)
    if bundle.quality.get("complete") is not True:
        raise ValueError("PEAD bundle is incomplete")
    candidates = generate_pead_candidates()
    analyses: list[dict[str, object]] = []
    development_returns: list[list[float]] = []
    development_segments: list[list[float]] = []
    for candidate in candidates:
        development = _policy_returns(
            bundle.development,
            candidate.policy,
            annual_cost_bps=PRIMARY_ANNUAL_BPS,
        )
        excess = [float(value) for value in development["excess"]]
        segment_sharpes = [annualized_sharpe(segment) for segment in _segments(excess)]
        if len(segment_sharpes) != 10:
            raise ValueError("PEAD development needs ten complete segments")
        development_returns.append(excess)
        development_segments.append(segment_sharpes)
        analyses.append(
            {
                "candidate": candidate,
                "development_sharpe": annualized_sharpe(excess),
                "segment_sharpes": segment_sharpes,
            }
        )
    winner_index = max(
        range(len(analyses)),
        key=lambda index: (float(analyses[index]["development_sharpe"]), -index),
    )
    winner = analyses[winner_index]["candidate"]
    assert isinstance(winner, PeadCandidate)
    trial_sharpes = [float(row["development_sharpe"]) for row in analyses]
    pbo = probability_of_backtest_overfitting(development_segments)
    effective_trials = effective_independent_trials(development_returns)
    dsr = deflated_sharpe_from_trials(
        development_returns[winner_index],
        trial_sharpes,
        effective_trial_count=effective_trials,
    )

    confirmation_rows = (*bundle.post_publication_pre_recent, *bundle.recent)
    primary = _policy_returns(
        confirmation_rows,
        winner.policy,
        annual_cost_bps=PRIMARY_ANNUAL_BPS,
    )
    stress300 = _policy_returns(confirmation_rows, winner.policy, annual_cost_bps=300)
    stress500 = _policy_returns(confirmation_rows, winner.policy, annual_cost_bps=500)
    placebo = _policy_returns(
        confirmation_rows,
        winner.policy,
        annual_cost_bps=PRIMARY_ANNUAL_BPS,
        sign=-1.0,
    )
    months = [str(value) for value in primary["months"]]
    excess = [float(value) for value in primary["excess"]]
    factors = [float(value) for value in primary["factors"]]
    psr = probabilistic_sharpe(excess)
    annual_excess = _annualized(factors)
    era_ranges = (
        ("1998-01", "2004-12"),
        ("2005-01", "2010-12"),
        ("2011-01", "2015-12"),
        ("2016-01", "2024-12"),
    )
    era_annual: dict[str, float] = {}
    for start, end in era_ranges:
        indexes = [index for index, month in enumerate(months) if start <= month <= end]
        era_annual[f"{start[:4]}-{end[:4]}"] = _annualized(
            [factors[index] for index in indexes]
        )
    positive_eras = sum(value > 0 for value in era_annual.values())
    recent_primary = _policy_returns(
        bundle.recent,
        winner.policy,
        annual_cost_bps=PRIMARY_ANNUAL_BPS,
    )
    recent_factors = [float(value) for value in recent_primary["factors"]]
    recent_windows = [
        _annualized(recent_factors[index : index + 36]) for index in range(0, 108, 36)
    ]
    positive_recent = sum(value > 0 for value in recent_windows)
    year_concentration = _year_concentration(months, excess)
    top_five_concentration = _top_five_concentration(excess)
    maximum_drawdown = _max_drawdown(factors)
    stress300_annual = _annualized([float(value) for value in stress300["factors"]])
    stress500_annual = _annualized([float(value) for value in stress500["factors"]])
    placebo_excess = [float(value) for value in placebo["excess"]]
    placebo_psr = probabilistic_sharpe(placebo_excess)
    placebo_annual = _annualized([float(value) for value in placebo["factors"]])
    placebo_core_passed = bool(
        placebo_psr is not None and placebo_psr >= Decimal("0.95") and placebo_annual >= 0.01
    )

    trial_records: list[dict[str, object]] = []
    for index, analysis in enumerate(analyses):
        candidate = analysis["candidate"]
        assert isinstance(candidate, PeadCandidate)
        candidate_confirmation = _policy_returns(
            confirmation_rows,
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
                    probabilistic_sharpe(
                        [float(value) for value in candidate_confirmation["excess"]]
                    )
                ),
                "selected_by_development": index == winner_index,
                "holdout_inspected_after_selection": True,
                "data_fingerprint": bundle.quality.get("content_digest"),
            }
        )
        trial_records.append(record)
    audit_records = annotate_research_families(prior + trial_records)
    trial_records = audit_records[-EXPECTED_CANDIDATES:]
    family_audit = build_research_family_audit(audit_records)
    candidate_ids = [str(row["candidate_id"]) for row in audit_records]
    fingerprints = [str(row["strategy_fingerprint"]) for row in audit_records]
    family_sizes = Counter(int(row["candidate_count"]) for row in family_audit)
    if (
        len(audit_records) != EXPECTED_GLOBAL_TRIALS
        or len(set(candidate_ids)) != EXPECTED_GLOBAL_TRIALS
        or len(set(fingerprints)) != EXPECTED_GLOBAL_TRIALS
        or len(family_audit) != EXPECTED_GLOBAL_FAMILIES
        or family_sizes != Counter({16: 11, 64: 10})
    ):
        raise ValueError("PEAD global research audit contract failed")

    gates = [
        _gate("program_calibration", True, True, True),
        _gate("family_pbo", pbo is not None and pbo <= Decimal("0.25"), pbo, "<=0.25"),
        _gate(
            "post_publication_psr",
            psr is not None and psr >= Decimal("0.95"),
            psr,
            ">=0.95",
        ),
        _gate("post_publication_annual_excess", annual_excess >= 0.01, annual_excess, ">=0.01"),
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
            top_five_concentration <= 0.50,
            top_five_concentration,
            "<=0.50",
        ),
        _gate("maximum_drawdown", maximum_drawdown <= 0.30, maximum_drawdown, "<=0.30"),
        _gate("stress_300bps_positive", stress300_annual > 0, stress300_annual, ">0"),
        _gate(
            "sign_flipped_placebo_fails_core",
            not placebo_core_passed,
            placebo_core_passed,
            False,
        ),
    ]
    published = all(bool(row["passed"]) for row in gates)
    paper = bool(
        pbo is not None
        and pbo <= Decimal("0.25")
        and psr is not None
        and psr >= Decimal("0.80")
        and annual_excess > 0
        and stress300_annual > 0
        and not placebo_core_passed
    )
    verdict = PUBLISHED_EDGE if published else PAPER_CHALLENGER if paper else NO_FACTORY_EDGE
    selected_candidate_id = winner.candidate_id if published else None
    selected_fingerprint = winner.strategy_fingerprint if published else None
    criterion_validity = dict(preregistration["criterion_validity"])
    safety = dict(preregistration["safety"])
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_version": GATE_VERSION,
        "family_id": FAMILY_ID,
        "code_commit": code_commit,
        "generated_at": generated_at,
        "timestamp_utc": generated_at,
        "batch_id": f"pead-{str(bundle.quality['content_digest'])[7:19]}-{code_commit[:12]}",
        "pead_data_fingerprint": bundle.quality["content_digest"],
        "candidate_count": EXPECTED_CANDIDATES,
        "complete_trial_count": EXPECTED_CANDIDATES,
        "multiplicity_trial_count": EXPECTED_CANDIDATES,
        "prior_trial_count": EXPECTED_PRIOR_TRIALS,
        "global_audit_trial_count": EXPECTED_GLOBAL_TRIALS,
        "program_research_family_count": EXPECTED_GLOBAL_FAMILIES,
        "verdict": verdict,
        "program_calibration": program_calibration,
        "data_quality": bundle.quality,
        "split": {
            "development_start": _month_key(bundle.development[0].observed_month),
            "development_end": DEVELOPMENT_END,
            "embargo_start": EMBARGO_START,
            "embargo_end": EMBARGO_END,
            "post_publication_start": POST_PUBLICATION_START,
            "post_publication_pre_recent_end": POST_PUBLICATION_END,
            "recent_start": RECENT_START,
            "holdout_end": REQUIRED_LAST_MONTH,
            "development_months": len(bundle.development),
            "embargo_months": len(bundle.embargo),
            "post_publication_pre_recent_months": len(bundle.post_publication_pre_recent),
            "recent_months": len(bundle.recent),
            "full_confirmation_months": len(confirmation_rows),
        },
        "candidate_registry": [candidate.as_dict() for candidate in candidates],
        "trial_records": trial_records,
        "audit_records": audit_records,
        "research_family_audit": family_audit,
        "global_audit": {
            "trial_count": EXPECTED_GLOBAL_TRIALS,
            "unique_candidate_id_count": len(set(candidate_ids)),
            "unique_strategy_fingerprint_count": len(set(fingerprints)),
            "family_count": EXPECTED_GLOBAL_FAMILIES,
            "family_size_counts": {"16": family_sizes[16], "64": family_sizes[64]},
        },
        "development_returns": development_returns,
        "development_segment_sharpes": development_segments,
        "development_selection": {
            "method": "maximum_primary_cost_sharpe_on_development_only",
            "selected_candidate_id": winner.candidate_id,
            "selected_strategy_fingerprint": winner.strategy_fingerprint,
            "selected_trial_index": winner.trial_index,
            "holdout_used_for_selection": False,
            "development_end": DEVELOPMENT_END,
        },
        "criterion_validity": criterion_validity,
        "historical_evaluation": {
            "full_confirmation_psr": _decimal(psr),
            "full_confirmation_annual_excess": annual_excess,
            "era_annual_excess": era_annual,
            "positive_eras": positive_eras,
            "recent_36m_annual_excess": recent_windows,
            "recent_36m_wins": positive_recent,
            "single_year_positive_contribution": year_concentration,
            "top_five_month_positive_contribution": top_five_concentration,
            "maximum_drawdown": maximum_drawdown,
            "stress_300bps_annual_excess": stress300_annual,
            "stress_500bps_annual_excess": stress500_annual,
            "sign_flipped_placebo_psr": _decimal(placebo_psr),
            "sign_flipped_placebo_annual_excess": placebo_annual,
            "sign_flipped_placebo_core_passed": placebo_core_passed,
        },
        "research_live_parity": {
            "passed": False,
            "candidate_id": selected_candidate_id,
            "strategy_fingerprint": selected_fingerprint,
            "reason": (
                "public portfolio returns do not expose point-in-time constituents, delisting "
                "adjustments, short-borrow feasibility, integer shares, or current-account costs"
            ),
        },
        "forward_observation": {
            **dict(preregistration["forward_observation"]),
            "observed_earnings_events": 0,
            "observed_calendar_months": 0,
            "point_in_time_constituents": False,
            "delisting_adjusted_returns": False,
            "account_execution_parity": False,
            "eligible_for_next_review": False,
        },
        "decision": {
            "verdict": verdict,
            "historical_edge_passed": published,
            "provisional_best_candidate_id": winner.candidate_id,
            "selected_candidate_id": selected_candidate_id,
            "selected_strategy_fingerprint": selected_fingerprint,
            "selected_deploy_config": None,
            "research_canary_eligible": False,
            "promotion_allowed": False,
            "psr": _decimal(psr),
            "dsr": _decimal(dsr),
            "pbo": _decimal(pbo),
            "gates": gates,
            "failed_gates": [str(row["gate_id"]) for row in gates if not row["passed"]],
            "paper_gates_passed": paper,
            "threshold_change_after_results": False,
            "next_strategy_family": "forward-point-in-time-pead-observation",
            "search_space_exhausted": False,
        },
        "promotion_allowed": False,
        "safety": safety,
    }


def render_pead_markdown(payload: Mapping[str, object]) -> str:
    decision = payload.get("decision")
    evaluation = payload.get("historical_evaluation")
    quality = payload.get("data_quality")
    if not all(isinstance(value, Mapping) for value in (decision, evaluation, quality)):
        raise ValueError("PEAD result is incomplete")
    failed = decision.get("failed_gates")
    failed_text = ", ".join(str(value) for value in failed) if isinstance(failed, list) else ""
    return "\n".join(
        [
            "# 자동 전략 공장 - PEAD 공개 복제",
            "",
            f"- 역사 판정: `{decision.get('verdict')}`",
            f"- 개발 선택 후보: `{decision.get('provisional_best_candidate_id')}`",
            f"- 출판 후 PSR: `{decision.get('psr')}`",
            (
                "- 연 1.5% 비용 후 출판 후 초과수익: "
                f"`{evaluation.get('full_confirmation_annual_excess')}`"
            ),
            f"- 최근 36개월 합격: `{evaluation.get('recent_36m_wins')}/3`",
            f"- 실패 관문: `{failed_text or '없음'}`",
            f"- 공개자료 SHA-256: `{quality.get('content_digest')}`",
            "- 공개 복제자료 일부는 사전 타당성 확인에서 열람되어 비공개 홀드아웃이 아닙니다.",
            "- 역사 합격도 현재 계좌 실행 적격이 아닙니다.",
            "- 안전: 연구 캐너리 false, 승격 false, 자본 0%, 주문 0건",
        ]
    )


__all__ = [
    "DATA_RELEASE",
    "DATA_URL",
    "EXPECTED_CANDIDATES",
    "EXPECTED_GLOBAL_FAMILIES",
    "EXPECTED_GLOBAL_TRIALS",
    "FAMILY_ID",
    "GATE_VERSION",
    "PAPER_CHALLENGER",
    "PUBLISHED_EDGE",
    "NO_FACTORY_EDGE",
    "PeadBundle",
    "PeadCandidate",
    "PeadMonth",
    "PeadPair",
    "PeadPolicy",
    "build_pead_bundle",
    "generate_pead_candidates",
    "parse_open_asset_pricing_csv",
    "render_pead_markdown",
    "run_pead_factory",
]
