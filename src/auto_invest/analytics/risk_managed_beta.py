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

from auto_invest.backtest.metrics import max_drawdown_pct
from auto_invest.backtest.significance import probabilistic_sharpe_ratio
from auto_invest.portfolio.edge_verdict import calmar_ratio

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


__all__ = [
    "Comparison",
    "LegStats",
    "MonthlyRow",
    "cash_factors",
    "compare_trend_overlay",
    "equity_curve",
    "market_total_return_factors",
    "overlay_factors",
    "parse_shiller",
    "summarize",
    "trend_in_market",
]
