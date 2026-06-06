"""스펙 046 — 일일 전략 모니터: 검증된 스펙들을 합친 *지속 감시* 대시보드.

운영자 지시(2026-06-06): "이어서 자율 수행해. 세계 최고 수준으로 돈 벌자." 앞서 제안한 지속
감시 배선을 단순 모니터링이 아니라 *세계 최고 수준의 일일 대시보드*로 만든다.

매 forward 페이퍼 실행마다(또는 수동) Shiller 데이터로 네 가지를 한눈에 답한다:
  ① 엣지가 *최근에도* 유효한가 — 최근 5·10년 분산 추세 샤프(스펙 045).
  ② 분산 가정이 *지금* 신뢰 가능한가 — 주식·채권 상관 regime 판정(스펙 045).
  ③ 내 낙폭 예산에서 레버리지로 복리 얼마인가 — 성장 최적 레버리지 권고(스펙 044).
  ④ 오늘 추세 신호 — S&P vs 10개월 SMA, 투자/현금(스펙 042).

읽기 전용·순수·결정론·비커널. 주문 0건, 돈 0 이동. 라이브 레버리지/무장 변경 없음(이건
감시 보고이지 거래 변경이 아니다 — 라이브는 운영자 게이트, 헌법 X.4).
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.analytics.growth_optimal import (
    drawdown_constrained_optimal,
    growth_curve,
    growth_point,
    risk_free_monthly,
)
from auto_invest.analytics.multi_asset_trend import diversified_trend_factors
from auto_invest.analytics.regime_audit import (
    correlation_regime,
    slice_by_year,
    window_stats,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow, current_signal

DEFAULT_LEVERAGES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
# 레버리지 권고는 *최근 regime* 데이터로 계산한다(스펙 045 원칙 — 먼 과거 대공황 낙폭에
# 레버리지를 묶지 않는다). 단 충분한 스트레스(닷컴 2000·GFC 2008·코로나 2020·2022 동반폭락)를
# 포함하도록 ~25년을 쓴다: 최근이라 regime 관련성 있고, 길어서 꼬리위험을 과소평가하지 않는다.
DEFAULT_LEVERAGE_WINDOW_YEARS = 25


@dataclass(frozen=True)
class Dashboard:
    """일일 전략 대시보드 — 네 가지 판정의 스냅샷."""

    as_of: str
    # ① 최근 엣지(분산 추세 샤프)
    edge_5y_sharpe: float | None
    edge_10y_sharpe: float | None
    edge_5y_maxdd_pct: float | None
    # ② 분산 가정 regime
    corr_current: float | None
    corr_recent_5y_avg: float | None
    regime_verdict: str
    # ③ 성장 최적 레버리지 권고(낙폭 예산) — 최근 regime 데이터 기준
    dd_budget_pct: float
    leverage_window_years: int
    unlevered_cagr_pct: float | None
    rec_leverage: float | None
    rec_cagr_pct: float | None
    rec_maxdd_pct: float | None
    # ④ 오늘 추세 신호
    signal_in_market: bool | None
    signal_gap_pct: float | None

    def as_dict(self) -> dict:
        def _r(x):
            return round(x, 3) if isinstance(x, float) else x
        return {
            "as_of": self.as_of,
            "edge": {
                "diversified_5y_sharpe": _r(self.edge_5y_sharpe),
                "diversified_10y_sharpe": _r(self.edge_10y_sharpe),
                "diversified_5y_maxdd_pct": _r(self.edge_5y_maxdd_pct),
            },
            "regime": {
                "corr_current": _r(self.corr_current),
                "corr_recent_5y_avg": _r(self.corr_recent_5y_avg),
                "verdict": self.regime_verdict,
            },
            "leverage_recommendation": {
                "dd_budget_pct": self.dd_budget_pct,
                "window_years": self.leverage_window_years,
                "unlevered_cagr_pct": _r(self.unlevered_cagr_pct),
                "leverage": _r(self.rec_leverage),
                "cagr_pct": _r(self.rec_cagr_pct),
                "maxdd_pct": _r(self.rec_maxdd_pct),
            },
            "today_signal": {
                "in_market": self.signal_in_market,
                "gap_pct": _r(self.signal_gap_pct),
            },
        }

    def as_text(self) -> str:
        sig = (
            ("투자(추세 위)" if self.signal_in_market else "현금(추세 아래)")
            if self.signal_in_market is not None
            else "N/A"
        )
        lev = (
            f"L={self.rec_leverage:.1f} → 복리 {self.rec_cagr_pct:.1f}%/년 "
            f"(낙폭 {self.rec_maxdd_pct:.0f}%)"
            if self.rec_leverage is not None
            else "N/A"
        )
        lines = [
            f"# 일일 전략 모니터 (as of {self.as_of}) — 읽기 전용, 돈 0 이동",
            "",
            "① 엣지(분산 추세)가 최근에도 유효한가:",
            f"   최근 5년 샤프 {self._f(self.edge_5y_sharpe)} | 최근 10년 샤프 "
            f"{self._f(self.edge_10y_sharpe)} | 최근 5년 낙폭 {self._f(self.edge_5y_maxdd_pct)}%",
            "",
            "② 분산 가정이 지금 신뢰 가능한가 (주식·채권 상관):",
            f"   현재 {self._f(self.corr_current)} | 최근 5년 평균 "
            f"{self._f(self.corr_recent_5y_avg)} → 판정: {self.regime_verdict}",
            "",
            f"③ 낙폭 예산 {self.dd_budget_pct:.0f}%에서 레버리지 복리 권고 "
            f"(최근 {self.leverage_window_years}년 기준):",
            f"   무레버 복리 {self._f(self.unlevered_cagr_pct)}% → 권고 {lev}",
            "",
            "④ 오늘 추세 신호 (S&P vs 10개월 SMA):",
            f"   {sig} (갭 {self._f(self.signal_gap_pct)}%)",
            "",
            "⚠ 이건 감시 보고다. 라이브 레버리지/무장은 운영자 게이트(헌법 X.4).",
        ]
        return "\n".join(lines)

    @staticmethod
    def _f(x) -> str:
        return f"{x:+.2f}" if isinstance(x, float) else "N/A"


def build_dashboard(
    rows: list[MonthlyRow],
    *,
    window: int = 10,
    dd_budget_pct: float = 15.0,
    leverage_window_years: int = DEFAULT_LEVERAGE_WINDOW_YEARS,
    leverages: list[float] | None = None,
) -> Dashboard:
    """Shiller 행들로 일일 대시보드를 구성(네 판정 합성)."""
    levs = leverages if leverages is not None else DEFAULT_LEVERAGES
    last_year = int(rows[-1].date[:4])

    # ① 최근 엣지
    w5 = window_stats(rows, "최근 5년", last_year - 4, None, window=window)
    w10 = window_stats(rows, "최근 10년", last_year - 9, None, window=window)

    # ② regime
    reg = correlation_regime(rows, window=36)

    # ③ 성장 최적 레버리지 권고 — *최근 regime* 데이터 기준(스펙 045 원칙: 먼 과거 대공황
    #    낙폭에 레버리지를 묶지 않되, ~25년이라 닷컴·GFC·코로나·2022 스트레스는 포함).
    div_full = diversified_trend_factors(rows, window=window)
    rf_full = risk_free_monthly(rows)
    start_year = last_year - leverage_window_years + 1
    div = slice_by_year(rows, div_full, start_year, None)
    rf = slice_by_year(rows, rf_full, start_year, None)
    unlev = growth_point(div, rf, leverage=1.0) if len(div) >= 24 else None
    dd_opt = None
    if len(div) >= 24:
        curve = growth_curve(div, rf, leverages=levs)
        dd_opt = drawdown_constrained_optimal(curve, max_dd_pct=dd_budget_pct)

    # ④ 오늘 신호
    sig = current_signal(rows, window=window)

    return Dashboard(
        as_of=rows[-1].date[:7],
        edge_5y_sharpe=w5.diversified.sharpe,
        edge_10y_sharpe=w10.diversified.sharpe,
        edge_5y_maxdd_pct=w5.diversified.max_dd_pct,
        corr_current=reg.current,
        corr_recent_5y_avg=reg.recent_5y_avg,
        regime_verdict=reg.verdict,
        dd_budget_pct=dd_budget_pct,
        leverage_window_years=leverage_window_years,
        unlevered_cagr_pct=unlev.cagr_pct if unlev else None,
        rec_leverage=dd_opt.leverage if dd_opt else None,
        rec_cagr_pct=dd_opt.cagr_pct if dd_opt else None,
        rec_maxdd_pct=dd_opt.max_dd_pct if dd_opt else None,
        signal_in_market=sig.in_market if sig else None,
        signal_gap_pct=sig.gap_pct if sig else None,
    )


__all__ = ["DEFAULT_LEVERAGES", "Dashboard", "build_dashboard"]
