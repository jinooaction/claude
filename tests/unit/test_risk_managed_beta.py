"""스펙 042 — 위험관리된 베타(추세 타이밍 오버레이) 단위 테스트."""

from __future__ import annotations

from auto_invest.analytics.risk_managed_beta import (
    CostModel,
    MonthlyRow,
    apply_cost_model,
    cash_factors,
    compare_trend_overlay,
    compare_with_costs,
    count_switches,
    equity_curve,
    market_total_return_factors,
    overlay_factors,
    parse_shiller,
    production_in_market,
    summarize,
    trend_in_market,
    turnover_stats,
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


def test_count_switches_counts_initial_buy_and_state_changes():
    # 현금에서 시작 가정 → 첫 True 가 최초 매수(1).
    assert count_switches([True, True, True]) == 1  # 최초 매수만
    assert count_switches([True, False, True]) == 3  # 매수, 매도, 재매수
    assert count_switches([False, False]) == 0  # 줄곧 현금 → 거래 없음
    assert count_switches([]) == 0


def test_turnover_stats_per_year():
    # 24개월(2년)에 전환 4회 → 2회/년.
    sig = [True, False, True, False] * 6  # 24개, 매 칸 전환 + 최초 매수
    ts = turnover_stats(sig)
    assert ts.years == 2.0
    assert ts.switches == count_switches(sig)
    assert ts.switches_per_year == round(ts.switches / 2.0, 3)


def test_cost_model_buyhold_pays_only_initial_buy():
    # 줄곧 투자(단순 보유)면 최초 매수 비용 1회만 — 이후 팩터는 비용 0.
    market = [1.05, 1.02, 0.98]
    cash = [1.0, 1.0, 1.0]
    all_in = [True, True, True]
    net = apply_cost_model(market, cash, all_in, CostModel(cost_bps=100.0, tax_rate=0.0))
    assert abs(net[0] - 1.05 * 0.99) < 1e-9  # 최초 매수 1% 비용
    assert abs(net[1] - 1.02) < 1e-9  # 이후 비용 없음
    assert abs(net[2] - 0.98) < 1e-9


def test_cost_model_charges_each_switch():
    market = [1.10, 1.10, 1.10]
    cash = [1.0, 1.0, 1.0]
    sig = [True, False, True]  # 매수, 매도, 재매수 = 전환 3회
    net = apply_cost_model(market, cash, sig, CostModel(cost_bps=100.0, tax_rate=0.0))
    # 세 기간 모두 전환이라 모두 1% 비용.
    assert abs(net[0] - 1.10 * 0.99) < 1e-9
    assert abs(net[1] - 1.00 * 0.99) < 1e-9
    assert abs(net[2] - 1.10 * 0.99) < 1e-9


def test_tax_only_on_realized_gain_at_sell():
    # 한 달 +10% 상승 후 매도 → 이익에 50% 과세. 거래비용 0 으로 세금만 분리.
    market = [1.10]
    cash = [1.0]
    # 진입은 첫 기간(매수), 이익 실현 시점을 보려면 두 기간 필요.
    market2 = [1.10, 1.0]  # t0 투자 +10%, t1 현금(매도)
    cash2 = [1.0, 1.0]
    sig = [True, False]
    net = apply_cost_model(market2, cash2, sig, CostModel(cost_bps=0.0, tax_rate=0.5))
    # t0: 매수(비용0), 자산 1.0→1.1. t1: 매도, 이익 0.1 에 50% 세금=0.05 → 팩터 *= (1-0.05/1.1).
    assert abs(net[0] - 1.10) < 1e-9
    expected_t1 = 1.0 * (1.0 - 0.05 / 1.10)
    assert abs(net[1] - expected_t1) < 1e-9
    _ = (market, cash)  # 사용 안 함 가드


def test_compare_with_costs_edge_survives_low_turnover():
    # 저회전 합성 폭락: 추세 방어가 낮은 비용에서도 엣지를 유지해야 한다.
    prices = [100.0 * (1.008**i) for i in range(80)]
    prices += [prices[-1] * (0.93**i) for i in range(1, 16)]
    prices += [prices[-1] * (1.01**i) for i in range(1, 60)]
    rows = _rows(prices)
    cmp = compare_with_costs(rows, window=10, cost_bps=10.0, tax_rate=0.0)
    assert cmp.verdict in {"EDGE_SURVIVES_COSTS", "NO_IMPROVEMENT", "INSUFFICIENT"}
    # 비용은 작아야(저회전) — 비용후 CAGR 가 비용전보다 약간만 낮다.
    assert cmp.trend_net.cagr_pct <= cmp.trend_gross.cagr_pct
    assert cmp.trend_net.cagr_pct > cmp.trend_gross.cagr_pct - 1.0  # 1%p 미만 잠식
    assert cmp.turnover.switches_per_year < 5.0  # 저회전


def test_production_signal_matches_research_signal():
    # 슬라이스 3 브리지: 운영 코드(strategy.trend.above_trend) 신호가 연구 신호와 같아야
    # 한다 — 같아야 "검증된 엣지가 라이브 코드 경로에 그대로 실린다"가 성립.
    prices = [100.0 * (1.007**i) for i in range(50)]
    prices += [prices[-1] * (0.95**i) for i in range(1, 14)]
    prices += [prices[-1] * (1.012**i) for i in range(1, 30)]
    rows = _rows(prices)
    research = trend_in_market(rows, window=10)
    prod = production_in_market(rows, lookback=10)
    assert prod == research


def test_production_signal_reproduces_drawdown_defense():
    # 운영 신호로도 추세 방어(낙폭 축소)가 나와야 한다.
    prices = [100.0 * (1.008**i) for i in range(80)]
    prices += [prices[-1] * (0.93**i) for i in range(1, 16)]
    prices += [prices[-1] * (1.01**i) for i in range(1, 50)]
    rows = _rows(prices)
    prod = production_in_market(rows, lookback=10)
    cmp = compare_with_costs(rows, window=10, in_market=prod)
    assert cmp.trend_net.max_dd_pct < cmp.buy_hold_net.max_dd_pct


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
