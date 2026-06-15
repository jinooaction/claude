"""스펙 044 — 성장 최적 레버리지: 고정 자본에서 복리 성장률(CAGR)을 극대화.

운영자 지시(2026-06-05): "자본 규모가 클수록 큰 돈을 번다는 건 초등학생도 하는 말. 세계
최고 수준으로 *현재 자본에서* 복리 효과 등으로 수익을 극대화하라."

핵심 수학(왜 이게 정답인가):
  한 전략의 *복리 성장률 상한*은 그 전략의 **샤프 비율**로 정해진다. 연속복리 근사로
    g_max ≈ r_f + Sharpe² / 2      (성장 최적 레버리지 L* ≈ Sharpe / σ 에서 달성)
  즉 raw 수익이 아니라 샤프가 복리 성장의 천장을 정한다. 스펙 043 이 분산으로 샤프를
  1.18→1.58~1.81 로 올린 것이 바로 이 천장을 올린 것이고, 이제 그 천장을 *실제 복리 성장*으로
  바꾸는 마지막 단계 = **성장 최적 레버리지(=변동성 타깃팅, 부분 켈리)** 다.

세계 최고 수준의 미묘함(초등학생과의 차이):
  레버리지를 키우면 CAGR 이 *오르다가 다시 떨어진다* — 변동성 드래그(기하평균 페널티)
  때문이다. g(L) ≈ L·μ − (L·σ)²/2 − (L−1)·차입비용. L 에 대해 위로 볼록(hump) → 정확한
  최적 L* 가 존재하고, 그 너머는 *레버리지를 더 키울수록 복리로 돈을 잃는다*. "최대 레버리지"가
  아니라 이 최적점을 찾는 것이 기술이다.

이 모듈은 순수·결정론·비커널이다. 레버리지는 **연구/페이퍼 측정 전용** — 라이브 K1 포지션
캡(헌법 I-VII 안전 경계)을 건드리지 않는다. 라이브 레버리지는 별도 운영자 게이트(헌법 X.4).

차입비용 정직 모델: L>1 이면 (L−1) 만큼을 차입금리(무위험 + 스프레드)로 빌린다. L<1 이면
(1−L) 를 현금(무위험)으로 둔다. 무위험/차입 기준은 Shiller 장기금리(스펙 042/043 와 동일
한계 — 단기 T-bill 보다 약간 후하나 두 비교에 동일 적용이라 *상대* 판정은 공정).
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.analytics.multi_asset_trend import carry_forward_rates
from auto_invest.analytics.risk_managed_beta import (
    MonthlyRow,
    equity_curve,
    summarize,
)

MONTHS_PER_YEAR = 12
DEFAULT_BORROW_SPREAD_ANNUAL = 0.01  # 차입금리 = 무위험 + 1%(브로커 마진 현실 근사, 보수적)


def risk_free_monthly(rows: list[MonthlyRow]) -> list[float]:
    """월간 무위험 수익률(소수), 길이 N-1. period t 는 직전 월 금리(t-1)를 쓴다(미래 누출 0).

    금리 결측은 carry_forward_rates 로 메운다. 금리 0이면 0%(보수적).
    """
    rates = carry_forward_rates(rows)
    return [rates[t - 1] / 100.0 / MONTHS_PER_YEAR for t in range(1, len(rows))]


def lever_factors(
    strat_factors: list[float],
    rf_monthly: list[float],
    *,
    leverage: float,
    borrow_spread_annual: float = DEFAULT_BORROW_SPREAD_ANNUAL,
) -> list[float]:
    """전략 그로스 팩터에 레버리지 L 을 얹은 *순* 월간 팩터(차입비용 반영), 길이 동일.

    levered_factor_t = 1 + L·r_t − (L−1)·fin_t
      r_t   = strat_factor_t − 1 (전략 월수익)
      fin_t = 차입금리(L≥1: 무위험+스프레드) 또는 무위험(L<1: 남는 현금 수익)
    L=1 이면 전략 그대로(차입·현금 0). L>1 은 (L−1) 차입, L<1 은 (1−L) 현금.
    """
    if len(strat_factors) != len(rf_monthly):
        raise ValueError("length mismatch")
    spread_m = borrow_spread_annual / MONTHS_PER_YEAR
    out: list[float] = []
    for f, rf in zip(strat_factors, rf_monthly, strict=True):
        r = f - 1.0
        fin = (rf + spread_m) if leverage >= 1.0 else rf
        out.append(1.0 + leverage * r - (leverage - 1.0) * fin)
    return out


@dataclass(frozen=True)
class GrowthPoint:
    """한 레버리지에서의 복리 성장·위험 요약."""

    leverage: float
    cagr_pct: float
    vol_pct: float
    sharpe: float
    max_dd_pct: float
    calmar: float | None

    def as_dict(self) -> dict:
        return {
            "leverage": round(self.leverage, 3),
            "cagr_pct": round(self.cagr_pct, 2),
            "vol_pct": round(self.vol_pct, 2),
            "sharpe": round(self.sharpe, 3),
            "max_dd_pct": round(self.max_dd_pct, 2),
            "calmar": round(self.calmar, 3) if self.calmar is not None else None,
        }


def growth_point(
    strat_factors: list[float],
    rf_monthly: list[float],
    *,
    leverage: float,
    borrow_spread_annual: float = DEFAULT_BORROW_SPREAD_ANNUAL,
) -> GrowthPoint:
    """레버리지 L 적용 후 CAGR·변동성·샤프·최대낙폭·칼마(스펙 042 summarize 재사용).

    파산 처리(정직): 레버리지가 과해 단월 손실이 자본을 초과하면(levered_factor ≤ 0) 자산이
    0 이하로 무너진다 = 파산. 이 경우 CAGR −100%·최대낙폭 100%·칼마 없음으로 정직히 보고한다
    (이게 "레버리지를 더 키우면 돈을 잃는다"의 극단 — 단 한 번의 나쁜 달에 청산된다).
    """
    levered = lever_factors(
        strat_factors, rf_monthly, leverage=leverage,
        borrow_spread_annual=borrow_spread_annual,
    )
    curve = equity_curve(levered)
    if any(f <= 0.0 for f in levered) or min(curve) <= 0.0:
        rets = [f - 1.0 for f in levered]
        n = len(rets)
        vol_pct = 0.0
        if n >= 2:
            mean = sum(rets) / n
            var = sum((r - mean) ** 2 for r in rets) / (n - 1)
            vol_pct = (var ** 0.5) * (MONTHS_PER_YEAR ** 0.5) * 100.0
        return GrowthPoint(
            leverage=leverage, cagr_pct=-100.0, vol_pct=vol_pct,
            sharpe=0.0, max_dd_pct=100.0, calmar=None,
        )
    s = summarize(levered, in_market=None)
    return GrowthPoint(
        leverage=leverage,
        cagr_pct=s.cagr_pct,
        vol_pct=s.vol_pct,
        sharpe=s.sharpe,
        max_dd_pct=s.max_dd_pct,
        calmar=s.calmar,
    )


def growth_curve(
    strat_factors: list[float],
    rf_monthly: list[float],
    *,
    leverages: list[float],
    borrow_spread_annual: float = DEFAULT_BORROW_SPREAD_ANNUAL,
) -> list[GrowthPoint]:
    """레버리지 격자에 대한 성장 곡선 — CAGR 이 오르다 떨어지는 hump 를 드러낸다."""
    return [
        growth_point(
            strat_factors, rf_monthly, leverage=lev,
            borrow_spread_annual=borrow_spread_annual,
        )
        for lev in leverages
    ]


def growth_optimal(points: list[GrowthPoint]) -> GrowthPoint:
    """CAGR(복리 성장률)을 최대로 하는 점 = 성장 최적 레버리지(부분 켈리의 풀켈리 끝).

    주의: 이 점은 보통 낙폭이 매우 크다(풀켈리는 실무에서 과격). 운영자에겐 낙폭 제약
    최적(`drawdown_constrained_optimal`)을 함께 보고하는 것이 정직하다.
    """
    if not points:
        raise ValueError("empty curve")
    return max(points, key=lambda p: p.cagr_pct)


def drawdown_constrained_optimal(
    points: list[GrowthPoint], *, max_dd_pct: float
) -> GrowthPoint | None:
    """최대낙폭 ≤ max_dd_pct 제약 아래 CAGR 을 최대로 하는 점(실무적 최적).

    "낙폭을 이 정도까지는 견딘다"는 위험 예산을 주면, 그 예산 안에서 복리 성장을 극대화하는
    레버리지를 고른다. 제약을 만족하는 점이 없으면 None(레버리지 1 도 한도 초과 = 드문 경우).
    """
    feasible = [p for p in points if p.max_dd_pct <= max_dd_pct]
    if not feasible:
        return None
    return max(feasible, key=lambda p: p.cagr_pct)


@dataclass(frozen=True)
class LeverageComparison:
    """두 전략(예: 단일 주식 추세 vs 분산 추세)의 성장 최적 레버리지 비교.

    같은 낙폭 예산에서 어느 쪽이 더 높은 복리 성장을 내는지 = 샤프가 높은 쪽이 이긴다는 것을
    드러낸다(고정 자본 복리 극대화의 핵심: raw 수익이 아니라 샤프가 천장을 정한다).
    """

    label_a: str
    label_b: str
    unlevered_a: GrowthPoint
    unlevered_b: GrowthPoint
    dd_opt_a: GrowthPoint | None
    dd_opt_b: GrowthPoint | None
    max_dd_budget_pct: float

    def as_dict(self) -> dict:
        return {
            "max_dd_budget_pct": self.max_dd_budget_pct,
            "unlevered": {
                self.label_a: self.unlevered_a.as_dict(),
                self.label_b: self.unlevered_b.as_dict(),
            },
            "drawdown_constrained_optimal": {
                self.label_a: self.dd_opt_a.as_dict() if self.dd_opt_a else None,
                self.label_b: self.dd_opt_b.as_dict() if self.dd_opt_b else None,
            },
        }


def compare_leverage(
    label_a: str,
    factors_a: list[float],
    label_b: str,
    factors_b: list[float],
    rf_monthly: list[float],
    *,
    leverages: list[float],
    max_dd_budget_pct: float = 30.0,
    borrow_spread_annual: float = DEFAULT_BORROW_SPREAD_ANNUAL,
) -> LeverageComparison:
    """두 전략을 같은 낙폭 예산에서 레버리지 최적화해 복리 성장을 비교."""
    curve_a = growth_curve(
        factors_a, rf_monthly, leverages=leverages,
        borrow_spread_annual=borrow_spread_annual,
    )
    curve_b = growth_curve(
        factors_b, rf_monthly, leverages=leverages,
        borrow_spread_annual=borrow_spread_annual,
    )
    unlev_a = growth_point(factors_a, rf_monthly, leverage=1.0,
                           borrow_spread_annual=borrow_spread_annual)
    unlev_b = growth_point(factors_b, rf_monthly, leverage=1.0,
                           borrow_spread_annual=borrow_spread_annual)
    return LeverageComparison(
        label_a=label_a,
        label_b=label_b,
        unlevered_a=unlev_a,
        unlevered_b=unlev_b,
        dd_opt_a=drawdown_constrained_optimal(curve_a, max_dd_pct=max_dd_budget_pct),
        dd_opt_b=drawdown_constrained_optimal(curve_b, max_dd_pct=max_dd_budget_pct),
        max_dd_budget_pct=max_dd_budget_pct,
    )


@dataclass(frozen=True)
class LeverageHeadroom:
    """한 전략의 낙폭 예산 내 레버리지 여유 — 무레버리지 대비 복리 성장 상승.

    무레버리지(L=1) 대비, 운영자 낙폭 예산 안에서 복리 성장(CAGR)을 최대화하는 레버리지와
    그때의 CAGR 을 보고한다. 무레버리지 낙폭이 낮을수록 더 큰 레버리지를 안전하게 얹어 더 높은
    복리를 낸다 = 레버리지 여유가 크다(스펙 047 발견 — 라이브 전략 낙폭 5.3% — 의 '진짜 돈'
    귀결: 같은 위험 예산에서 복리 천장을 올리는 것).
    """

    label: str
    max_dd_budget_pct: float
    unlevered: GrowthPoint
    dd_optimal: GrowthPoint | None  # 예산 내 최적(없으면 L=1 도 예산 초과 = 드묾)

    @property
    def leverage_multiple(self) -> float | None:
        return self.dd_optimal.leverage if self.dd_optimal else None

    @property
    def cagr_uplift_pct(self) -> float | None:
        """예산 내 최적 CAGR − 무레버리지 CAGR(레버리지가 더해준 복리 성장)."""
        if self.dd_optimal is None:
            return None
        return self.dd_optimal.cagr_pct - self.unlevered.cagr_pct

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "max_dd_budget_pct": self.max_dd_budget_pct,
            "unlevered": self.unlevered.as_dict(),
            "dd_optimal": self.dd_optimal.as_dict() if self.dd_optimal else None,
            "leverage_multiple": (
                round(self.leverage_multiple, 3)
                if self.leverage_multiple is not None
                else None
            ),
            "cagr_uplift_pct": (
                round(self.cagr_uplift_pct, 2)
                if self.cagr_uplift_pct is not None
                else None
            ),
        }


def leverage_headroom(
    label: str,
    strat_factors: list[float],
    rf_monthly: list[float],
    *,
    leverages: list[float],
    max_dd_budget_pct: float,
    borrow_spread_annual: float = DEFAULT_BORROW_SPREAD_ANNUAL,
) -> LeverageHeadroom:
    """한 전략의 낙폭 예산 내 성장 최적 레버리지 여유를 잰다(스펙 044 엔진 재사용).

    `leverages` 격자에 1.0 이 없어도 무레버리지 점은 별도로 정확히 계산해 비교 기준으로 쓴다.
    """
    curve = growth_curve(
        strat_factors, rf_monthly, leverages=leverages,
        borrow_spread_annual=borrow_spread_annual,
    )
    unlev = growth_point(
        strat_factors, rf_monthly, leverage=1.0,
        borrow_spread_annual=borrow_spread_annual,
    )
    dd_opt = drawdown_constrained_optimal(curve, max_dd_pct=max_dd_budget_pct)
    return LeverageHeadroom(
        label=label,
        max_dd_budget_pct=max_dd_budget_pct,
        unlevered=unlev,
        dd_optimal=dd_opt,
    )


def rank_leverage_headroom(items: list[LeverageHeadroom]) -> list[LeverageHeadroom]:
    """예산 내 최적 CAGR 내림차순 정렬(최적 없는 항목은 뒤로) — 같은 낙폭 예산 비교용."""

    def _key(h: LeverageHeadroom) -> tuple[int, float]:
        if h.dd_optimal is None:
            return (1, 0.0)
        return (0, -h.dd_optimal.cagr_pct)

    return sorted(items, key=_key)


__all__ = [
    "DEFAULT_BORROW_SPREAD_ANNUAL",
    "GrowthPoint",
    "LeverageComparison",
    "LeverageHeadroom",
    "compare_leverage",
    "drawdown_constrained_optimal",
    "growth_curve",
    "growth_optimal",
    "growth_point",
    "lever_factors",
    "leverage_headroom",
    "rank_leverage_headroom",
    "risk_free_monthly",
]
