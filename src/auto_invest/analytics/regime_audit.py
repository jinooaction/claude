"""스펙 045 — 최근 regime / 시점 강건성 감사: 엣지가 *먼 과거가 아니라 지금도* 통하는가.

운영자 지적(2026-06-05): "너무 먼 과거(1871~) 데이터를 기준으로 분석하는 것 아닌가? 세계
최고 수준이라면 이 기준 자체를 점검해야 한다."

정당한 지적이다. 스펙 042/043/044 는 전부 Shiller 1871~ 로 검증했다. 먼 과거는 *대공황 같은
폭락 표본*을 줘서 통계 검정력엔 좋지만, **regime 비정상성** 위험이 있다 — 1871~1950(금본위·연준
이전·다른 미시구조)은 오늘과 구조가 다르다. 특히 분산 논리는 *주식·채권 비상관* 가정에 기대는데,
**2022 년엔 주식과 채권이 같이 폭락(상관 양수 전환)** 했다. "먼 과거에 통함"이 "지금 통함"을
보장하지 않는다.

이 모듈은 그 기준을 정면 점검한다(순수·결정론·비커널·읽기 전용):
  ① 최근 추적창(5·10·15·20·30년)·연대별로 엣지를 분해 — 쇠퇴 여부.
  ② 주식·채권 *롤링 상관*의 regime 변화 추적 — 특히 *현재* 상관, 2022 양수 전환.
  ③ 2022(주식·채권 동반 폭락)·2020(코로나) 스트레스에서 추세 오버레이가 방어했는가.

세계 최고 수준의 원칙(이 모듈이 강제하는 것): 먼 과거는 *꼬리위험 스트레스 표본*으로만 쓰고,
*엣지 채택 판단*은 최근 regime 증거에 더 무게를 둔다. 그리고 regime(상관)을 *지속 감시*한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.analytics.multi_asset_trend import (
    blend,
    bond_total_return_factors,
    correlation,
    diversified_trend_factors,
    equity_trend_factors,
)
from auto_invest.analytics.risk_managed_beta import (
    LegStats,
    MonthlyRow,
    market_total_return_factors,
    summarize,
)


def factor_year(rows: list[MonthlyRow], index: int) -> int:
    """팩터 index(0..N-2)가 실현된 달의 연도 = rows[index+1] 의 연도."""
    return int(rows[index + 1].date[:4])


def slice_by_year(
    rows: list[MonthlyRow],
    factors: list[float],
    start_year: int,
    end_year: int | None = None,
) -> list[float]:
    """팩터 스트림을 [start_year, end_year] 실현 연도로 자른다(미래 누출 0 — 신호는 전체
    이력으로 미리 계산됨, 워밍업 편향 없음)."""
    out: list[float] = []
    for i, f in enumerate(factors):
        y = factor_year(rows, i)
        if y >= start_year and (end_year is None or y <= end_year):
            out.append(f)
    return out


@dataclass(frozen=True)
class WindowStats:
    """한 시점창에서 세 전략의 위험조정 요약."""

    label: str
    n_months: int
    bh_6040: LegStats
    trend_equity: LegStats
    diversified: LegStats

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "n_months": self.n_months,
            "bh_6040": self.bh_6040.as_dict(),
            "trend_equity": self.trend_equity.as_dict(),
            "diversified": self.diversified.as_dict(),
        }


def _streams(rows: list[MonthlyRow], window: int):
    """세 전략의 *전체 이력* 팩터 스트림(이후 시점창으로 슬라이스)."""
    eq_market = market_total_return_factors(rows)
    bond = bond_total_return_factors(rows)
    bh_6040 = blend([(0.6, eq_market), (0.4, bond)])
    trend_eq = equity_trend_factors(rows, window=window)
    div = diversified_trend_factors(rows, window=window)
    return bh_6040, trend_eq, div


def window_stats(
    rows: list[MonthlyRow],
    label: str,
    start_year: int,
    end_year: int | None = None,
    *,
    window: int = 10,
) -> WindowStats:
    """[start_year,end_year] 시점창에서 60/40 단순보유 vs 단일 주식 추세 vs 분산 추세."""
    bh_6040, trend_eq, div = _streams(rows, window)
    return WindowStats(
        label=label,
        n_months=len(slice_by_year(rows, div, start_year, end_year)),
        bh_6040=summarize(slice_by_year(rows, bh_6040, start_year, end_year)),
        trend_equity=summarize(slice_by_year(rows, trend_eq, start_year, end_year)),
        diversified=summarize(slice_by_year(rows, div, start_year, end_year)),
    )


@dataclass(frozen=True)
class CorrelationRegime:
    """주식·채권 롤링 상관 regime — 분산 가정의 핵심 위험을 추적."""

    window_months: int
    current: float | None  # 가장 최근 창의 상관
    recent_5y_avg: float | None  # 최근 5년 롤링 상관 평균
    recent_5y_pos_fraction: float | None  # 최근 5년 중 상관>0(분산 실패) 비중
    full_avg: float | None

    def as_dict(self) -> dict:
        def _r(x):
            return round(x, 4) if x is not None else None
        return {
            "window_months": self.window_months,
            "current": _r(self.current),
            "recent_5y_avg": _r(self.recent_5y_avg),
            "recent_5y_pos_fraction": _r(self.recent_5y_pos_fraction),
            "full_avg": _r(self.full_avg),
        }


def rolling_correlation_series(
    a: list[float], b: list[float], window: int
) -> list[float]:
    """트레일링 window 개월 롤링 상관 시계열(길이 len-window+1). 분산 0이면 건너뜀."""
    out: list[float] = []
    for end in range(window, len(a) + 1):
        c = correlation(a[end - window:end], b[end - window:end])
        if c is not None:
            out.append(c)
    return out


def correlation_regime(
    rows: list[MonthlyRow], *, window: int = 36
) -> CorrelationRegime:
    """주식·채권 총수익의 롤링 상관 regime — 현재·최근 5년·전체."""
    eq = market_total_return_factors(rows)
    bond = bond_total_return_factors(rows)
    series = rolling_correlation_series(eq, bond, window)
    if not series:
        return CorrelationRegime(window, None, None, None, None)
    recent = series[-60:]  # 최근 ~60 창 ≈ 5년
    recent_pos = sum(1 for c in recent if c > 0) / len(recent) if recent else None
    return CorrelationRegime(
        window_months=window,
        current=series[-1],
        recent_5y_avg=sum(recent) / len(recent) if recent else None,
        recent_5y_pos_fraction=recent_pos,
        full_avg=sum(series) / len(series),
    )


def year_cumulative_return_pct(
    rows: list[MonthlyRow], factors: list[float], year: int
) -> float:
    """달력 연도의 누적 수익률(%) — 스트레스 연도 방어 측정."""
    seg = slice_by_year(rows, factors, year, year)
    prod = 1.0
    for f in seg:
        prod *= f
    return (prod - 1.0) * 100.0


@dataclass(frozen=True)
class StressYear:
    """한 스트레스 연도에서 네 전략의 실제 수익률 — 추세 오버레이 방어 검증."""

    year: int
    bh_equity_pct: float
    bh_6040_pct: float
    trend_equity_pct: float
    diversified_pct: float

    def as_dict(self) -> dict:
        return {
            "year": self.year,
            "bh_equity_pct": round(self.bh_equity_pct, 1),
            "bh_6040_pct": round(self.bh_6040_pct, 1),
            "trend_equity_pct": round(self.trend_equity_pct, 1),
            "diversified_pct": round(self.diversified_pct, 1),
        }


def stress_year(rows: list[MonthlyRow], year: int, *, window: int = 10) -> StressYear:
    """스트레스 연도에서 단순보유 주식·60/40 vs 추세 전략들의 실제 수익률."""
    eq_market = market_total_return_factors(rows)
    bond = bond_total_return_factors(rows)
    bh_6040 = blend([(0.6, eq_market), (0.4, bond)])
    trend_eq = equity_trend_factors(rows, window=window)
    div = diversified_trend_factors(rows, window=window)
    return StressYear(
        year=year,
        bh_equity_pct=year_cumulative_return_pct(rows, eq_market, year),
        bh_6040_pct=year_cumulative_return_pct(rows, bh_6040, year),
        trend_equity_pct=year_cumulative_return_pct(rows, trend_eq, year),
        diversified_pct=year_cumulative_return_pct(rows, div, year),
    )


__all__ = [
    "CorrelationRegime",
    "StressYear",
    "WindowStats",
    "correlation_regime",
    "factor_year",
    "rolling_correlation_series",
    "slice_by_year",
    "stress_year",
    "window_stats",
    "year_cumulative_return_pct",
]
