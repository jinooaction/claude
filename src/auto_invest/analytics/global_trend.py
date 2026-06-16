"""스펙 047 — 글로벌 분산 추세추종: 검증된 2자산(주식+채권)을 *3자산(+금)* 진짜 GTAA 로 확장.

배경(정직한 우선순위 판단):
  - 종목 선택 알파는 측정상 0(스펙 041). 유일하게 끈질긴 엣지 = 추세추종의 자본 방어(042).
  - 스펙 043 이 그 엣지를 *두 비상관 자산*(주식 베타 + 채권 듀레이션)으로 분산해 샤프를
    1.18~1.43 → 1.58~1.81 로 올렸다(낙폭 절반). 분산은 금융 최대의 "공짜 점심"이다.
  - 그러나 스펙 045 / 일일 모니터(046)가 지금 경고하는 위험: **주식·채권 상관이 양수로
    전환**(2022 인플레 regime)하면 채권이 더는 분산해 주지 못한다(DIVERSIFICATION_WEAKENED).
    두 다리만으로는 바로 그 regime 에 취약하다.

세계 최고 수준과의 진짜 격차 = **세 번째 비상관 자산(금)**. 금은 역사적으로 주식·채권 *둘
다와* 비상관이고, 특히 인플레이션·실질금리 하락 regime(주식·채권이 동반 하락하는 바로 그
구간)에서 방어한다. 즉 금 추가는 단순한 "자산 하나 더"가 아니라 *지금 경고된 약점(채권 분산
약화)의 구조적 정답*이다. 세계 최고 수준 managed futures(AQR, Man-AHL, Winton)가 실제로
하는 진짜 GTAA(주식·채권·원자재·통화의 비상관 추세 다발) 방향이다.

데이터: 스펙 042/043 가 쓰는 그 GitHub Shiller CSV(주식·채권)에 더해, GitHub `datasets/
gold-prices`(런던 금 월간, 1833~현재 — 이 컨테이너에서 닿는다)로 *추가 데이터 0의 외부 의존
없이* 금 다리를 검증한다. Shiller 와 같은 월간 cadence 라 YYYY-MM 으로 정렬된다.

정직한 한계(반드시 명시):
  - **금은 1971 년 브레튼우즈 붕괴 전까지 사실상 고정환**($18.93→$20.67→1934 $35). 페그
    구간엔 추세가 없다 → 금이 *자유변동 추세 자산*인 건 1971 년 이후다. 그래서 전체(1871~)·
    현대(1950~) 결과엔 페그 잡음이 섞이고, **자유변동(1971~)·최근(1990~) 구간이 정직한 답**
    이다. probe 가 구간별로 분리 보고한다.
  - 금은 쿠폰·배당이 없다 → 총수익 = 순수 가격수익(factor_t = P_t / P_{t-1}). 보관비용은 ETF
    경비(GLD ~0.40%/년)로 근사 가능하나 장기 *상대* 비교엔 무시할 수준(명시).
  - "현금"(추세 아래)·채권 프록시 한계는 스펙 042/043 과 동일(세 다리 동일 적용이라 상대
    비교는 공정).

이 모듈은 순수(부수효과 0)·결정론이며 비커널이다. 주문 0건, 돈 0 이동(연구/측정 전용).
미래 누출 없음: period t 의 매수/현금·재평가 결정은 t-1 말까지의 정보만 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.analytics.multi_asset_trend import (
    DEFAULT_BOND_MATURITY_YEARS,
    blend,
    bond_total_return_factors,
    correlation,
    sma_in_market,
)
from auto_invest.analytics.risk_managed_beta import (
    CostModel,
    LegStats,
    MonthlyRow,
    apply_cost_model,
    cash_factors,
    market_total_return_factors,
    summarize,
    trend_in_market,
)

# 브레튼우즈 붕괴 — 금이 자유변동 추세 자산이 된 해. 이 이전은 페그(추세 없음).
GOLD_FLOAT_YEAR = 1971


# ─────────────────────────────── 금 데이터 ───────────────────────────────


def parse_gold(csv_text: str) -> dict[str, float]:
    """`datasets/gold-prices` 월간 CSV → {YYYY-MM: price} 매핑.

    헤더: Date,Price. Date 는 `YYYY-MM`. 가격<=0/불량 행은 건너뛴다.
    """
    out: dict[str, float] = {}
    for line in csv_text.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        ym = parts[0].strip()
        if len(ym) < 7:  # 최소 YYYY-MM
            continue
        try:
            price = float(parts[1])
        except ValueError:
            continue
        if price > 0:
            out[ym[:7]] = price
    return out


def align_gold_levels(
    rows: list[MonthlyRow], gold_by_month: dict[str, float]
) -> list[float]:
    """Shiller `rows`(YYYY-MM-DD) 각 행에 금 가격을 YYYY-MM 으로 정렬한 레벨 시계열(길이 N).

    한 달이 금 데이터에 비면 직전 유효 금가를 캐리(금은 월 단위로 천천히 움직임). 첫 행의
    달조차 금 데이터(또는 그 이전)가 없으면 ValueError — 호출부가 겹치는 구간만 넘기도록.
    미래 누출 없음: 각 레벨은 같은 달 관측치(또는 직전 캐리)만 쓴다.
    """
    out: list[float] = []
    last: float | None = None
    for r in rows:
        ym = r.date[:7]
        if ym in gold_by_month:
            last = gold_by_month[ym]
        if last is None:
            raise ValueError(f"no gold price at or before {ym}")
        out.append(last)
    return out


def gold_total_return_factors(gold_levels: list[float]) -> list[float]:
    """금 월간 총수익 그로스 팩터(1+r), 길이 N-1. 금은 쿠폰/배당 0 → 순수 가격수익.

    factor_t = gold_levels[t] / gold_levels[t-1]. 미래 누출 없음.
    """
    return [
        gold_levels[t] / gold_levels[t - 1] for t in range(1, len(gold_levels))
    ]


# ─────────────────────────── 글로벌 3자산 비교 ───────────────────────────


@dataclass(frozen=True)
class GlobalTrendComparison:
    """2자산(주식+채권) 분산 추세 vs 3자산(+금) 분산 추세 — 금이 가치를 더하는가."""

    window: int
    equity_weight: float
    bond_weight: float
    gold_weight: float
    trend_equity: LegStats  # 단일 주식 추세(스펙 042)
    trend_bond: LegStats  # 채권 추세만(참고)
    trend_gold: LegStats  # 금 추세만(참고)
    diversified_2asset: LegStats  # 주식추세 + 채권추세(스펙 043, 50/50)
    diversified_3asset: LegStats  # 주식추세 + 채권추세 + 금추세(고정 가중, 스펙 047 후보)
    risk_parity_3asset: LegStats  # 주+채+금 역변동성 가중(원칙적 사이징)
    gold_corr_equity: float | None  # 금↔주식 월수익 상관
    gold_corr_bond: float | None  # 금↔채권 월수익 상관
    verdict: str  # 고정 가중 3자산이 2자산 대비 엣지인가
    reason: str
    verdict_rp: str  # 역변동성 3자산이 2자산 대비 엣지인가
    reason_rp: str

    def as_dict(self) -> dict:
        return {
            "window": self.window,
            "equity_weight": self.equity_weight,
            "bond_weight": self.bond_weight,
            "gold_weight": self.gold_weight,
            "verdict": self.verdict,
            "reason": self.reason,
            "gold_corr_equity": (
                round(self.gold_corr_equity, 3)
                if self.gold_corr_equity is not None
                else None
            ),
            "gold_corr_bond": (
                round(self.gold_corr_bond, 3)
                if self.gold_corr_bond is not None
                else None
            ),
            "verdict_rp": self.verdict_rp,
            "reason_rp": self.reason_rp,
            "trend_equity": self.trend_equity.as_dict(),
            "trend_bond": self.trend_bond.as_dict(),
            "trend_gold": self.trend_gold.as_dict(),
            "diversified_2asset": self.diversified_2asset.as_dict(),
            "diversified_3asset": self.diversified_3asset.as_dict(),
            "risk_parity_3asset": self.risk_parity_3asset.as_dict(),
        }


def _classify_gold(
    two_asset: LegStats, three_asset: LegStats
) -> tuple[str, str]:
    """3자산(+금) 분산이 2자산 대비 *위험조정으로* 가치를 더하는가(사전 등록 기준).

    금을 더해 ① 샤프를 올리고 ② 칼마를 올리고 ③ 최대낙폭을 악화시키지 않으면
    GOLD_DIVERSIFICATION_EDGE. 분산의 본질은 *위험 단위당 수익*을 올리는 것이라 raw CAGR 이
    아니라 샤프·칼마·낙폭으로 판정한다(스펙 043 과 같은 잣대).
    """
    if two_asset.calmar is None or three_asset.calmar is None:
        return "INSUFFICIENT", "칼마 정의 불가(낙폭 0 또는 데이터 부족)"
    sharpe_up = three_asset.sharpe > two_asset.sharpe
    calmar_up = three_asset.calmar > two_asset.calmar
    dd_ok = three_asset.max_dd_pct <= two_asset.max_dd_pct * 1.001  # 동률 허용
    detail = (
        f"샤프 {two_asset.sharpe:.2f}→{three_asset.sharpe:.2f}, "
        f"칼마 {two_asset.calmar:.2f}→{three_asset.calmar:.2f}, "
        f"낙폭 {two_asset.max_dd_pct:.0f}%→{three_asset.max_dd_pct:.0f}%"
    )
    if sharpe_up and calmar_up and dd_ok:
        return "GOLD_DIVERSIFICATION_EDGE", detail
    fails = []
    if not sharpe_up:
        fails.append("샤프 개선 없음")
    if not calmar_up:
        fails.append("칼마 개선 없음")
    if not dd_ok:
        fails.append("낙폭 악화")
    return "NO_GOLD_BENEFIT", "; ".join(fails) + f"; {detail}"


def _normalized_weights(
    equity_weight: float, bond_weight: float, gold_weight: float
) -> tuple[float, float, float]:
    total = equity_weight + bond_weight + gold_weight
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return equity_weight / total, bond_weight / total, gold_weight / total


def compare_global_trend(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    window: int = 10,
    equity_weight: float = 1.0,
    bond_weight: float = 1.0,
    gold_weight: float = 1.0,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
) -> GlobalTrendComparison:
    """2자산(주식+채권 50/50) vs 3자산(주식+채권+금 정규화 가중) 분산 추세를 같은 기간 비교.

    `gold_levels` 는 `align_gold_levels(rows, ...)` 로 rows 와 정렬된 길이 N 금 가격 시계열.
    각 다리는 월간 팩터로 환산해 summarize(샤프·칼마·낙폭). 가중치는 합으로 정규화한다(3자산은
    기본 1:1:1 = 1/3 씩). 2자산 베이스라인은 스펙 043 과 동일한 고정 50/50.
    """
    if len(gold_levels) != len(rows):
        raise ValueError("gold_levels must align 1:1 with rows")
    ew, bw, gw = _normalized_weights(equity_weight, bond_weight, gold_weight)

    eq_market = market_total_return_factors(rows)
    bond = bond_total_return_factors(rows, maturity_years=bond_maturity_years)
    gold = gold_total_return_factors(gold_levels)

    eq_sleeve, bond_sleeve, gold_sleeve = _build_sleeves(
        rows, gold_levels, window, bond_maturity_years
    )
    eq_in = trend_in_market(rows, window)
    bond_in = sma_in_market(_cum_levels(bond), window)
    gold_in = sma_in_market(gold_levels, window)

    # 2자산 분산(스펙 043, 고정 50/50), 3자산 고정 가중, 3자산 역변동성(리스크 패리티).
    div2 = blend([(0.5, eq_sleeve), (0.5, bond_sleeve)])
    div3 = blend([(ew, eq_sleeve), (bw, bond_sleeve), (gw, gold_sleeve)])
    rp3 = risk_parity_global_factors(
        rows, gold_levels, window=window, bond_maturity_years=bond_maturity_years
    )

    leg_trend_equity = summarize(eq_sleeve, in_market=eq_in)
    leg_trend_bond = summarize(bond_sleeve, in_market=bond_in)
    leg_trend_gold = summarize(gold_sleeve, in_market=gold_in)
    leg_div2 = summarize(div2, in_market=None)
    leg_div3 = summarize(div3, in_market=None)
    leg_rp3 = summarize(rp3, in_market=None)

    verdict, reason = _classify_gold(leg_div2, leg_div3)
    verdict_rp, reason_rp = _classify_gold(leg_div2, leg_rp3)
    return GlobalTrendComparison(
        window=window,
        equity_weight=ew,
        bond_weight=bw,
        gold_weight=gw,
        trend_equity=leg_trend_equity,
        trend_bond=leg_trend_bond,
        trend_gold=leg_trend_gold,
        diversified_2asset=leg_div2,
        diversified_3asset=leg_div3,
        risk_parity_3asset=leg_rp3,
        gold_corr_equity=correlation(gold, eq_market),
        gold_corr_bond=correlation(gold, bond),
        verdict=verdict,
        reason=reason,
        verdict_rp=verdict_rp,
        reason_rp=reason_rp,
    )


def _cum_levels(factors: list[float], start: float = 1.0) -> list[float]:
    """그로스 팩터 → 누적 레벨(길이 N). multi_asset_trend.equity_curve 와 동일 규칙."""
    out = [start]
    for f in factors:
        out.append(out[-1] * f)
    return out


def _trailing_vol(returns: list[float], end_idx: int, window: int) -> float | None:
    """returns[:end_idx] 의 마지막 window 개 표준편차(미래 누출 0). 표본<2면 None."""
    seg = returns[max(0, end_idx - window):end_idx]
    if len(seg) < 2:
        return None
    m = sum(seg) / len(seg)
    var = sum((x - m) ** 2 for x in seg) / (len(seg) - 1)
    return var ** 0.5


def _build_sleeves(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    window: int,
    bond_maturity_years: int,
    cost_bps: float = 0.0,
) -> tuple[list[float], list[float], list[float]]:
    """주식·채권·금 추세 슬리브 팩터(각 길이 N-1)를 만든다(내부 공용).

    `cost_bps`>0 이면 각 슬리브 전환마다 일방 거래비용 반영. cost_bps=0 에서 `apply_cost_model`
    은 `sleeve_factors` 와 수학적으로 동일(비용계수 1.0) → 기본값은 기존 동작과 완전히 같다.
    """
    eq_market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    bond = bond_total_return_factors(rows, maturity_years=bond_maturity_years)
    gold = gold_total_return_factors(gold_levels)
    eq_in = trend_in_market(rows, window)
    bond_in = sma_in_market(_cum_levels(bond), window)
    gold_in = sma_in_market(gold_levels, window)
    model = CostModel(cost_bps=cost_bps)
    return (
        apply_cost_model(eq_market, cash, eq_in, model),
        apply_cost_model(bond, cash, bond_in, model),
        apply_cost_model(gold, cash, gold_in, model),
    )


def risk_parity_global_factors(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    window: int = 10,
    vol_window: int = 12,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
    cost_bps: float = 0.0,
) -> list[float]:
    """역변동성(리스크 패리티) 가중 글로벌 3자산 추세 월간 팩터 스트림(길이 N-1).

    고정 가중 대신 *각 슬리브가 위험에 동등 기여*하도록 매월 트레일링 역변동성으로 가중한다.
    금처럼 변동성 큰 자산은 자동으로 작은 비중을 받아(위험 과배분 방지), "마법의 상수" 없이
    원칙적으로 사이징된다(세계 최고 수준 managed futures 의 표준). 미래 누출 0: period t
    가중치는 t 이전(<=t-1) 수익의 트레일링 변동성만 쓴다. 이력 부족이면 1/3 균등(중립).
    `cost_bps`>0 이면 슬리브 추세 전환 거래비용 반영(기본 0 = 역호환). 단 역변동성의 매월
    가중 재조정 회전율(슬리브 비중 변화)은 여기 반영 안 됨 → 이 비용은 *보수적*(역변동성에
    유리, 실제 비용 과소평가).
    """
    if len(gold_levels) != len(rows):
        raise ValueError("gold_levels must align 1:1 with rows")
    eq_s, bond_s, gold_s = _build_sleeves(
        rows, gold_levels, window, bond_maturity_years, cost_bps
    )
    rets = [[f - 1.0 for f in s] for s in (eq_s, bond_s, gold_s)]
    out: list[float] = []
    for t in range(len(eq_s)):
        vols = [_trailing_vol(r, t, vol_window) for r in rets]
        if any(v is None or v <= 0 for v in vols):
            w = [1 / 3, 1 / 3, 1 / 3]
        else:
            inv = [1.0 / v for v in vols]  # type: ignore[arg-type]
            s = sum(inv)
            w = [i / s for i in inv]
        out.append(
            w[0] * eq_s[t] + w[1] * bond_s[t] + w[2] * gold_s[t]
        )
    return out


def global_trend_factors(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    window: int = 10,
    equity_weight: float = 1.0,
    bond_weight: float = 1.0,
    gold_weight: float = 1.0,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
    cost_bps: float = 0.0,
) -> list[float]:
    """글로벌 3자산(주식추세+채권추세+금추세) 월간 그로스 팩터 스트림(길이 N-1).

    `compare_global_trend` 와 같은 계산이지만 LegStats 요약이 아니라 *원시 팩터 스트림*을
    돌려준다 — 스펙 044 성장 최적 레버리지가 이 스트림에 레버리지를 얹어 복리 성장을 잰다.
    고정 가중이라 회전율은 슬리브 추세 전환뿐 → `cost_bps` 비용이 회전율을 온전히 반영한다
    (역변동성과 달리 매월 비중 재조정 추가 회전 없음, 기본 0 = 역호환).
    """
    if len(gold_levels) != len(rows):
        raise ValueError("gold_levels must align 1:1 with rows")
    ew, bw, gw = _normalized_weights(equity_weight, bond_weight, gold_weight)
    eq_sleeve, bond_sleeve, gold_sleeve = _build_sleeves(
        rows, gold_levels, window, bond_maturity_years, cost_bps
    )
    return blend([(ew, eq_sleeve), (bw, bond_sleeve), (gw, gold_sleeve)])


__all__ = [
    "GOLD_FLOAT_YEAR",
    "GlobalTrendComparison",
    "align_gold_levels",
    "compare_global_trend",
    "global_trend_factors",
    "gold_total_return_factors",
    "parse_gold",
    "risk_parity_global_factors",
]
