"""스펙 054 — 비상관 수익원: 밸류(CAPE) 타이밍 + 추세와의 분산 이득 측정.

배경(왜 이게 "세계 최고 수준"의 다음 차원인가):
  현재 forward 토너먼트 6트랙이 *전부 추세추종(모멘텀) 계열*이다(추세 ON/OFF·위험관리 베타·
  멀티에셋 추세·글로벌 추세·확대·고정가중). 추세추종의 끈질긴 엣지는 폭락 방어(자본 보존)
  이지만, 단일 차원이라 추세가 실패하는 regime(빠른 V자 반등·추세 없는 횡보)엔 약하다.
  세계 최고 수준 퀀트(AQR "Value and Momentum Everywhere", 2013)의 정석은 모멘텀과 *음의
  상관*인 밸류를 결합하는 것 — 둘은 서로 다른 시점에 작동해(모멘텀은 추세장, 밸류는 평균
  회귀장) 결합하면 *같은 수익을 더 낮은 변동성*(샤프↑)으로 낸다. 분산은 금융 유일의 공짜 점심.

밸류 = 경기조정 PER(Shiller CAPE = PE10). 주식이 *펀더멘털(10년 실질수익) 대비* 비쌀 때
비중을 줄이고 쌀 때 늘린다. 추세(가격 *방향*)와 밸류(가격 *수준*)는 강세장 후반에 정반대
신호를 낸다(추세=보유, 밸류=축소) → 음의 상관. 그 음의 상관이 곧 분산 이득의 원천이다.

데이터: Shiller 월간(`parse_shiller` 의 earnings·cpi, 1871~). CAPE_t = (P_t/CPI_t) /
mean(E_s/CPI_s, s∈[t-120,t-1]). 실질화(CPI 조정)로 인플레기 명목수익 왜곡 제거. 추가 데이터 0.

미래 누출 없음: period t 의 밸류 노출은 t-1 까지의 CAPE 분포만 쓴다(결정론).
이 모듈은 순수(부수효과 0)·비커널이다. 주문 0건, 돈 0 이동(연구/측정 전용).
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.analytics.multi_asset_trend import (
    DEFAULT_BOND_MATURITY_YEARS,
    bond_total_return_factors,
    correlation,
)
from auto_invest.analytics.risk_managed_beta import (
    LegStats,
    MonthlyRow,
    cash_factors,
    combined_factors,
    market_total_return_factors,
    overlay_factors,
    summarize,
    trend_in_market,
)

DEFAULT_SMOOTH_MONTHS = 120  # CAPE 실질수익 평활 창(10년, Shiller 표준).
DEFAULT_MIN_HISTORY = 60  # 백분위 판단 최소 CAPE 표본(5년) — 그전엔 중립(풀투자).
DEFAULT_CORR_MAX = 0.6  # 분산 이득으로 인정할 추세↔밸류 상관 상한.

VERDICT_EDGE = "DIVERSIFICATION_EDGE"  # 결합이 단독보다 샤프↑ + 상관 낮음.
VERDICT_NONE = "NO_DIVERSIFICATION_BENEFIT"
VERDICT_INSUFFICIENT = "INSUFFICIENT"


# ──────────────────────────────── CAPE ────────────────────────────────


def real_earnings_deflated(rows: list[MonthlyRow]) -> list[float | None]:
    """각 행의 실질수익 프록시 E_s/CPI_s. CPI>0·E>0 인 행만 유효(그 외 None). 길이 N."""
    out: list[float | None] = []
    for r in rows:
        out.append(r.earnings / r.cpi if r.cpi > 0 and r.earnings > 0 else None)
    return out


def cape(
    rows: list[MonthlyRow], *, smooth_months: int = DEFAULT_SMOOTH_MONTHS
) -> list[float | None]:
    """경기조정 PER(Shiller CAPE) 시계열, 길이 N(정의 불가 행은 None).

    CAPE_t = (P_t / CPI_t) / mean(E_s/CPI_s for s in [t-smooth_months, t-1], 유효행).
    실질화(CPI 조정)로 인플레 시기 명목수익 왜곡을 제거한다. 미래 누출 0: t 의 CAPE 는 t 까지의
    가격과 *과거* 평활창 수익만 쓴다. 평활창 유효표본이 비거나 가격/CPI 결측이면 None(밸류 판단
    불가 → 호출부가 중립 노출로 처리). smooth_months>=1.
    """
    if smooth_months < 1:
        raise ValueError("smooth_months must be >= 1")
    defl = real_earnings_deflated(rows)
    out: list[float | None] = []
    for t in range(len(rows)):
        r = rows[t]
        if r.cpi <= 0 or r.price <= 0 or t < smooth_months:
            out.append(None)
            continue
        window = [d for d in defl[t - smooth_months : t] if d is not None]
        if not window:
            out.append(None)
            continue
        avg = sum(window) / len(window)
        out.append((r.price / r.cpi) / avg if avg > 0 else None)
    return out


# ─────────────────────────── 밸류 타이밍 노출 ───────────────────────────


def value_exposure(
    rows: list[MonthlyRow],
    *,
    smooth_months: int = DEFAULT_SMOOTH_MONTHS,
    min_history_months: int = DEFAULT_MIN_HISTORY,
) -> list[float]:
    """밸류 타이밍 월간 노출 e_t ∈ [0,1], 길이 N-1(market factor 와 정렬).

    e 는 현재 CAPE 의 *확장 역사 백분위*의 역 — 주식이 역사 대비 비쌀수록(높은 백분위) 낮은
    노출, 쌀수록 높은 노출. period t(=factor 인덱스 i=t-1)의 노출은 CAPE[0..i] 만 쓴다
    (미래 누출 0 — period t 진입은 직전 월 종가까지의 정보로 결정). CAPE 부족/표본 <
    min_history 면 중립(1.0=풀투자, 추세의 '판단 불가→투자'와 같은 보수적 철학).
    """
    capes = cape(rows, smooth_months=smooth_months)
    out: list[float] = []
    for i in range(len(rows) - 1):
        cur = capes[i]
        if cur is None:
            out.append(1.0)
            continue
        hist = [c for c in capes[: i + 1] if c is not None]
        if len(hist) < min_history_months:
            out.append(1.0)
            continue
        below = sum(1 for c in hist if c < cur)
        pct = below / len(hist)  # 비쌀수록 1 에 가까움
        out.append(max(0.0, min(1.0, 1.0 - pct)))
    return out


def value_timing_factors(
    rows: list[MonthlyRow],
    *,
    smooth_months: int = DEFAULT_SMOOTH_MONTHS,
    min_history_months: int = DEFAULT_MIN_HISTORY,
) -> list[float]:
    """밸류 타이밍 전략 월간 그로스 팩터(길이 N-1): e_t*시장 + (1-e_t)*현금.

    노출이 연속(0..1)이라 추세의 이진(0/1) 게이트와 달리 *부드럽게* 비중을 조절한다 — 고평가
    구간서 일부만 빼고(전부 현금 아님) 저평가서 풀투자. 거래비용은 이 측정 단계에선 미반영
    (상관·결합 샤프가 핵심 질문이고, 비용은 트랙 배선 단계서 `apply_exposure_costs` 로 반영).
    """
    market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    exposure = value_exposure(
        rows, smooth_months=smooth_months, min_history_months=min_history_months
    )
    return combined_factors(market, cash, exposure)


# ─────────────────────────── 캐리(자산 선택) ───────────────────────────


def earnings_yield(rows: list[MonthlyRow]) -> list[float | None]:
    """주식 수익수익률 E/P(명목), 길이 N. P<=0 또는 E<=0 이면 None(캐리 판단 불가)."""
    return [
        r.earnings / r.price if r.price > 0 and r.earnings > 0 else None for r in rows
    ]


def carry_rotation_factors(
    rows: list[MonthlyRow],
    *,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
) -> list[float]:
    """주식 캐리(E/P) vs 채권 캐리(장기금리) 로테이션 월간 그로스 팩터(길이 N-1).

    period t 의 보유 자산은 t-1 의 *캐리 우위*로 정한다 — 주식 수익수익률 E/P 가 채권 만기
    수익률(장기금리)보다 높으면 주식, 낮으면 채권(Fed-model 스타일 자산 로테이션). 추세추종은
    "주식을 *언제* 들지"(절대 타이밍)인데 캐리 로테이션은 "주식이냐 *채권이냐*"(자산 선택)라
    구조적으로 더 직교한다 — 그게 진짜 비상관 수익원의 후보 근거다. E/P 또는 금리 결측이면
    주식 보유(베타 중립). 미래 누출 0: t 결정은 t-1 까지의 수익수익률·금리만 쓴다.
    """
    eq = market_total_return_factors(rows)
    bond = bond_total_return_factors(rows, maturity_years=bond_maturity_years)
    ey = earnings_yield(rows)
    out: list[float] = []
    for t in range(1, len(rows)):
        eyp = ey[t - 1]
        bond_yield = rows[t - 1].long_rate / 100.0
        if eyp is None or rows[t - 1].long_rate <= 0:
            out.append(eq[t - 1])  # 정보 부족 → 주식(베타 중립)
        elif eyp >= bond_yield:
            out.append(eq[t - 1])  # 주식 캐리 우위
        else:
            out.append(bond[t - 1])  # 채권 캐리 우위
    return out


# ──────────────────── 추세 × (밸류·캐리) 분산 이득 측정 ────────────────────


@dataclass(frozen=True)
class DiversificationStats:
    """추세 vs 후보(밸류·캐리) 결합 분산 이득 — 어느 후보든 같은 잣대로 정직히 비교."""

    candidate_label: str  # "밸류(CAPE)" / "캐리(E/P vs 금리)"
    trend: LegStats  # S&P 추세 타이밍(스펙 042)
    candidate: LegStats  # 후보 수익원(밸류 또는 캐리)
    combined: LegStats  # blend_weight*추세 + (1-blend_weight)*후보
    buy_hold: LegStats  # 단순 보유(맥락)
    correlation: float | None  # 추세 수익 ↔ 후보 수익 상관(낮을수록 분산 이득 큼)
    blend_weight: float
    verdict: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "candidate_label": self.candidate_label,
            "verdict": self.verdict,
            "reason": self.reason,
            "blend_weight": self.blend_weight,
            "correlation": (
                round(self.correlation, 3) if self.correlation is not None else None
            ),
            "trend": self.trend.as_dict(),
            "candidate": self.candidate.as_dict(),
            "combined": self.combined.as_dict(),
            "buy_hold": self.buy_hold.as_dict(),
        }


def _fmt_corr(corr: float | None) -> str:
    return f"{corr:.2f}" if corr is not None else "—"


def _classify_diversification(
    trend: LegStats,
    candidate: LegStats,
    combined: LegStats,
    corr: float | None,
    *,
    corr_max: float = DEFAULT_CORR_MAX,
) -> tuple[str, str]:
    """후보가 추세에 *분산 이득*을 더하는가(사전 등록 기준).

    결합(50/50)이 ① 두 단독 전략 각각의 샤프보다 높고(위험조정 우위) ② 추세↔후보 상관이 낮으면
    (corr < corr_max — 진짜 비상관 수익원) DIVERSIFICATION_EDGE. 분산의 본질은 *낮은 상관의 두
    수익원을 합쳐 샤프를 올림*이라 이 둘을 함께 본다(높은 샤프가 단지 한쪽 우연이 아님을 상관이
    보증). 샤프 정의 불가(데이터 부족)면 INSUFFICIENT.
    """
    if combined.n_months < 2:
        return VERDICT_INSUFFICIENT, "결합 표본 부족(샤프 정의 불가)"
    best_solo = max(trend.sharpe, candidate.sharpe)
    sharpe_up = combined.sharpe > best_solo
    corr_low = corr is not None and corr < corr_max
    detail = (
        f"추세샤프 {trend.sharpe:.2f}·후보샤프 {candidate.sharpe:.2f}→결합 "
        f"{combined.sharpe:.2f}(최고단독 {best_solo:.2f}), 상관 {_fmt_corr(corr)}"
    )
    if sharpe_up and corr_low:
        return VERDICT_EDGE, detail
    fails: list[str] = []
    if not sharpe_up:
        fails.append("결합 샤프가 단독 최고를 못 넘음")
    if not corr_low:
        fails.append(f"상관 {_fmt_corr(corr)} ≥ {corr_max}(비상관 아님)")
    return VERDICT_NONE, "; ".join(fails) + f"; {detail}"


def _measure_against_trend(
    rows: list[MonthlyRow],
    candidate_f: list[float],
    candidate_label: str,
    *,
    window: int,
    blend_weight: float,
    corr_max: float,
) -> DiversificationStats:
    """공용: S&P 추세 타이밍 vs 후보 vs 결합을 같은 기간 비교(밸류·캐리 공통 잣대).

    같은 베타(S&P)에 추세 신호와 후보 신호를 얹어 *사과 대 사과*로 상관·결합 샤프를 잰다.
    `candidate_f` 는 추세 스트림(길이 N-1)과 정렬돼야 한다. 미래 누출 0(각 스트림이 보장).
    """
    if not 0.0 <= blend_weight <= 1.0:
        raise ValueError("blend_weight must be in [0, 1]")
    market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    trend_f = overlay_factors(market, cash, trend_in_market(rows, window))
    if len(candidate_f) != len(trend_f):
        raise ValueError("candidate stream must align with the trend stream")
    combined_f = [
        blend_weight * t + (1.0 - blend_weight) * c
        for t, c in zip(trend_f, candidate_f, strict=True)
    ]
    leg_trend = summarize(trend_f)
    leg_candidate = summarize(candidate_f)
    leg_combined = summarize(combined_f)
    leg_bh = summarize(market)
    corr = correlation(trend_f, candidate_f)
    verdict, reason = _classify_diversification(
        leg_trend, leg_candidate, leg_combined, corr, corr_max=corr_max
    )
    return DiversificationStats(
        candidate_label=candidate_label,
        trend=leg_trend,
        candidate=leg_candidate,
        combined=leg_combined,
        buy_hold=leg_bh,
        correlation=corr,
        blend_weight=blend_weight,
        verdict=verdict,
        reason=reason,
    )


def measure_value_diversification(
    rows: list[MonthlyRow],
    *,
    window: int = 10,
    smooth_months: int = DEFAULT_SMOOTH_MONTHS,
    min_history_months: int = DEFAULT_MIN_HISTORY,
    blend_weight: float = 0.5,
    corr_max: float = DEFAULT_CORR_MAX,
) -> DiversificationStats:
    """추세 타이밍 vs 밸류(CAPE) 타이밍 vs 결합 — 밸류가 비상관 수익원인지 실측."""
    value_f = value_timing_factors(
        rows, smooth_months=smooth_months, min_history_months=min_history_months
    )
    return _measure_against_trend(
        rows, value_f, "밸류(CAPE)", window=window, blend_weight=blend_weight,
        corr_max=corr_max,
    )


def measure_carry_diversification(
    rows: list[MonthlyRow],
    *,
    window: int = 10,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
    blend_weight: float = 0.5,
    corr_max: float = DEFAULT_CORR_MAX,
) -> DiversificationStats:
    """추세 타이밍 vs 캐리(E/P vs 금리 로테이션) vs 결합 — 캐리가 비상관 수익원인지 실측."""
    carry_f = carry_rotation_factors(rows, bond_maturity_years=bond_maturity_years)
    return _measure_against_trend(
        rows, carry_f, "캐리(E/P vs 금리)", window=window, blend_weight=blend_weight,
        corr_max=corr_max,
    )


__all__ = [
    "DEFAULT_CORR_MAX",
    "DEFAULT_MIN_HISTORY",
    "DEFAULT_SMOOTH_MONTHS",
    "VERDICT_EDGE",
    "VERDICT_INSUFFICIENT",
    "VERDICT_NONE",
    "DiversificationStats",
    "cape",
    "carry_rotation_factors",
    "earnings_yield",
    "measure_carry_diversification",
    "measure_value_diversification",
    "real_earnings_deflated",
    "value_exposure",
    "value_timing_factors",
]
