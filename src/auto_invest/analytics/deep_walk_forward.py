"""스펙 047 후속 — 깊은 OOS walk-forward: 추세추종이 단순 보유를 *정말* 이기는가(레짐 완전).

배경(왜 이게 "진짜 돈"의 병목인가):
  - 라이브 지정 전략 GLOBAL-TREND(SPY·IEF·GLD 역변동성 추세)의 forward 판정이 2022~2026
    KIS 일봉 창에서 "강건한 엣지 없음(3구간 중 0구간 승, 단순 보유에 −28%p)"으로 나왔다.
  - 그런데 그 창은 **강세장 편향**이다. 추세추종(방어적 현금화)의 엣지는 *수익으로 이김*이
    아니라 *약세장에서 자본을 지킴*이다 — 방어할 폭락이 없는 강세장 4년만 보면 보험료만 낸
    것처럼 보인다. 정직하게 재려면 **약세장을 포함한 깊은(레짐 완전) 데이터**가 필요하다.
  - 스펙 047 은 그 전략 *규칙*을 1871~2026 월간(Shiller S&P + 10년 국채 + 런던 금)으로
    이미 검증했지만(샤프 1.6~1.8·낙폭 5%), 그 검증은 **전체표본 + 2자산 vs 3자산** 비교였다.
    "단순 보유(buy-and-hold)를 표본 외(OOS)로, 구간마다, 강건하게 이기는가"는 *깊은 데이터에서
    측정된 적이 없다*. 바로 그 빈칸을 이 모듈이 닫는다.

무엇을 재나:
  깊은 월간 데이터를 겹치지 않는 연속 구간(기본 5년)으로 타일링하고, 각 구간에서 후보 추세
  전략과 **같은 자산의 단순 보유 벤치마크**를 나란히 요약(샤프·칼마·낙폭). 구간별 승/패를
  세고(레짐 강건성), 전체표본 판정을 낸다. 핵심 정직성: *수익 엣지*(샤프로 강건하게 이김)와
  *방어 엣지*(낙폭을 의미 있게 줄여 칼마를 올림)를 **분리**해 판정한다 — 추세추종의 진짜
  엣지는 후자이고, 강세장 단일 창은 구조적으로 그걸 못 본다.

사전 등록 기준(프로젝트 표준 `risk_managed_beta._classify` 와 동일):
  추세가 단순 보유 대비 *위험조정으로* 가치를 더하려면 ① 최대낙폭을 의미 있게 줄이고(≤0.8배),
  ② 칼마(수익/낙폭)를 올리고, ③ 샤프를 떨어뜨리지 않아야 한다. 셋 다면 방어 엣지. 거기에
  더해 샤프·CAGR 까지 단순 보유를 넘으면 수익 엣지.

이 모듈은 순수(부수효과 0)·결정론·비커널이다. 주문 0건, 돈 0 이동(연구/측정 전용).
미래 누출 없음(각 팩터 스트림은 t-1 까지의 정보만 쓰는 기존 빌더에서 온다).
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.analytics.global_trend import (
    global_trend_factors,
    gold_total_return_factors,
    risk_parity_global_factors,
)
from auto_invest.analytics.multi_asset_trend import (
    DEFAULT_BOND_MATURITY_YEARS,
    blend,
    bond_total_return_factors,
    diversified_trend_factors,
    equity_trend_factors,
)
from auto_invest.analytics.risk_managed_beta import (
    LegStats,
    MonthlyRow,
    market_total_return_factors,
    summarize,
)

# 방어 엣지 사전 등록 임계(프로젝트 표준과 동일).
DD_CUT_RATIO = 0.8  # 추세 낙폭 ≤ 0.8 × 단순보유 낙폭이어야 "의미 있는 방어".

# 판정 상수.
VERDICT_RETURN_EDGE = "RETURN_EDGE"  # 방어 + 샤프·CAGR 까지 단순 보유 초과(가장 강함).
VERDICT_DEFENSE_EDGE = "ROBUST_DEFENSE_EDGE"  # 낙폭 방어 + 칼마↑ + 샤프 비악화.
VERDICT_NO_EDGE = "NO_ROBUST_EDGE"  # 방어 기준 미달.


# ──────────────────────────── 구간 타일링 ────────────────────────────


def tile_windows(
    n: int, *, segment_months: int, min_window_months: int
) -> list[tuple[int, int]]:
    """길이 n 스트림을 겹치지 않는 연속 구간 (start, length) 으로 타일링한다.

    꼬리 나머지가 `min_window_months` 이상이면 독립 구간으로 유지하고, 미만이면 직전 구간에
    흡수시킨다(데이터를 버리지 않되 통계가 정의되는 최소 길이는 보장). segment_months 자체가
    min_window_months 미만이면 ValueError(설정 오류).
    """
    if segment_months < min_window_months:
        raise ValueError("segment_months must be >= min_window_months")
    if n < min_window_months:
        return []
    windows: list[tuple[int, int]] = []
    start = 0
    while start < n:
        length = min(segment_months, n - start)
        windows.append((start, length))
        start += length
    # 꼬리가 너무 짧으면 직전 구간에 흡수.
    if len(windows) >= 2 and windows[-1][1] < min_window_months:
        prev_start, prev_len = windows[-2]
        last_start, last_len = windows[-1]
        windows[-2] = (prev_start, prev_len + last_len)
        windows.pop()
    return windows


# ──────────────────────────── 구간 결과 ────────────────────────────


@dataclass(frozen=True)
class WindowResult:
    """한 walk-forward OOS 구간에서 후보 vs 단순 보유 벤치마크 요약."""

    index: int
    start_idx: int
    n_months: int
    candidate: LegStats
    benchmark: LegStats
    sharpe_win: bool  # 후보 샤프 > 벤치마크 샤프
    calmar_win: bool  # 후보 칼마 > 벤치마크 칼마(None 안전)
    return_win: bool  # 후보 CAGR > 벤치마크 CAGR
    dd_better: bool  # 후보 최대낙폭 < 벤치마크 최대낙폭
    defense_edge: bool  # 이 구간에서 방어 엣지 사전등록 기준 충족

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "n_months": self.n_months,
            "sharpe_win": self.sharpe_win,
            "calmar_win": self.calmar_win,
            "return_win": self.return_win,
            "dd_better": self.dd_better,
            "defense_edge": self.defense_edge,
            "candidate": self.candidate.as_dict(),
            "benchmark": self.benchmark.as_dict(),
        }


def _meets_defense(cand: LegStats, bench: LegStats) -> bool:
    """방어 엣지 사전등록 기준: 낙폭 ≤ 0.8배 + 칼마↑ + 샤프 비악화(칼마 None 이면 불충족)."""
    if cand.calmar is None or bench.calmar is None:
        return False
    dd_cut = cand.max_dd_pct <= DD_CUT_RATIO * bench.max_dd_pct
    calmar_up = cand.calmar > bench.calmar
    sharpe_ok = cand.sharpe >= bench.sharpe
    return dd_cut and calmar_up and sharpe_ok


def _eval_window(
    index: int,
    start_idx: int,
    cand_factors: list[float],
    bench_factors: list[float],
) -> WindowResult:
    cand = summarize(cand_factors)
    bench = summarize(bench_factors)
    calmar_win = (
        cand.calmar is not None
        and bench.calmar is not None
        and cand.calmar > bench.calmar
    )
    return WindowResult(
        index=index,
        start_idx=start_idx,
        n_months=len(cand_factors),
        candidate=cand,
        benchmark=bench,
        sharpe_win=cand.sharpe > bench.sharpe,
        calmar_win=calmar_win,
        return_win=cand.cagr_pct > bench.cagr_pct,
        dd_better=cand.max_dd_pct < bench.max_dd_pct,
        defense_edge=_meets_defense(cand, bench),
    )


# ──────────────────────────── 후보 강건성 ────────────────────────────


@dataclass(frozen=True)
class CandidateRobustness:
    """한 후보 전략의 단순 보유 대비 OOS 강건성 판정."""

    key: str
    label: str
    spec: str
    n_windows: int
    sharpe_wins: int
    calmar_wins: int
    return_wins: int
    defense_edge_wins: int
    full_period: LegStats
    full_benchmark: LegStats
    worst_window_cagr_pct: float | None  # 후보의 최악 구간 CAGR(방어가 보이는 곳)
    worst_window_cagr_pct_bench: float | None  # 벤치마크 최악 구간 CAGR
    verdict: str
    reason: str
    windows: tuple[WindowResult, ...]

    def as_dict(self, *, include_windows: bool = False) -> dict:
        out = {
            "key": self.key,
            "label": self.label,
            "spec": self.spec,
            "n_windows": self.n_windows,
            "sharpe_wins": self.sharpe_wins,
            "calmar_wins": self.calmar_wins,
            "return_wins": self.return_wins,
            "defense_edge_wins": self.defense_edge_wins,
            "worst_window_cagr_pct": (
                round(self.worst_window_cagr_pct, 2)
                if self.worst_window_cagr_pct is not None
                else None
            ),
            "worst_window_cagr_pct_bench": (
                round(self.worst_window_cagr_pct_bench, 2)
                if self.worst_window_cagr_pct_bench is not None
                else None
            ),
            "verdict": self.verdict,
            "reason": self.reason,
            "full_period": self.full_period.as_dict(),
            "full_benchmark": self.full_benchmark.as_dict(),
        }
        if include_windows:
            out["windows"] = [w.as_dict() for w in self.windows]
        return out


def _classify_robustness(
    full_cand: LegStats, full_bench: LegStats, *, sharpe_wins: int, n_windows: int
) -> tuple[str, str]:
    """전체표본 판정 — 수익 엣지 / 방어 엣지 / 엣지 없음(사전 등록).

    방어 엣지: 낙폭 ≤ 0.8배 + 칼마↑ + 샤프 비악화(프로젝트 표준 RISK_MANAGED_EDGE).
    수익 엣지: 방어 엣지 + 샤프·CAGR 까지 단순 보유 초과(드묾 — 방어형 추세엔 강한 신호).
    """
    if full_cand.calmar is None or full_bench.calmar is None:
        return VERDICT_NO_EDGE, "칼마 정의 불가(낙폭 0 또는 데이터 부족)"
    win_note = f"구간 샤프 승 {sharpe_wins}/{n_windows}"
    detail = (
        f"낙폭 {full_bench.max_dd_pct:.0f}%→{full_cand.max_dd_pct:.0f}%, "
        f"칼마 {full_bench.calmar:.2f}→{full_cand.calmar:.2f}, "
        f"샤프 {full_bench.sharpe:.2f}→{full_cand.sharpe:.2f}; {win_note}"
    )
    if not _meets_defense(full_cand, full_bench):
        fails = []
        if full_cand.max_dd_pct > DD_CUT_RATIO * full_bench.max_dd_pct:
            fails.append("낙폭 충분히 안 줄음")
        if not (full_cand.calmar > full_bench.calmar):
            fails.append("칼마 개선 없음")
        if not (full_cand.sharpe >= full_bench.sharpe):
            fails.append("샤프 악화")
        return VERDICT_NO_EDGE, "; ".join(fails) + f"; {detail}"
    if full_cand.sharpe > full_bench.sharpe and full_cand.cagr_pct > full_bench.cagr_pct:
        return VERDICT_RETURN_EDGE, "방어 + 샤프·CAGR 까지 초과; " + detail
    return VERDICT_DEFENSE_EDGE, "자본 방어(낙폭↓·칼마↑·샤프 비악화); " + detail


def evaluate_candidate(
    cand_factors: list[float],
    bench_factors: list[float],
    *,
    key: str,
    label: str,
    spec: str,
    segment_months: int,
    min_window_months: int,
) -> CandidateRobustness:
    """한 후보 팩터 스트림을 벤치마크 대비 구간별 + 전체표본으로 평가한다."""
    if len(cand_factors) != len(bench_factors):
        raise ValueError("candidate and benchmark factor streams must align")
    n = len(cand_factors)
    tiles = tile_windows(
        n, segment_months=segment_months, min_window_months=min_window_months
    )
    windows = tuple(
        _eval_window(
            i,
            start,
            cand_factors[start : start + length],
            bench_factors[start : start + length],
        )
        for i, (start, length) in enumerate(tiles)
    )
    full_cand = summarize(cand_factors)
    full_bench = summarize(bench_factors)
    sharpe_wins = sum(1 for w in windows if w.sharpe_win)
    calmar_wins = sum(1 for w in windows if w.calmar_win)
    return_wins = sum(1 for w in windows if w.return_win)
    defense_wins = sum(1 for w in windows if w.defense_edge)
    worst_cand = min((w.candidate.cagr_pct for w in windows), default=None)
    worst_bench = min((w.benchmark.cagr_pct for w in windows), default=None)
    verdict, reason = _classify_robustness(
        full_cand, full_bench, sharpe_wins=sharpe_wins, n_windows=len(windows)
    )
    return CandidateRobustness(
        key=key,
        label=label,
        spec=spec,
        n_windows=len(windows),
        sharpe_wins=sharpe_wins,
        calmar_wins=calmar_wins,
        return_wins=return_wins,
        defense_edge_wins=defense_wins,
        full_period=full_cand,
        full_benchmark=full_bench,
        worst_window_cagr_pct=worst_cand,
        worst_window_cagr_pct_bench=worst_bench,
        verdict=verdict,
        reason=reason,
        windows=windows,
    )


# ──────────────────────────── 전체 비교 ────────────────────────────


@dataclass(frozen=True)
class DeepWalkForwardReport:
    """깊은 OOS walk-forward 비교 — 추세 후보군 vs 같은 자산 단순 보유."""

    window: int  # 추세 SMA 개월
    segment_months: int
    n_months_total: int
    n_windows: int
    benchmark_label: str
    candidates: tuple[CandidateRobustness, ...]

    @property
    def champion(self) -> CandidateRobustness | None:
        """엣지 있는 후보 중 *위험조정 최강* — 샤프 → 칼마 순. 없으면 None.

        판정 등급(수익/방어)이 아니라 샤프·칼마로 고르는 이유: 역변동성처럼 변동성을 낮춰
        raw CAGR 이 낮아도 샤프가 높은 전략은 스펙 044 성장 최적 레버리지로 같은 낙폭 예산에서
        더 높은 복리를 낸다 — 레버리지 천장은 raw 수익이 아니라 샤프가 정한다. 등급은 엣지의
        *성격*(raw 수익까지 이기나)을 설명할 뿐 우열을 정하지 않는다.
        """
        edged = [c for c in self.candidates if c.verdict != VERDICT_NO_EDGE]
        if not edged:
            return None
        return max(
            edged,
            key=lambda c: (
                c.full_period.sharpe,
                c.full_period.calmar if c.full_period.calmar is not None else -1.0,
            ),
        )

    def as_dict(self, *, include_windows: bool = False) -> dict:
        champ = self.champion
        return {
            "schema_version": "1.0",
            "window": self.window,
            "segment_months": self.segment_months,
            "n_months_total": self.n_months_total,
            "n_windows": self.n_windows,
            "benchmark_label": self.benchmark_label,
            "champion_key": champ.key if champ else None,
            "champion_verdict": champ.verdict if champ else None,
            "candidates": [
                c.as_dict(include_windows=include_windows) for c in self.candidates
            ],
        }


def _equal_weight_buy_hold(
    eq_bh: list[float], bond_bh: list[float], gold_bh: list[float]
) -> list[float]:
    """등가중(1/3 씩) 매월 재조정 단순 보유 벤치마크 — 추세 게이트 없음, 항상 투자."""
    third = 1.0 / 3.0
    return blend([(third, eq_bh), (third, bond_bh), (third, gold_bh)])


def deep_walk_forward_compare(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    window: int = 10,
    segment_months: int = 60,
    min_window_months: int = 24,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
) -> DeepWalkForwardReport:
    """추세 후보군(스펙 042·043·047)을 *같은 자산 등가중 단순 보유* 대비 깊은 OOS 로 비교.

    `rows`(Shiller 월간)와 `gold_levels`(align_gold_levels 로 rows 와 정렬된 금 레벨)가 입력.
    벤치마크 = 등가중 3자산(주식·채권·금) 단순 보유(추세 게이트 없음). 라이브 forward 판정이
    쓴 "등가중 유니버스 보유"와 같은 잣대라 2022~2026 일봉 결과와 직접 대조된다.
    """
    if len(gold_levels) != len(rows):
        raise ValueError("gold_levels must align 1:1 with rows")

    eq_bh = market_total_return_factors(rows)
    bond_bh = bond_total_return_factors(rows, maturity_years=bond_maturity_years)
    gold_bh = gold_total_return_factors(gold_levels)
    benchmark = _equal_weight_buy_hold(eq_bh, bond_bh, gold_bh)

    specs: list[tuple[str, str, str, list[float]]] = [
        (
            "trend_equity",
            "주식 추세만 (스펙 042)",
            "042",
            equity_trend_factors(rows, window=window),
        ),
        (
            "trend_2asset",
            "2자산 분산 추세 주+채 (스펙 043)",
            "043",
            diversified_trend_factors(
                rows, window=window, bond_maturity_years=bond_maturity_years
            ),
        ),
        (
            "trend_3asset_fixed",
            "3자산 고정가중 추세 +금 (스펙 047)",
            "047",
            global_trend_factors(
                rows, gold_levels, window=window, bond_maturity_years=bond_maturity_years
            ),
        ),
        (
            "trend_3asset_invvol",
            "3자산 역변동성 추세 +금 (스펙 047, 라이브)",
            "047",
            risk_parity_global_factors(
                rows, gold_levels, window=window, bond_maturity_years=bond_maturity_years
            ),
        ),
    ]

    candidates = tuple(
        evaluate_candidate(
            factors,
            benchmark,
            key=key,
            label=label,
            spec=spec,
            segment_months=segment_months,
            min_window_months=min_window_months,
        )
        for key, label, spec, factors in specs
    )
    n_windows = candidates[0].n_windows if candidates else 0
    return DeepWalkForwardReport(
        window=window,
        segment_months=segment_months,
        n_months_total=len(benchmark),
        n_windows=n_windows,
        benchmark_label="등가중 3자산 단순 보유 (주식·채권·금 1/3씩, 추세 게이트 없음)",
        candidates=candidates,
    )


__all__ = [
    "CandidateRobustness",
    "DeepWalkForwardReport",
    "VERDICT_DEFENSE_EDGE",
    "VERDICT_NO_EDGE",
    "VERDICT_RETURN_EDGE",
    "WindowResult",
    "deep_walk_forward_compare",
    "evaluate_candidate",
    "tile_windows",
]
