"""스펙 042 — 위험관리된 베타(추세 타이밍 오버레이) 단위 테스트."""

from __future__ import annotations

from auto_invest.analytics.risk_managed_beta import (
    MonthlyRow,
    cash_factors,
    compare_trend_overlay,
    equity_curve,
    market_total_return_factors,
    overlay_factors,
    parse_shiller,
    summarize,
    trend_in_market,
)


def _rows(prices: list[float], *, div: float = 0.0, rate: float = 0.0) -> list[MonthlyRow]:
    return [
        MonthlyRow(
            date=f"20{1 + i // 12:02d}-{1 + i % 12:02d}-01",
            price=p,
            dividend=div,
            long_rate=rate,
        )
        for i, p in enumerate(prices)
    ]


def test_parse_shiller_basic_and_missing_fields():
    csv = (
        "Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate,X\n"
        "1871-01-01,4.44,0.26,0.4,12.46,5.32,0\n"
        "2026-05-01,7412.55,,,,,0\n"  # 최근 달: 배당·금리 미기재(빈칸)
        "1900-01-01,-1,0,0,0,0,0\n"  # 가격<=0 → 제외
    )
    rows = parse_shiller(csv)
    assert len(rows) == 2
    assert rows[0].price == 4.44 and rows[0].dividend == 0.26 and rows[0].long_rate == 5.32
    assert rows[1].dividend == 0.0 and rows[1].long_rate == 0.0  # 빈칸 → 0


def test_market_factors_include_dividends():
    rows = _rows([100.0, 110.0], div=12.0)  # 연배당 12 → 월 1
    f = market_total_return_factors(rows)
    assert len(f) == 1
    # (110 + 12/12) / 100 = 1.11
    assert abs(f[0] - 1.11) < 1e-9


def test_cash_factors_use_prior_rate():
    rows = _rows([100.0, 101.0, 102.0], rate=12.0)  # 연 12% → 월 1%
    c = cash_factors(rows)
    assert len(c) == 2
    assert all(abs(x - 1.01) < 1e-9 for x in c)


def test_cash_factor_zero_rate_is_flat():
    rows = _rows([100.0, 101.0], rate=0.0)
    assert cash_factors(rows) == [1.0]


def test_trend_signal_no_lookahead_and_window():
    # 상승 후 급락. window=3.
    prices = [10, 11, 12, 13, 14, 9, 8, 7]
    rows = _rows([float(p) for p in prices])
    sig = trend_in_market(rows, window=3)
    assert len(sig) == len(prices) - 1
    # 첫 window-1 구간은 SMA 부족 → True(투자).
    assert sig[0] is True and sig[1] is True
    # 상승 구간엔 가격 > SMA → 투자.
    assert sig[3] is True
    # 급락 후엔 가격 < SMA → 현금(False)이 나와야 한다.
    assert sig[-1] is False


def test_overlay_defends_crash_drawdown():
    # 60개월 상승 후 12개월 -50% 폭락. 추세 타이밍이 낙폭을 단순 보유보다 크게 줄여야 한다.
    prices = [100.0 * (1.01**i) for i in range(60)]  # 꾸준한 상승
    crash_start = prices[-1]
    prices += [crash_start * (0.94**i) for i in range(1, 13)]  # 급락(월 -6%)
    rows = _rows(prices)
    market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    sig = trend_in_market(rows, window=10)
    strat = overlay_factors(market, cash, sig)
    bh = summarize(market)
    tr = summarize(strat, in_market=sig)
    # 추세 타이밍은 폭락 초입에 현금으로 빠져 낙폭이 단순 보유보다 작아야 한다.
    assert tr.max_dd_pct < bh.max_dd_pct
    assert tr.pct_in_market < 1.0  # 일부 구간 현금


def test_equity_curve_compounds():
    assert equity_curve([1.1, 1.0, 0.5]) == [1.0, 1.1, 1.1, 0.55]


def test_summarize_flat_market_zero_sharpe():
    rows = _rows([100.0] * 13)
    f = market_total_return_factors(rows)
    s = summarize(f)
    assert s.sharpe == 0.0
    assert s.max_dd_pct == 0.0


def test_compare_smoke_on_synthetic_crash():
    prices = [100.0 * (1.008**i) for i in range(80)]
    prices += [prices[-1] * (0.93**i) for i in range(1, 16)]
    prices += [prices[-1] * (1.01**i) for i in range(1, 40)]  # 회복
    rows = _rows(prices)
    cmp = compare_trend_overlay(rows, window=10)
    assert cmp.verdict in {"RISK_MANAGED_EDGE", "NO_IMPROVEMENT", "INSUFFICIENT"}
    assert cmp.buy_hold.n_months == len(prices) - 1
    # 폭락이 큰 합성 시계열이므로 추세 방어가 낙폭을 줄여야 한다.
    assert cmp.trend.max_dd_pct < cmp.buy_hold.max_dd_pct
