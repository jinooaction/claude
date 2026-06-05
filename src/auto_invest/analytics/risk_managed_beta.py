"""스펙 042 — 위험관리된 베타: 추세 타이밍 오버레이가 단순 보유 대비 위험조정 수익을
올리는가(자본 방어)를 정직하게 측정. 비커널 진단(주문 0건, 돈 0 이동).

운영자 결정(2026-06-05): 가격 종목선택 알파는 측정상 없음이 확정됐고(스펙 041), 다른 알파를
만들 데이터(펀더멘털·매크로)는 이 환경에서 차단됐다. 그래서 "세계 최고 수준 + 실제 수익"의
정직한 의미를 **위험관리된 베타**로 재정의한다 — 시장 수익(베타)을 잡되, 추세/변동성 방어로
폭락에서 자본을 지켜 위험조정 수익(샤프·칼마)을 올리는 것.

추세추종의 드로다운 방어는 금융에서 몇 안 되는 끈질긴 효과다(Faber, "A Quantitative Approach
to Tactical Asset Allocation"). 그 효과를 *우리 데이터로 정직하게* 잰다: Shiller 월간 S&P 500
(1871~현재, GitHub 호스팅 — 이 컨테이너에서 닿는 유일한 장기 데이터)으로 단순 보유 총수익 vs
10개월 이동평균 추세 타이밍을 비교한다. 이 데이터는 1929·1973·2000·2008 등 *실제 대공황*을
포함하므로, 폭락이 없는 2013-2018 데이터로는 불가능한 자본 방어 검증이 가능하다.

미래 누출 없음: 매월 t의 매수/현금 결정은 t-1 말까지의 정보(P[t-1] vs SMA(P[t-window..t-1]))만
쓴다. 결정론(부동소수 결정적).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from auto_invest.backtest.metrics import max_drawdown_pct
from auto_invest.backtest.significance import probabilistic_sharpe_ratio
from auto_invest.portfolio.edge_verdict import calmar_ratio
from auto_invest.strategy.sizing import realized_volatility, volatility_scale
from auto_invest.strategy.trend import METHOD_SMA, TrendSpec, above_trend

MONTHS_PER_YEAR = 12


@dataclass(frozen=True)
class MonthlyRow:
    """Shiller 월간 한 행 — 우리가 쓰는 필드만."""

    date: str  # YYYY-MM-DD
    price: float
    dividend: float  # 연환산 $/주 (없으면 0)
    long_rate: float  # 연 % (없으면 0)


def parse_shiller(csv_text: str) -> list[MonthlyRow]:
    """Shiller datahub CSV → MonthlyRow 오름차순.

    헤더: Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate,...
    가격<=0 행은 제외(데이터 불량). 최근 달은 Dividend/Long Interest Rate 가 0(미기재)일 수
    있고 그건 호출부에서 '없음'으로 안전 처리한다(배당 0 기여, 현금 수익 0).
    """
    rows: list[MonthlyRow] = []
    lines = csv_text.splitlines()
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            price = float(parts[1])
            dividend = float(parts[2]) if parts[2] else 0.0
            long_rate = float(parts[5]) if parts[5] else 0.0
        except ValueError:
            continue
        if price <= 0:
            continue
        rows.append(MonthlyRow(parts[0], price, max(dividend, 0.0), max(long_rate, 0.0)))
    return rows


def market_total_return_factors(rows: list[MonthlyRow]) -> list[float]:
    """단순 보유(항상 투자) 월간 총수익 그로스 팩터(1+r), 길이 N-1.

    factor_t = (P_t + Dividend_t/12) / P_{t-1}. 배당은 Shiller 의 연환산 배당이라 월 기여는
    /12. 최근 달 배당 0 이면 가격수익만(과소평가지만 장기 판정엔 무시할 수준).
    """
    factors: list[float] = []
    for t in range(1, len(rows)):
        prev = rows[t - 1].price
        monthly_div = rows[t].dividend / MONTHS_PER_YEAR
        factors.append((rows[t].price + monthly_div) / prev)
    return factors


def cash_factors(rows: list[MonthlyRow]) -> list[float]:
    """현금(추세 아래일 때) 월간 그로스 팩터, 길이 N-1.

    factor_t = 1 + rate_{t-1}/100/12 (월초에 아는 직전 금리). 금리 0/미기재면 1.0(현금 0%
    수익 — 보수적). Shiller 장기금리(10년)는 단기 T-bill 보다 약간 후하다는 한계는 정직히 명시.
    """
    factors: list[float] = []
    for t in range(1, len(rows)):
        rate = rows[t - 1].long_rate
        factors.append(1.0 + (rate / 100.0 / MONTHS_PER_YEAR if rate > 0 else 0.0))
    return factors


def trend_in_market(rows: list[MonthlyRow], window: int) -> list[bool]:
    """추세 신호 — period t(=월 t)에 투자할지. 길이 N-1, 미래 누출 없음.

    in_market_t = P[t-1] > SMA(P[t-window .. t-1]). SMA 가 아직 없으면(t<window) 투자(True)
    로 둔다(아직 타이밍 불가, 단순 보유와 동일 — 첫 ~window 달뿐). 월말 종가로만 판단.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    prices = [r.price for r in rows]
    out: list[bool] = []
    for t in range(1, len(rows)):
        end = t  # 직전 월 인덱스(t-1) 포함까지 = prices[:t]
        if end < window:
            out.append(True)
            continue
        sma = sum(prices[end - window:end]) / window
        out.append(prices[end - 1] > sma)
    return out


def overlay_factors(
    market: list[float], cash: list[float], in_market: list[bool]
) -> list[float]:
    """추세 타이밍 전략 월간 팩터: 투자면 시장, 아니면 현금."""
    if not (len(market) == len(cash) == len(in_market)):
        raise ValueError("length mismatch")
    return [m if inm else c for m, c, inm in zip(market, cash, in_market, strict=True)]


def production_in_market(rows: list[MonthlyRow], *, lookback: int = 10) -> list[bool]:
    """**운영 코드** `strategy.trend.above_trend`(SMA, lookback)로 in_market 신호를 만든다.

    슬라이스 3 브리지 — 슬라이스 1·2의 결론(독립 연구 모듈 `trend_in_market`)이 *실제 라이브
    재조정에서 도는 바로 그 함수*(`above_trend`, `apply_trend_filter` 가 호출)에서도 똑같이
    나오는지 검증하기 위함이다. period t(=월 t) 결정은 `prices[0..t-1]` 만 본다(미래 누출 0).
    above_trend 가 부족(None)이면 연구 모듈과 동일하게 투자(True)로 둔다. 두 신호가 같으면
    "검증된 엣지가 라이브 코드 경로에 그대로 실린다"는 뜻이다(테스트로 보증).
    """
    spec = TrendSpec(method=METHOD_SMA, lookback=lookback)
    prices = [Decimal(str(r.price)) for r in rows]
    out: list[bool] = []
    for t in range(1, len(rows)):
        verdict = above_trend(prices[:t], spec)
        out.append(True if verdict is None else bool(verdict))
    return out


@dataclass(frozen=True)
class CostModel:
    """거래비용·세금 가정 — 엣지가 *비용을 견디는지* 정직히 재기 위한 모델.

    - cost_bps: 전환(매수/매도) 1회당 *일방* 거래비용(거래 명목의 bp). SPY 같은 초유동
      ETF는 현실적으로 1~5bp이나 보수적으로 10bp 기본(비용을 과대평가해 정직히).
    - tax_rate: 현금으로 빠질 때(매도) 실현이익에 매기는 자본이득세율(0..1). **0 = 세금
      이연 계좌**(자동매매·IRA류 — 우리 시스템의 기본 가정). 과세 계좌를 보려면 >0.
      단순화: 매도 시점 이익에만 과세(장·단기 구분·손실이월·워시세일 무시 — 보수적 근사).
    """

    cost_bps: float = 10.0
    tax_rate: float = 0.0


def count_switches(in_market: list[bool]) -> int:
    """포지션 상태가 바뀌는 횟수(거래 횟수). 시작이 투자면 최초 매수도 1회로 센다."""
    if not in_market:
        return 0
    switches = 1 if in_market[0] else 0  # 현금에서 시작 → 첫 진입이 매수
    for a, b in zip(in_market[:-1], in_market[1:], strict=True):
        if a != b:
            switches += 1
    return switches


def apply_cost_model(
    market: list[float],
    cash: list[float],
    in_market: list[bool],
    model: CostModel,
) -> list[float]:
    """전환마다 일방 거래비용 + (과세 계좌면) 매도 시 실현이익 세금을 반영한 *순* 팩터.

    경로 의존(세금은 직전 진입가 대비 이익에 매김)이라 자산을 따라가며 계산한다. 단순
    보유(in_market 전부 True)면 최초 매수 비용 1회만 — 이연 이점은 그대로(말기 미실현
    이익엔 과세 안 함, 그게 단순 보유의 진짜 세금 이점이자 타이밍의 세금 불리다).
    """
    if not (len(market) == len(cash) == len(in_market)):
        raise ValueError("length mismatch")
    cost_mult = 1.0 - model.cost_bps / 10_000.0
    net: list[float] = []
    equity = 1.0
    entry_value: float | None = None  # 마지막 진입 시 자산(세금 기준가)
    prev_in = False  # 첫 기간 전엔 현금이라고 본다
    for t, inm in enumerate(in_market):
        f = market[t] if inm else cash[t]
        if inm != prev_in:  # 전환(매수 또는 매도) 발생
            f *= cost_mult
            selling = prev_in and not inm  # 매도(현금으로) → 실현이익 과세
            if (
                selling
                and model.tax_rate > 0
                and entry_value is not None
                and equity > entry_value
            ):
                tax = model.tax_rate * (equity - entry_value)
                f *= 1.0 - tax / equity
            if not prev_in and inm:  # 매수(진입) → 기준가 갱신
                entry_value = equity
        net.append(f)
        equity *= f
        prev_in = inm
    return net



def equity_curve(factors: list[float], start: float = 1.0) -> list[float]:
    """그로스 팩터 누적 자산곡선(시작값 포함, 길이 N)."""
    curve = [start]
    for f in factors:
        curve.append(curve[-1] * f)
    return curve


@dataclass(frozen=True)
class LegStats:
    """한 다리(단순 보유 또는 추세)의 위험조정 요약."""

    cagr_pct: float
    vol_pct: float  # 연율 변동성
    sharpe: float  # 연율(√12), RFR=0
    max_dd_pct: float  # 양수
    calmar: float | None
    psr_gt0: float | None  # 참 샤프 > 0 확률
    pct_in_market: float  # 투자 비중(단순 보유=1.0)
    n_months: int

    def as_dict(self) -> dict:
        return {
            "cagr_pct": round(self.cagr_pct, 2),
            "vol_pct": round(self.vol_pct, 2),
            "sharpe": round(self.sharpe, 3),
            "max_dd_pct": round(self.max_dd_pct, 2),
            "calmar": round(self.calmar, 3) if self.calmar is not None else None,
            "psr_gt0": round(self.psr_gt0, 3) if self.psr_gt0 is not None else None,
            "pct_in_market": round(self.pct_in_market, 3),
            "n_months": self.n_months,
        }


def summarize(factors: list[float], in_market: list[bool] | None = None) -> LegStats:
    """월간 팩터 → CAGR·변동성·샤프(√12)·최대낙폭·칼마·PSR(>0)·투자비중."""
    n = len(factors)
    if n < 2:
        return LegStats(0.0, 0.0, 0.0, 0.0, None, None, 1.0, n)
    rets = [f - 1.0 for f in factors]
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    std = math.sqrt(var)
    sharpe = (mean / std) * math.sqrt(MONTHS_PER_YEAR) if std > 0 else 0.0
    vol_pct = std * math.sqrt(MONTHS_PER_YEAR) * 100.0
    curve = equity_curve(factors)
    final = curve[-1]
    years = n / MONTHS_PER_YEAR
    cagr_pct = ((final ** (1.0 / years)) - 1.0) * 100.0 if final > 0 else -100.0
    max_dd = float(max_drawdown_pct(curve))
    calmar = calmar_ratio(
        total_return_pct=(final - 1.0) * 100.0,
        max_drawdown_pct=max_dd,
        n_obs=n,
        periods_per_year=MONTHS_PER_YEAR,
    )
    psr = probabilistic_sharpe_ratio(rets, benchmark_sharpe_annual=0)
    pct_in = (sum(1 for x in in_market if x) / len(in_market)) if in_market else 1.0
    return LegStats(
        cagr_pct=cagr_pct,
        vol_pct=vol_pct,
        sharpe=sharpe,
        max_dd_pct=max_dd,
        calmar=float(calmar) if calmar is not None else None,
        psr_gt0=float(psr) if psr is not None else None,
        pct_in_market=pct_in,
        n_months=n,
    )


@dataclass(frozen=True)
class Comparison:
    """단순 보유 vs 추세 타이밍 — 위험관리 베타 판정."""

    buy_hold: LegStats
    trend: LegStats
    window: int
    verdict: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "window": self.window,
            "verdict": self.verdict,
            "reason": self.reason,
            "buy_hold": self.buy_hold.as_dict(),
            "trend": self.trend.as_dict(),
        }


def _classify(bh: LegStats, tr: LegStats) -> tuple[str, str]:
    """위험관리 엣지 판정(사전 등록 기준 — 자본 방어 중심).

    추세 오버레이가 *위험조정으로* 가치를 더하려면: ① 최대낙폭을 의미 있게 줄이고(≤0.8배),
    ② 칼마(수익/낙폭)를 올리고, ③ 샤프를 단순 보유보다 떨어뜨리지 않아야 한다. 셋 다면
    RISK_MANAGED_EDGE(폭락 방어가 위험조정 수익을 올림). 아니면 NO_IMPROVEMENT.
    """
    if bh.calmar is None or tr.calmar is None:
        return "INSUFFICIENT", "칼마 정의 불가(낙폭 0 또는 데이터 부족)"
    dd_cut = tr.max_dd_pct <= 0.8 * bh.max_dd_pct
    calmar_up = tr.calmar > bh.calmar
    sharpe_ok = tr.sharpe >= bh.sharpe
    if dd_cut and calmar_up and sharpe_ok:
        return (
            "RISK_MANAGED_EDGE",
            f"낙폭 {bh.max_dd_pct:.0f}%→{tr.max_dd_pct:.0f}%(방어), "
            f"칼마 {bh.calmar:.2f}→{tr.calmar:.2f}, 샤프 {bh.sharpe:.2f}→{tr.sharpe:.2f}",
        )
    fails = []
    if not dd_cut:
        fails.append("낙폭 충분히 안 줄음")
    if not calmar_up:
        fails.append("칼마 개선 없음")
    if not sharpe_ok:
        fails.append("샤프 악화")
    return "NO_IMPROVEMENT", "; ".join(fails)


def compare_trend_overlay(rows: list[MonthlyRow], *, window: int = 10) -> Comparison:
    """단순 보유 총수익 vs N개월 SMA 추세 타이밍을 같은 기간에서 비교."""
    market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    in_mkt = trend_in_market(rows, window)
    strat = overlay_factors(market, cash, in_mkt)
    bh = summarize(market, in_market=None)
    tr = summarize(strat, in_market=in_mkt)
    verdict, reason = _classify(bh, tr)
    return Comparison(buy_hold=bh, trend=tr, window=window, verdict=verdict, reason=reason)


@dataclass(frozen=True)
class TurnoverStats:
    """추세 타이밍의 회전(거래 빈도) — 거래비용이 무는 표면."""

    switches: int
    years: float
    switches_per_year: float


def turnover_stats(in_market: list[bool]) -> TurnoverStats:
    """전환 횟수 + 연 환산 전환 빈도(월간 가정)."""
    n = len(in_market)
    sw = count_switches(in_market)
    years = n / MONTHS_PER_YEAR if n else 0.0
    return TurnoverStats(
        switches=sw,
        years=round(years, 2),
        switches_per_year=round(sw / years, 3) if years > 0 else 0.0,
    )


@dataclass(frozen=True)
class CostedComparison:
    """슬라이스 2 — 비용·세금 반영 후에도 위험관리 엣지가 남는가."""

    buy_hold_net: LegStats  # 단순 보유(최초 매수 비용만, 세금 이연)
    trend_gross: LegStats  # 비용 0(슬라이스 1과 동일)
    trend_net: LegStats  # 거래비용 반영(세금 0 = 이연 계좌)
    trend_net_tax: LegStats | None  # 거래비용 + 세금(과세 계좌, tax_rate>0 일 때만)
    turnover: TurnoverStats
    window: int
    cost_bps: float
    tax_rate: float
    verdict: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "window": self.window,
            "cost_bps": self.cost_bps,
            "tax_rate": self.tax_rate,
            "verdict": self.verdict,
            "reason": self.reason,
            "switches_per_year": self.turnover.switches_per_year,
            "buy_hold_net": self.buy_hold_net.as_dict(),
            "trend_gross": self.trend_gross.as_dict(),
            "trend_net": self.trend_net.as_dict(),
            "trend_net_tax": self.trend_net_tax.as_dict() if self.trend_net_tax else None,
        }


def compare_with_costs(
    rows: list[MonthlyRow],
    *,
    window: int = 10,
    cost_bps: float = 10.0,
    tax_rate: float = 0.0,
    in_market: list[bool] | None = None,
) -> CostedComparison:
    """비용·세금 반영 비교 — 엣지가 거래비용을 견디는지(슬라이스 2의 핵심 질문).

    단순 보유도 최초 매수 비용을 동등하게 문다(공정 비교). 판정은 *비용 반영 추세*(세금 0,
    이연 계좌)를 *비용 반영 단순 보유*와 같은 기준(낙폭↓·칼마↑·샤프 유지)으로 비교 →
    통과면 EDGE_SURVIVES_COSTS. 세금 계좌(tax_rate>0)는 별도 다리로 함께 보고.

    `in_market` 를 주면 그 신호를 쓴다(슬라이스 3: 운영 코드 신호 `production_in_market`
    주입 → 라이브 경로가 같은 결과를 내는지). 없으면 연구 신호(`trend_in_market`).
    """
    market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    in_mkt = in_market if in_market is not None else trend_in_market(rows, window)
    all_in = [True] * len(in_mkt)

    bh_net_factors = apply_cost_model(market, cash, all_in, CostModel(cost_bps, 0.0))
    tr_gross_factors = overlay_factors(market, cash, in_mkt)
    tr_net_factors = apply_cost_model(market, cash, in_mkt, CostModel(cost_bps, 0.0))

    bh_net = summarize(bh_net_factors, in_market=None)
    tr_gross = summarize(tr_gross_factors, in_market=in_mkt)
    tr_net = summarize(tr_net_factors, in_market=in_mkt)
    tr_net_tax = None
    if tax_rate > 0:
        tax_factors = apply_cost_model(market, cash, in_mkt, CostModel(cost_bps, tax_rate))
        tr_net_tax = summarize(tax_factors, in_market=in_mkt)

    base_verdict, base_reason = _classify(bh_net, tr_net)
    verdict = "EDGE_SURVIVES_COSTS" if base_verdict == "RISK_MANAGED_EDGE" else base_verdict
    return CostedComparison(
        buy_hold_net=bh_net,
        trend_gross=tr_gross,
        trend_net=tr_net,
        trend_net_tax=tr_net_tax,
        turnover=turnover_stats(in_mkt),
        window=window,
        cost_bps=cost_bps,
        tax_rate=tax_rate,
        verdict=verdict,
        reason=base_reason,
    )


def vol_target_exposure(
    rows: list[MonthlyRow],
    in_market: list[bool],
    *,
    window: int = 12,
    target_annual_vol: float = 0.12,
    max_scale: float = 1.0,
) -> list[float]:
    """슬라이스 4 — 유효 노출 e_t ∈ [0, max_scale]: 추세 아래면 0, 위면 변동성 타깃 스케일.

    고변동 구간에서 노출을 줄여(하향 전용, max_scale=1 = 무레버리지) 위험을 매끈하게 한다.
    운영 코드 `sizing.realized_volatility`·`volatility_scale` 재사용(같은 잣대). 미래 누출 0:
    period i 의 노출은 `prices[:i+1]`(직전 월까지)의 후행 변동성으로만 정한다. 이력 부족이면
    노출 1(타깃 불가 → 추세 신호만 따름).
    """
    prices = [Decimal(str(r.price)) for r in rows]
    target_m = Decimal(str(target_annual_vol)) / Decimal(MONTHS_PER_YEAR).sqrt()
    max_s = Decimal(str(max_scale))
    exposure: list[float] = []
    for i in range(len(in_market)):
        if not in_market[i]:
            exposure.append(0.0)
            continue
        recent = prices[max(0, i + 1 - window) : i + 1]
        rv = realized_volatility(recent)
        if rv is None:
            exposure.append(float(max_s))  # 이력 부족 → 기본 노출(추세만 따름)
        else:
            exposure.append(float(volatility_scale(rv, target_m, max_scale=max_s)))
    return exposure


def combined_factors(
    market: list[float], cash: list[float], exposure: list[float]
) -> list[float]:
    """유효 노출 e 로 자산/현금 혼합한 월간 팩터: e*시장 + (1-e)*현금."""
    if not (len(market) == len(cash) == len(exposure)):
        raise ValueError("length mismatch")
    return [e * m + (1.0 - e) * c for m, c, e in zip(market, cash, exposure, strict=True)]


def apply_exposure_costs(
    market: list[float], cash: list[float], exposure: list[float], cost_bps: float
) -> list[float]:
    """노출 변화량 |Δe| 에 거래비용을 매긴 순 팩터(연속 리밸런싱 회전 반영).

    이진 추세(0↔1)의 전환 비용을 일반화한다 — 변동성 타깃은 매월 노출을 조금씩 바꾸므로
    회전이 늘고, 그 비용을 정직히 |e_t − e_{t-1}| × cost 로 문다(추세만일 때와 동일 한도).
    """
    cost_rate = cost_bps / 10_000.0
    net: list[float] = []
    prev_e = 0.0
    for m, c, e in zip(market, cash, exposure, strict=True):
        f = e * m + (1.0 - e) * c
        f *= 1.0 - cost_rate * abs(e - prev_e)
        net.append(f)
        prev_e = e
    return net


@dataclass(frozen=True)
class VolTargetComparison:
    """슬라이스 4 — 추세 위에 변동성 타깃을 얹으면 위험조정 수익이 더 오르는가."""

    buy_hold_net: LegStats
    trend_net: LegStats  # 추세만(이진 노출)
    trend_vol_net: LegStats  # 추세 + 변동성 타깃
    avg_exposure: float  # 추세+변동성 타깃의 평균 노출
    window: int
    target_annual_vol: float
    cost_bps: float
    verdict: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "window": self.window,
            "target_annual_vol": self.target_annual_vol,
            "cost_bps": self.cost_bps,
            "avg_exposure": round(self.avg_exposure, 3),
            "verdict": self.verdict,
            "reason": self.reason,
            "buy_hold_net": self.buy_hold_net.as_dict(),
            "trend_net": self.trend_net.as_dict(),
            "trend_vol_net": self.trend_vol_net.as_dict(),
        }


def _classify_vol(trend: LegStats, trend_vol: LegStats) -> tuple[str, str]:
    """변동성 타깃이 추세 위에 *위험조정* 가치를 더하는가: 샤프↑ 그리고 칼마↑ 면 추가 가치."""
    sharpe_up = trend_vol.sharpe > trend.sharpe
    calmar_up = (
        trend.calmar is not None
        and trend_vol.calmar is not None
        and trend_vol.calmar > trend.calmar
    )
    if sharpe_up and calmar_up:
        return (
            "VOL_TARGET_ADDS",
            f"샤프 {trend.sharpe:.2f}→{trend_vol.sharpe:.2f}, "
            f"칼마 {(trend.calmar or 0):.2f}→{(trend_vol.calmar or 0):.2f}",
        )
    return (
        "NO_ADDITIONAL_BENEFIT",
        f"샤프 {trend.sharpe:.2f}→{trend_vol.sharpe:.2f}, "
        f"칼마 {(trend.calmar or 0):.2f}→{(trend_vol.calmar or 0):.2f}(추가 가치 미미)",
    )


def compare_with_vol_target(
    rows: list[MonthlyRow],
    *,
    window: int = 10,
    vol_window: int = 12,
    target_annual_vol: float = 0.12,
    cost_bps: float = 10.0,
) -> VolTargetComparison:
    """추세만 vs 추세+변동성 타깃 — 변동성 타깃이 위험조정 수익을 더 올리는지(슬라이스 4)."""
    market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    in_mkt = trend_in_market(rows, window)
    all_in = [True] * len(in_mkt)
    exposure = vol_target_exposure(
        rows, in_mkt, window=vol_window, target_annual_vol=target_annual_vol
    )

    bh_net = summarize(apply_cost_model(market, cash, all_in, CostModel(cost_bps, 0.0)))
    tr_net = summarize(
        apply_cost_model(market, cash, in_mkt, CostModel(cost_bps, 0.0)), in_market=in_mkt
    )
    tv_net_factors = apply_exposure_costs(market, cash, exposure, cost_bps)
    tv_net = summarize(tv_net_factors, in_market=[e > 0 for e in exposure])
    avg_exp = sum(exposure) / len(exposure) if exposure else 0.0

    verdict, reason = _classify_vol(tr_net, tv_net)
    return VolTargetComparison(
        buy_hold_net=bh_net,
        trend_net=tr_net,
        trend_vol_net=tv_net,
        avg_exposure=avg_exp,
        window=window,
        target_annual_vol=target_annual_vol,
        cost_bps=cost_bps,
        verdict=verdict,
        reason=reason,
    )


__all__ = [
    "Comparison",
    "CostModel",
    "CostedComparison",
    "LegStats",
    "MonthlyRow",
    "TurnoverStats",
    "VolTargetComparison",
    "apply_cost_model",
    "apply_exposure_costs",
    "combined_factors",
    "compare_with_costs",
    "compare_with_vol_target",
    "vol_target_exposure",
    "count_switches",
    "turnover_stats",
    "cash_factors",
    "compare_trend_overlay",
    "equity_curve",
    "market_total_return_factors",
    "overlay_factors",
    "parse_shiller",
    "production_in_market",
    "summarize",
    "trend_in_market",
]
