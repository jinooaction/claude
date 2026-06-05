"""스펙 042 — 위험관리된 베타(추세 타이밍 오버레이) 단위 테스트."""

from __future__ import annotations

from auto_invest.analytics.risk_managed_beta import (
    CostModel,
    MonthlyRow,
    apply_cost_model,
    apply_exposure_costs,
    cash_factors,
    combined_factors,
    compare_trend_overlay,
    compare_with_costs,
    compare_with_vol_target,
    count_switches,
    current_signal,
    equity_curve,
    event_window_defense,
    market_total_return_factors,
    overlay_factors,
    parse_shiller,
    production_in_market,
    signal_timeline,
    summarize,
    trend_in_market,
    turnover_stats,
    vol_target_exposure,
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


def test_vol_target_zero_exposure_when_trend_below():
    prices = [100.0 + i for i in range(30)]
    rows = _rows(prices)
    in_mkt = [False] * (len(rows) - 1)  # 전부 추세 아래
    exp = vol_target_exposure(rows, in_mkt, window=12, target_annual_vol=0.12)
    assert all(e == 0.0 for e in exp)  # 추세 아래 → 노출 0(현금)


def test_vol_target_throttles_in_high_vol_never_levers():
    # 저변동 상승 후 고변동 구간 → 노출이 1 아래로 줄어야(하향 전용, 절대 1 초과 없음).
    calm = [100.0 * (1.002**i) for i in range(24)]
    wild = []
    base = calm[-1]
    for i in range(24):
        base *= 1.10 if i % 2 == 0 else 0.93  # 큰 등락(고변동)
        wild.append(base)
    rows = _rows(calm + wild)
    in_mkt = [True] * (len(rows) - 1)
    exp = vol_target_exposure(rows, in_mkt, window=12, target_annual_vol=0.12, max_scale=1.0)
    assert all(e <= 1.0 for e in exp)  # 무레버리지
    # 고변동 구간(뒤쪽)의 평균 노출 < 저변동 구간(앞쪽) 평균 노출.
    head = [e for e in exp[:20]]
    tail = [e for e in exp[-20:]]
    assert sum(tail) / len(tail) < sum(head) / len(head)


def test_combined_factors_blend_and_bounds():
    market = [1.1, 1.1]
    cash = [1.0, 1.0]
    # 노출 0.5 → 0.5*1.1 + 0.5*1.0 = 1.05
    assert combined_factors(market, cash, [0.5, 0.5]) == [1.05, 1.05]
    # 노출 1 → 시장, 0 → 현금
    assert combined_factors(market, cash, [1.0, 0.0]) == [1.1, 1.0]


def test_exposure_costs_charge_on_change():
    market = [1.1, 1.1]
    cash = [1.0, 1.0]
    # 0→1 변화(첫 기간) = 1.0 거래, 100bp → 1% 비용. 1→1(둘째) = 변화 0 → 비용 없음.
    net = apply_exposure_costs(market, cash, [1.0, 1.0], cost_bps=100.0)
    assert abs(net[0] - 1.1 * 0.99) < 1e-9
    assert abs(net[1] - 1.1) < 1e-9


def test_compare_with_vol_target_smoke():
    prices = [100.0 * (1.007**i) for i in range(120)]
    prices += [prices[-1] * (0.94**i) for i in range(1, 14)]
    prices += [prices[-1] * (1.01**i) for i in range(1, 60)]
    rows = _rows(prices)
    cmp = compare_with_vol_target(rows, window=10, target_annual_vol=0.12)
    assert cmp.verdict in {"VOL_TARGET_ADDS", "NO_ADDITIONAL_BENEFIT"}
    assert 0.0 <= cmp.avg_exposure <= 1.0
    assert cmp.trend_vol_net.vol_pct <= cmp.trend_net.vol_pct + 1e-6  # 변동성은 안 늘어야


def _dated_rows(start_year: int, prices: list[float]) -> list[MonthlyRow]:
    rows = []
    for i, p in enumerate(prices):
        y = start_year + i // 12
        m = 1 + i % 12
        rows.append(MonthlyRow(date=f"{y:04d}-{m:02d}-01", price=p, dividend=0.0, long_rate=0.0))
    return rows


def test_event_window_defense_detects_slow_bear_defense():
    # 느린 약세장: 24개월 상승 → 18개월 천천히 -40% 하락. 추세가 방어해야 한다.
    prices = [100.0 * (1.01**i) for i in range(24)]
    top = prices[-1]
    prices += [top * (0.97**i) for i in range(1, 19)]
    rows = _dated_rows(2000, prices)
    ev = event_window_defense(rows, "느린약세", "2002-01", "2003-06", window=10)
    assert ev.strategy_drawdown_pct < ev.buy_hold_drawdown_pct
    assert ev.defended is True
    assert ev.months_in_cash > 0


def test_event_window_defense_reports_failure_on_fast_vcrash():
    # 빠른 V자: 한 달 -35% 폭락 후 즉시 회복. 월간 추세는 못 막아 방어 실패가 나야 정직.
    prices = [100.0 * (1.005**i) for i in range(30)]
    crash = prices[-1]
    prices.append(crash * 0.65)  # 한 달 -35%
    prices += [crash * (0.99 + 0.01 * i) for i in range(1, 10)]  # 빠른 회복
    rows = _dated_rows(2018, prices)
    ev = event_window_defense(rows, "V자", "2020-01", "2020-12", window=10)
    # 빠른 폭락은 추세가 못 막는다 — 방어 실패(또는 미미)가 정직한 결과.
    assert ev.strategy_drawdown_pct > 0
    assert ev.defended is False


def test_signal_timeline_records_transitions():
    prices = [100.0 + i for i in range(20)] + [120.0 - 3 * i for i in range(1, 15)]
    rows = _dated_rows(2010, prices)
    tl = signal_timeline(rows, "2010-01", "2012-12", window=10)
    assert tl[0][1] == "투자"  # 상승 구간 시작
    assert any(state == "현금" for _, state in tl)  # 하락 후 현금 전환 존재


def test_current_signal_in_market_when_above_sma():
    prices = [100.0 + i for i in range(20)]  # 꾸준한 상승 → 현재가 > SMA
    rows = _dated_rows(2024, prices)
    cur = current_signal(rows, window=10)
    assert cur is not None
    assert cur.in_market is True
    assert cur.gap_pct > 0
    assert cur.as_of == rows[-1].date[:7]


def test_current_signal_cash_when_below_sma():
    prices = [100.0 + i for i in range(15)] + [114.0 - 4 * i for i in range(1, 6)]
    rows = _dated_rows(2024, prices)
    cur = current_signal(rows, window=10)
    assert cur is not None
    assert cur.in_market is False  # 최근 급락 → 현재가 < SMA
    assert cur.gap_pct < 0


def test_current_signal_none_when_insufficient():
    rows = _dated_rows(2024, [100.0, 101.0, 102.0])
    assert current_signal(rows, window=10) is None


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
