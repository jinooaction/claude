"""스펙 138 - 실제 설정을 시간 분리로 검증하는 no-live 수익 증거 엔진."""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from auto_invest.analytics.global_trend import (
    global_trend_factors,
    gold_total_return_factors,
    risk_parity_global_factors,
)
from auto_invest.analytics.multi_asset_trend import (
    blend,
    bond_total_return_factors,
    diversified_trend_factors,
)
from auto_invest.analytics.risk_managed_beta import (
    LegStats,
    MonthlyRow,
    market_total_return_factors,
    summarize,
)

SCHEMA_VERSION = "1.0"
HOLDOUT_EDGE = "HOLDOUT_EDGE"
NO_HOLDOUT_EDGE = "NO_HOLDOUT_EDGE"
FORWARD_VALIDATION = "FORWARD_VALIDATION"
FORWARD_EDGE_READY = "FORWARD_EDGE_READY"

_WINDOWS = (6, 8, 10, 12)
_ALLOCATIONS = (
    "two_asset_equal",
    "three_asset_fixed",
    "three_asset_inverse_vol",
)
_FORWARD_TRACK = {
    "two_asset_equal": "multiasset",
    "three_asset_fixed": "globalfixed",
    "three_asset_inverse_vol": "global",
}
_SAFETY_INVARIANTS = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live rearming",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no constitution/kernel change",
    "Backtest -> Canary -> Full remains mandatory",
)


@dataclass(frozen=True)
class ProfitCandidate:
    candidate_id: str
    allocation: str
    trend_window_months: int
    trial_index: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "allocation": self.allocation,
            "trend_window_months": self.trend_window_months,
            "trial_index": self.trial_index,
        }


@dataclass(frozen=True)
class PerformanceSnapshot:
    n_months: int
    cagr_pct: float
    sharpe: float
    max_drawdown_pct: float
    calmar: float | None

    @classmethod
    def from_stats(cls, stats: LegStats) -> PerformanceSnapshot:
        return cls(
            n_months=stats.n_months,
            cagr_pct=round(stats.cagr_pct, 6),
            sharpe=round(stats.sharpe, 6),
            max_drawdown_pct=round(stats.max_dd_pct, 6),
            calmar=round(stats.calmar, 6) if stats.calmar is not None else None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_months": self.n_months,
            "cagr_pct": self.cagr_pct,
            "sharpe": self.sharpe,
            "max_drawdown_pct": self.max_drawdown_pct,
            "calmar": self.calmar,
        }


@dataclass(frozen=True)
class TemporalSplit:
    development_start: str
    development_end: str
    holdout_start: str
    holdout_end: str
    overlap_months: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "development_start": self.development_start,
            "development_end": self.development_end,
            "holdout_start": self.holdout_start,
            "holdout_end": self.holdout_end,
            "overlap_months": self.overlap_months,
        }


@dataclass(frozen=True)
class HoldoutGate:
    gate_id: str
    passed: bool
    candidate_value: float | None
    benchmark_value: float | None
    rule: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "passed": self.passed,
            "candidate_value": self.candidate_value,
            "benchmark_value": self.benchmark_value,
            "rule": self.rule,
        }


@dataclass(frozen=True)
class NeighborEvidence:
    trend_window_months: int
    performance: PerformanceSnapshot
    sharpe_better: bool
    drawdown_within_limit: bool

    @property
    def passed(self) -> bool:
        return self.sharpe_better and self.drawdown_within_limit

    def as_dict(self) -> dict[str, Any]:
        return {
            "trend_window_months": self.trend_window_months,
            "performance": self.performance.as_dict(),
            "sharpe_better": self.sharpe_better,
            "drawdown_within_limit": self.drawdown_within_limit,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class ForwardEvidence:
    track_key: str
    present: bool
    n_obs: int | None
    psr_vs_benchmark: float | None
    dsr: float | None
    verdict: str | None
    threshold: float = 0.95

    @property
    def passed(self) -> bool:
        if self.verdict != "EDGE_CONFIRMED" or self.psr_vs_benchmark is None:
            return False
        if self.psr_vs_benchmark < self.threshold:
            return False
        return self.dsr is None or self.dsr >= self.threshold

    def as_dict(self) -> dict[str, Any]:
        return {
            "track_key": self.track_key,
            "present": self.present,
            "n_obs": self.n_obs,
            "psr_vs_benchmark": self.psr_vs_benchmark,
            "dsr": self.dsr,
            "verdict": self.verdict,
            "threshold": self.threshold,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class ProfitEvidenceReport:
    status: str
    historical_verdict: str
    annual_cost_bps: int
    trial_count: int
    split: TemporalSplit
    selected_candidate: ProfitCandidate
    development: PerformanceSnapshot
    holdout: PerformanceSnapshot
    benchmark_holdout: PerformanceSnapshot
    gates: tuple[HoldoutGate, ...]
    neighbors: tuple[NeighborEvidence, ...]
    forward: ForwardEvidence
    family_scores: Mapping[str, Mapping[str, float]]
    safety_invariants: tuple[str, ...] = _SAFETY_INVARIANTS

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "historical_verdict": self.historical_verdict,
            "annual_cost_bps": self.annual_cost_bps,
            "trial_count": self.trial_count,
            "split": self.split.as_dict(),
            "selected_candidate": self.selected_candidate.as_dict(),
            "development": self.development.as_dict(),
            "holdout": self.holdout.as_dict(),
            "benchmark_holdout": self.benchmark_holdout.as_dict(),
            "gates": [gate.as_dict() for gate in self.gates],
            "neighbors": [neighbor.as_dict() for neighbor in self.neighbors],
            "forward": self.forward.as_dict(),
            "family_scores": {key: dict(value) for key, value in self.family_scores.items()},
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        selected = self.selected_candidate
        lines = [
            "# 수익 증거 엔진 최신 실행",
            "",
            f"> 판정: **{self.status}** / 역사 검증: **{self.historical_verdict}**",
            "",
            "## 찾은 방법",
            "",
            f"- 자산배분: `{selected.allocation}`",
            f"- 추세 창: `{selected.trend_window_months}`개월",
            f"- 사전등록 시행 수: `{self.trial_count}`",
            f"- 연간 비용 차감: `{self.annual_cost_bps}bp`",
            "",
            "## 선택과 최종 검증",
            "",
            f"- 개발 구간: {self.split.development_start} ~ {self.split.development_end}",
            f"- 최종 검증: {self.split.holdout_start} ~ {self.split.holdout_end}",
            f"- 구간 겹침: {self.split.overlap_months}개월",
            f"- 후보 연복리/샤프/낙폭: {self.holdout.cagr_pct:.2f}% / "
            f"{self.holdout.sharpe:.2f} / {self.holdout.max_drawdown_pct:.2f}%",
            f"- 벤치마크 연복리/샤프/낙폭: {self.benchmark_holdout.cagr_pct:.2f}% / "
            f"{self.benchmark_holdout.sharpe:.2f} / {self.benchmark_holdout.max_drawdown_pct:.2f}%",
            "",
            "## 현재 전진 관측",
            "",
            f"- 트랙: `{self.forward.track_key}`",
            f"- 관측/PSR/판정: {self.forward.n_obs} / {self.forward.psr_vs_benchmark} / "
            f"{self.forward.verdict}",
            "",
            "## 안전 경계",
            "",
            "역사 검증 통과는 실주문 승인이 아니다. 현재 forward 확률·다중검정, "
            "hardened canary, 전략 지문, 자본 사다리를 그대로 통과해야 한다. "
            "이 실행은 실주문·자본 배분·live 재무장을 하지 않는다.",
        ]
        return "\n".join(lines)


def registered_candidates() -> tuple[ProfitCandidate, ...]:
    candidates: list[ProfitCandidate] = []
    trial = 1
    for allocation in _ALLOCATIONS:
        for window in _WINDOWS:
            candidates.append(
                ProfitCandidate(
                    candidate_id=f"{allocation}-w{window}",
                    allocation=allocation,
                    trend_window_months=window,
                    trial_index=trial,
                )
            )
            trial += 1
    return tuple(candidates)


def apply_annual_cost_drag(
    factors: Sequence[float], *, annual_cost_bps: int = 50
) -> list[float]:
    if annual_cost_bps < 0:
        raise ValueError("annual_cost_bps must be non-negative")
    monthly_multiplier = (1.0 - annual_cost_bps / 10_000.0) ** (1.0 / 12.0)
    return [float(factor) * monthly_multiplier for factor in factors]


def build_candidate_factors(
    rows: list[MonthlyRow], gold_levels: list[float]
) -> tuple[dict[str, list[float]], list[float]]:
    if len(rows) != len(gold_levels):
        raise ValueError("rows and gold_levels must align")
    equity = market_total_return_factors(rows)
    bonds = bond_total_return_factors(rows)
    gold = gold_total_return_factors(gold_levels)
    benchmark = blend([(1 / 3, equity), (1 / 3, bonds), (1 / 3, gold)])
    factors: dict[str, list[float]] = {}
    for candidate in registered_candidates():
        window = candidate.trend_window_months
        if candidate.allocation == "two_asset_equal":
            values = diversified_trend_factors(rows, window=window)
        elif candidate.allocation == "three_asset_fixed":
            values = global_trend_factors(rows, gold_levels, window=window)
        else:
            values = risk_parity_global_factors(rows, gold_levels, window=window)
        factors[candidate.candidate_id] = values
    return factors, benchmark


def evaluate_profit_evidence(
    *,
    dates: Sequence[str],
    candidate_factors: Mapping[str, Sequence[float]],
    benchmark_factors: Sequence[float],
    leaderboard: Mapping[str, Any] | None = None,
    annual_cost_bps: int = 50,
    holdout_year: int = 2007,
) -> ProfitEvidenceReport:
    candidates = registered_candidates()
    n = len(dates)
    if len(benchmark_factors) != n:
        raise ValueError("dates and benchmark_factors must align")
    if any(len(candidate_factors.get(candidate.candidate_id, ())) != n for candidate in candidates):
        raise ValueError("all registered candidate factors must align with dates")
    split_index = next(
        (index for index, date in enumerate(dates) if int(date[:4]) >= holdout_year),
        n,
    )
    if split_index < 120 or n - split_index < 120:
        raise ValueError("development and holdout periods must each contain at least 120 months")

    net_factors = {
        candidate.candidate_id: apply_annual_cost_drag(
            candidate_factors[candidate.candidate_id], annual_cost_bps=annual_cost_bps
        )
        for candidate in candidates
    }
    development_stats = {
        candidate.candidate_id: summarize(net_factors[candidate.candidate_id][:split_index])
        for candidate in candidates
    }
    family_scores = _family_scores(candidates, development_stats)
    winning_family = max(
        _ALLOCATIONS,
        key=lambda allocation: (
            family_scores[allocation]["median_cagr_pct"],
            family_scores[allocation]["median_sharpe"],
            -family_scores[allocation]["median_max_drawdown_pct"],
            -_ALLOCATIONS.index(allocation),
        ),
    )
    selected = next(
        candidate
        for candidate in candidates
        if candidate.allocation == winning_family and candidate.trend_window_months == 10
    )
    holdout_stats = summarize(net_factors[selected.candidate_id][split_index:])
    benchmark_stats = summarize(list(benchmark_factors[split_index:]))
    neighbors = tuple(
        _neighbor_evidence(
            candidate,
            net_factors[candidate.candidate_id][split_index:],
            benchmark_stats,
        )
        for candidate in candidates
        if candidate.allocation == winning_family
        and candidate.trend_window_months in {8, 12}
    )
    gates = _holdout_gates(holdout_stats, benchmark_stats, neighbors)
    historical_verdict = (
        HOLDOUT_EDGE if all(gate.passed for gate in gates) else NO_HOLDOUT_EDGE
    )
    forward = _forward_evidence(winning_family, leaderboard)
    if historical_verdict == NO_HOLDOUT_EDGE:
        status = NO_HOLDOUT_EDGE
    elif forward.passed:
        status = FORWARD_EDGE_READY
    else:
        status = FORWARD_VALIDATION
    split = TemporalSplit(
        development_start=dates[0],
        development_end=dates[split_index - 1],
        holdout_start=dates[split_index],
        holdout_end=dates[-1],
    )
    return ProfitEvidenceReport(
        status=status,
        historical_verdict=historical_verdict,
        annual_cost_bps=annual_cost_bps,
        trial_count=len(candidates),
        split=split,
        selected_candidate=selected,
        development=PerformanceSnapshot.from_stats(development_stats[selected.candidate_id]),
        holdout=PerformanceSnapshot.from_stats(holdout_stats),
        benchmark_holdout=PerformanceSnapshot.from_stats(benchmark_stats),
        gates=gates,
        neighbors=neighbors,
        forward=forward,
        family_scores=family_scores,
    )


def build_profit_evidence_report(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    leaderboard: Mapping[str, Any] | None = None,
    annual_cost_bps: int = 50,
    holdout_year: int = 2007,
) -> ProfitEvidenceReport:
    factors, benchmark = build_candidate_factors(rows, gold_levels)
    return evaluate_profit_evidence(
        dates=[row.date for row in rows[1:]],
        candidate_factors=factors,
        benchmark_factors=benchmark,
        leaderboard=leaderboard,
        annual_cost_bps=annual_cost_bps,
        holdout_year=holdout_year,
    )


def _family_scores(
    candidates: Sequence[ProfitCandidate],
    stats: Mapping[str, LegStats],
) -> dict[str, dict[str, float]]:
    scores: dict[str, dict[str, float]] = {}
    for allocation in _ALLOCATIONS:
        rows = [stats[item.candidate_id] for item in candidates if item.allocation == allocation]
        scores[allocation] = {
            "median_cagr_pct": round(statistics.median(row.cagr_pct for row in rows), 6),
            "median_sharpe": round(statistics.median(row.sharpe for row in rows), 6),
            "median_max_drawdown_pct": round(
                statistics.median(row.max_dd_pct for row in rows), 6
            ),
        }
    return scores


def _neighbor_evidence(
    candidate: ProfitCandidate,
    factors: Sequence[float],
    benchmark: LegStats,
) -> NeighborEvidence:
    stats = summarize(list(factors))
    return NeighborEvidence(
        trend_window_months=candidate.trend_window_months,
        performance=PerformanceSnapshot.from_stats(stats),
        sharpe_better=stats.sharpe > benchmark.sharpe,
        drawdown_within_limit=stats.max_dd_pct <= benchmark.max_dd_pct * 0.8,
    )


def _holdout_gates(
    candidate: LegStats,
    benchmark: LegStats,
    neighbors: Sequence[NeighborEvidence],
) -> tuple[HoldoutGate, ...]:
    return (
        HoldoutGate(
            "cagr",
            candidate.cagr_pct > benchmark.cagr_pct,
            round(candidate.cagr_pct, 6),
            round(benchmark.cagr_pct, 6),
            "cost-adjusted candidate CAGR > benchmark CAGR",
        ),
        HoldoutGate(
            "sharpe",
            candidate.sharpe > benchmark.sharpe,
            round(candidate.sharpe, 6),
            round(benchmark.sharpe, 6),
            "candidate Sharpe > benchmark Sharpe",
        ),
        HoldoutGate(
            "drawdown",
            candidate.max_dd_pct <= benchmark.max_dd_pct * 0.8,
            round(candidate.max_dd_pct, 6),
            round(benchmark.max_dd_pct, 6),
            "candidate max drawdown <= 80% of benchmark",
        ),
        HoldoutGate(
            "neighbor_robustness",
            bool(neighbors) and all(neighbor.passed for neighbor in neighbors),
            float(sum(neighbor.passed for neighbor in neighbors)),
            float(len(neighbors)),
            "all adjacent registered windows preserve Sharpe and drawdown superiority",
        ),
    )


def _forward_evidence(
    allocation: str, leaderboard: Mapping[str, Any] | None
) -> ForwardEvidence:
    track_key = _FORWARD_TRACK[allocation]
    rows = leaderboard.get("rows") if isinstance(leaderboard, Mapping) else None
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping) and str(row.get("key")) == track_key:
                return ForwardEvidence(
                    track_key=track_key,
                    present=True,
                    n_obs=_optional_int(row.get("n_obs")),
                    psr_vs_benchmark=_optional_float(row.get("psr_vs_benchmark")),
                    dsr=_optional_float(row.get("dsr")),
                    verdict=str(row.get("verdict") or "") or None,
                )
    return ForwardEvidence(track_key, False, None, None, None, None)


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


__all__ = [
    "FORWARD_EDGE_READY",
    "FORWARD_VALIDATION",
    "HOLDOUT_EDGE",
    "NO_HOLDOUT_EDGE",
    "ForwardEvidence",
    "HoldoutGate",
    "PerformanceSnapshot",
    "ProfitCandidate",
    "ProfitEvidenceReport",
    "TemporalSplit",
    "apply_annual_cost_drag",
    "build_candidate_factors",
    "build_profit_evidence_report",
    "evaluate_profit_evidence",
    "registered_candidates",
]
