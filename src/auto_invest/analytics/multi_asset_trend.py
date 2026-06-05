"""스펙 043 — 멀티에셋 분산 추세추종: 검증된 단일 자산 엣지를 *세계 최고 수준* 차원으로 확장.

배경(정직한 우선순위 판단):
  - 종목 선택 알파는 측정상 0(스펙 041, 정보계수 IC≈0). 가격 팩터로 인덱스를 못 이긴다.
  - 유일하게 끈질긴 엣지 = 추세추종의 자본 방어(스펙 042, Shiller 155년 9/9 견고).
  - 그러나 그 엣지가 지금은 *단일 자산군(미국 주식 베타)* 에만 적용된다. SPY·QQQ 는 사실상
    같은 자산(상관 ~0.95). 단일 지수 추세 타이밍은 소매(retail) 수준이다.

세계 최고 수준과의 진짜 격차 = **멀티에셋 분산 추세추종**. 금융에서 가장 크고 끈질긴 "공짜
점심"은 비상관 수익 흐름의 분산이다(Faber, "A Quantitative Approach to Tactical Asset
Allocation"; AQR/Man-AHL 의 managed futures). 여러 비상관 자산(주식·채권 …)에 각각 추세
오버레이를 얹고 합치면, 추세 신호가 서로 다른 시점에 켜지고 자산 자체가 비상관이라 단일
자산 추세보다 위험조정 수익(샤프·칼마)이 더 높다.

결정적: 추가 데이터 없이 검증 가능하다. 스펙 042 가 쓰는 그 GitHub Shiller CSV 에 **10년
국채 수익률(Long Interest Rate)이 1871년부터** 들어있다. 그 수익률 시계열로 *상수만기 10년
국채 총수익 프록시*를 만들면, 주식(베타)과 채권(듀레이션)이라는 두 비상관 자산에 각각 추세
타이밍을 얹어 *155년 실폭락 데이터로* 분산 효과를 정직하게 잴 수 있다.

이 모듈은 순수(부수효과 0)·결정론이며 비커널이다. 주문 0건, 돈 0 이동(연구/측정 전용).
미래 누출 없음: period t 의 매수/현금·재평가 결정은 t-1 말까지의 정보만 쓴다.

채권 프록시의 정직한 한계(명시):
  - 상수만기 10년 par 채권을 연복리·연쿠폰으로 근사하고 매월 새 10년으로 롤(상수만기 지수
    방법론). 듀레이션을 약간 과대평가할 수 있다.
  - "현금"(추세 아래)은 스펙 042 와 같은 한계 — 장기금리/12 를 현금 수익으로 쓴다(진짜
    단기 T-bill 보다 약간 후함). 두 다리에 동일 적용이라 *상대* 비교는 공정하다.
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.analytics.risk_managed_beta import (
    LegStats,
    MonthlyRow,
    cash_factors,
    equity_curve,
    market_total_return_factors,
    summarize,
    trend_in_market,
)

MONTHS_PER_YEAR = 12
DEFAULT_BOND_MATURITY_YEARS = 10


# ───────────────────────────── 채권 총수익 프록시 ──────────────────────────────


def carry_forward_rates(rows: list[MonthlyRow]) -> list[float]:
    """장기금리(연 %)를 결측(0/미기재) 시 직전 유효값으로 캐리한 시계열(길이 N).

    Shiller 최근 달은 Long Interest Rate 가 0(미기재)일 수 있다 → 직전 유효 금리를 잇는다
    (현실적으로 금리는 월 단위로 천천히 변한다). 초반에 아직 유효 금리가 없으면 0(현금 0%).
    """
    out: list[float] = []
    last = 0.0
    for r in rows:
        if r.long_rate > 0:
            last = r.long_rate
        out.append(last)
    return out


def _par_bond_price(coupon: float, ytm: float, maturity_years: int) -> float:
    """액면 1, 연쿠폰 `coupon`, 만기 `maturity_years`인 채권을 수익률 `ytm`(연, 소수)로
    평가한 가격(연복리). ytm<=0 이면 무할인 근사(쿠폰 합 + 액면).

    par 발행(coupon==ytm)이면 정확히 1.0 을 돌려준다(par 채권 정의).
    """
    if ytm <= 0:
        return 1.0 + coupon * maturity_years
    disc = (1.0 + ytm) ** (-maturity_years)
    return coupon * (1.0 - disc) / ytm + disc


def bond_total_return_factors(
    rows: list[MonthlyRow], *, maturity_years: int = DEFAULT_BOND_MATURITY_YEARS
) -> list[float]:
    """상수만기 10년 국채의 월간 총수익 그로스 팩터(1+r), 길이 N-1.

    매월 시작에 직전 달 금리 y0(연 %)로 발행된 par 10년 채권을 보유한다. 한 달 뒤 금리가
    y1 으로 바뀌면 같은 채권을 y1 으로 재평가(상수만기=매월 새 10년으로 롤) → 가격변화 +
    한 달치 쿠폰(y0/12). factor = P(y1; coupon=y0, N) + y0/12.

      - y1==y0 → 가격 1.0, factor = 1 + y0/12 (순수 쿠폰; 금리 불변).
      - y1<y0 (금리 하락) → 가격>1 (채권 상승; 듀레이션 이득).
      - y1>y0 (금리 상승) → 가격<1 (채권 하락; 2022 같은 구간).

    금리 결측은 carry_forward_rates 로 메운다. y0==0(초반 유효 금리 없음)이면 현금(1.0).
    미래 누출 없음: factor_t 는 y0=rate[t-1], y1=rate[t] 만 쓴다(둘 다 month-end 관측).
    """
    rates = [r / 100.0 for r in carry_forward_rates(rows)]  # 연 %→소수
    factors: list[float] = []
    for t in range(1, len(rows)):
        y0 = rates[t - 1]
        y1 = rates[t]
        if y0 <= 0.0:
            factors.append(1.0)  # 아직 금리 없음 → 현금(보수적)
            continue
        price = _par_bond_price(y0, y1, maturity_years)
        factors.append(price + y0 / MONTHS_PER_YEAR)
    return factors


# ──────────────────────────── 일반 추세 신호(레벨) ────────────────────────────


def sma_in_market(levels: list[float], window: int) -> list[bool]:
    """레벨 시계열 `levels`(길이 M)에 대해 각 수익 기간(k-1→k)에서 투자할지(길이 M-1).

    in_market_k = levels[k-1] > SMA(levels[k-window .. k-1]). SMA 가 아직 없으면(k<window)
    투자(True). 스펙 042 `trend_in_market` 와 동일 규칙을 임의 레벨 시계열로 일반화한 것
    (채권 총수익 지수에 같은 잣대의 추세 타이밍을 적용하기 위함). 미래 누출 없음.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    out: list[bool] = []
    for k in range(1, len(levels)):
        if k < window:
            out.append(True)
            continue
        sma = sum(levels[k - window:k]) / window
        out.append(levels[k - 1] > sma)
    return out


def sleeve_factors(
    asset: list[float], cash: list[float], in_market: list[bool]
) -> list[float]:
    """한 자산 슬리브의 월간 팩터: 추세 위면 자산, 아래면 현금."""
    if not (len(asset) == len(cash) == len(in_market)):
        raise ValueError("length mismatch")
    return [a if inm else c for a, c, inm in zip(asset, cash, in_market, strict=True)]


def blend(weights_and_factors: list[tuple[float, list[float]]]) -> list[float]:
    """여러 슬리브를 *매월 목표 비중으로 재조정*한 혼합 팩터(가중 평균).

    portfolio_factor_t = Σ_i w_i * factor_i_t. 가중치는 매월 목표로 되돌린다는 가정(월간
    재조정). 가중치 합이 1이 아니어도 그대로 쓴다(현금 비중을 남기는 설계 가능).
    """
    if not weights_and_factors:
        raise ValueError("empty blend")
    n = len(weights_and_factors[0][1])
    for _, f in weights_and_factors:
        if len(f) != n:
            raise ValueError("length mismatch")
    out: list[float] = []
    for t in range(n):
        out.append(sum(w * f[t] for w, f in weights_and_factors))
    return out


# ─────────────────────────── 멀티에셋 분산 비교 ───────────────────────────


@dataclass(frozen=True)
class MultiAssetComparison:
    """단일 주식 추세 vs 멀티에셋 분산 추세 — 분산이 위험조정 가치를 더하는가."""

    window: int
    equity_weight: float
    bond_weight: float
    # 비교 다리들
    bh_equity: LegStats  # 단순 보유 주식(베이스라인)
    bh_6040: LegStats  # 60/40 주식·채권 단순 보유(고전 분산 베이스라인)
    trend_equity: LegStats  # 주식 추세만(스펙 042 결과)
    trend_bond: LegStats  # 채권 추세만(참고)
    diversified_trend: LegStats  # 주식추세 + 채권추세 분산(세계 최고 수준 후보)
    verdict: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "window": self.window,
            "equity_weight": self.equity_weight,
            "bond_weight": self.bond_weight,
            "verdict": self.verdict,
            "reason": self.reason,
            "bh_equity": self.bh_equity.as_dict(),
            "bh_6040": self.bh_6040.as_dict(),
            "trend_equity": self.trend_equity.as_dict(),
            "trend_bond": self.trend_bond.as_dict(),
            "diversified_trend": self.diversified_trend.as_dict(),
        }


def _classify_diversification(
    trend_equity: LegStats, diversified: LegStats, bh_6040: LegStats
) -> tuple[str, str]:
    """분산 추세가 *위험조정으로* 가치를 더하는가(사전 등록 기준).

    멀티에셋 분산 추세가 단일 주식 추세보다 ① 샤프를 올리고, ② 칼마를 올리고, ③ 최대낙폭을
    악화시키지 않으면 DIVERSIFICATION_EDGE. 비상관 자산을 합쳐 *위험 단위당 수익*을 올리는
    것이 분산의 본질이라 (raw CAGR 이 아니라) 샤프·칼마·낙폭으로 판정한다. 추가로 고전
    60/40 단순 보유보다 샤프가 나은지도 reason 에 함께 보고(분산 추세가 정적 분산도 이기는가).
    """
    if trend_equity.calmar is None or diversified.calmar is None:
        return "INSUFFICIENT", "칼마 정의 불가(낙폭 0 또는 데이터 부족)"
    sharpe_up = diversified.sharpe > trend_equity.sharpe
    calmar_up = diversified.calmar > trend_equity.calmar
    dd_ok = diversified.max_dd_pct <= trend_equity.max_dd_pct * 1.001  # 동률 허용
    beats_6040 = (
        bh_6040.calmar is not None and diversified.sharpe > bh_6040.sharpe
    )
    tail = (
        f"60/40 단순보유 샤프 {bh_6040.sharpe:.2f} {'<' if beats_6040 else '≥'} "
        f"분산추세 {diversified.sharpe:.2f}"
    )
    if sharpe_up and calmar_up and dd_ok:
        return (
            "DIVERSIFICATION_EDGE",
            f"샤프 {trend_equity.sharpe:.2f}→{diversified.sharpe:.2f}, "
            f"칼마 {trend_equity.calmar:.2f}→{diversified.calmar:.2f}, "
            f"낙폭 {trend_equity.max_dd_pct:.0f}%→{diversified.max_dd_pct:.0f}%; {tail}",
        )
    fails = []
    if not sharpe_up:
        fails.append("샤프 개선 없음")
    if not calmar_up:
        fails.append("칼마 개선 없음")
    if not dd_ok:
        fails.append("낙폭 악화")
    return "NO_DIVERSIFICATION_BENEFIT", "; ".join(fails) + f"; {tail}"


def compare_diversified_trend(
    rows: list[MonthlyRow],
    *,
    window: int = 10,
    equity_weight: float = 0.5,
    bond_weight: float = 0.5,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
) -> MultiAssetComparison:
    """단일 주식 추세 vs 주식추세+채권추세 분산을 같은 기간에서 비교(슬라이스 1의 핵심).

    각 다리는 월간 팩터로 환산해 summarize(샤프·칼마·낙폭). 분산 추세는 두 슬리브(주식
    추세 게이트 / 채권 추세 게이트)를 매월 목표 비중으로 재조정해 합친다.
    """
    eq_market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    bond = bond_total_return_factors(rows, maturity_years=bond_maturity_years)

    # 채권 총수익 지수(레벨)로 채권 추세 신호를 만든다(주식과 같은 SMA 잣대).
    bond_index = equity_curve(bond)  # 길이 N, rows 와 정렬
    eq_in = trend_in_market(rows, window)  # 길이 N-1
    bond_in = sma_in_market(bond_index, window)  # 길이 N-1

    eq_sleeve = sleeve_factors(eq_market, cash, eq_in)
    bond_sleeve = sleeve_factors(bond, cash, bond_in)

    diversified = blend([(equity_weight, eq_sleeve), (bond_weight, bond_sleeve)])
    bh_6040 = blend([(0.6, eq_market), (0.4, bond)])

    leg_bh_equity = summarize(eq_market, in_market=None)
    leg_bh_6040 = summarize(bh_6040, in_market=None)
    leg_trend_equity = summarize(eq_sleeve, in_market=eq_in)
    leg_trend_bond = summarize(bond_sleeve, in_market=bond_in)
    leg_diversified = summarize(diversified, in_market=None)

    verdict, reason = _classify_diversification(
        leg_trend_equity, leg_diversified, leg_bh_6040
    )
    return MultiAssetComparison(
        window=window,
        equity_weight=equity_weight,
        bond_weight=bond_weight,
        bh_equity=leg_bh_equity,
        bh_6040=leg_bh_6040,
        trend_equity=leg_trend_equity,
        trend_bond=leg_trend_bond,
        diversified_trend=leg_diversified,
        verdict=verdict,
        reason=reason,
    )


def diversified_trend_factors(
    rows: list[MonthlyRow],
    *,
    window: int = 10,
    equity_weight: float = 0.5,
    bond_weight: float = 0.5,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
) -> list[float]:
    """분산 추세(주식추세+채권추세) 월간 그로스 팩터 스트림(길이 N-1).

    `compare_diversified_trend` 와 같은 계산이지만 LegStats 요약이 아니라 *원시 팩터 스트림*을
    돌려준다 — 스펙 044 성장 최적 레버리지가 이 스트림에 레버리지를 얹어 복리 성장률을 잰다.
    """
    eq_market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    bond = bond_total_return_factors(rows, maturity_years=bond_maturity_years)
    bond_index = equity_curve(bond)
    eq_in = trend_in_market(rows, window)
    bond_in = sma_in_market(bond_index, window)
    eq_sleeve = sleeve_factors(eq_market, cash, eq_in)
    bond_sleeve = sleeve_factors(bond, cash, bond_in)
    return blend([(equity_weight, eq_sleeve), (bond_weight, bond_sleeve)])


def equity_trend_factors(rows: list[MonthlyRow], *, window: int = 10) -> list[float]:
    """단일 주식 추세(스펙 042) 월간 그로스 팩터 스트림(길이 N-1) — 레버리지 비교용."""
    eq_market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    eq_in = trend_in_market(rows, window)
    return sleeve_factors(eq_market, cash, eq_in)


def correlation(a: list[float], b: list[float]) -> float | None:
    """두 팩터(또는 수익) 시계열의 피어슨 상관 — 분산 효과의 근거를 정직히 드러낸다.

    1+r 팩터를 받아 내부에서 수익(r)으로 환산해 계산한다. 표본<2 또는 분산 0이면 None.
    """
    if len(a) != len(b) or len(a) < 2:
        return None
    ra = [x - 1.0 for x in a]
    rb = [x - 1.0 for x in b]
    n = len(ra)
    ma = sum(ra) / n
    mb = sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va <= 0 or vb <= 0:
        return None
    return cov / (va ** 0.5 * vb ** 0.5)


__all__ = [
    "DEFAULT_BOND_MATURITY_YEARS",
    "MultiAssetComparison",
    "blend",
    "bond_total_return_factors",
    "carry_forward_rates",
    "compare_diversified_trend",
    "correlation",
    "diversified_trend_factors",
    "equity_trend_factors",
    "sleeve_factors",
    "sma_in_market",
]
