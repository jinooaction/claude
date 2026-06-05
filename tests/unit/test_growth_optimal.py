"""스펙 044 — 성장 최적 레버리지(고정 자본 복리 극대화) 단위 테스트."""

from __future__ import annotations

from auto_invest.analytics.growth_optimal import (
    compare_leverage,
    drawdown_constrained_optimal,
    growth_curve,
    growth_optimal,
    growth_point,
    lever_factors,
    risk_free_monthly,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow, summarize


def _rows_with_rates(prices: list[float], rates: list[float]) -> list[MonthlyRow]:
    return [
        MonthlyRow(date=f"20{1 + i // 12:02d}-{1 + i % 12:02d}-01", price=p, dividend=0.0,
                   long_rate=rt)
        for i, (p, rt) in enumerate(zip(prices, rates, strict=True))
    ]


# ───────────────────────────── 무위험 수익 ─────────────────────────────


def test_risk_free_monthly_uses_prior_month_rate():
    rows = _rows_with_rates([1, 1, 1], [6.0, 12.0, 3.0])
    rf = risk_free_monthly(rows)
    # period t 는 직전 월 금리 → [6%/12, 12%/12].
    assert len(rf) == 2
    assert abs(rf[0] - 0.06 / 12) < 1e-12
    assert abs(rf[1] - 0.12 / 12) < 1e-12


# ───────────────────────────── 레버리지 팩터 ─────────────────────────────


def test_lever_factors_identity_at_one():
    strat = [1.10, 0.95, 1.03]
    rf = [0.001, 0.001, 0.001]
    assert lever_factors(strat, rf, leverage=1.0) == strat


def test_lever_factors_amplifies_with_borrow_cost():
    strat = [1.10, 0.95]
    rf = [0.001, 0.001]
    out = lever_factors(strat, rf, leverage=2.0, borrow_spread_annual=0.0)
    # L=2: 1 + 2r - 1*rf.
    assert abs(out[0] - (1 + 2 * 0.10 - 0.001)) < 1e-12
    assert abs(out[1] - (1 + 2 * (-0.05) - 0.001)) < 1e-12


def test_lever_factors_deleverage_holds_cash():
    strat = [1.10, 0.95]
    rf = [0.002, 0.002]
    out = lever_factors(strat, rf, leverage=0.5)
    # L<1: 1 + 0.5r + 0.5*rf.
    assert abs(out[0] - (1 + 0.5 * 0.10 + 0.5 * 0.002)) < 1e-12
    assert abs(out[1] - (1 + 0.5 * (-0.05) + 0.5 * 0.002)) < 1e-12


def test_lever_factors_length_mismatch_raises():
    try:
        lever_factors([1.0, 1.0], [0.001], leverage=2.0)
    except ValueError:
        return
    raise AssertionError("length mismatch should raise")


# ───────────────────────────── 성장 점/곡선 ─────────────────────────────


def test_growth_point_unlevered_matches_summarize():
    strat = [1.05, 0.98, 1.03, 1.01, 0.99, 1.04]
    rf = [0.001] * len(strat)
    gp = growth_point(strat, rf, leverage=1.0)
    s = summarize(strat)
    assert abs(gp.cagr_pct - s.cagr_pct) < 1e-9
    assert abs(gp.max_dd_pct - s.max_dd_pct) < 1e-9


def test_leverage_raises_cagr_when_no_ruin():
    # 꾸준한 양의 수익(파산 없음)에 레버리지를 키우면 CAGR 이 오른다.
    strat = [1.02] * 24
    rf = [0.0005] * 24
    g1 = growth_point(strat, rf, leverage=1.0)
    g2 = growth_point(strat, rf, leverage=2.0)
    assert g2.cagr_pct > g1.cagr_pct


def test_excess_leverage_causes_ruin():
    # 단월 손실이 자본을 초과하는 레버리지 → 파산(CAGR -100%, 낙폭 100%).
    strat = [1.05, 0.40, 1.05]  # 둘째 달 -60%
    rf = [0.0] * 3
    gp = growth_point(strat, rf, leverage=2.0)  # 2*(-0.60) = -120% → 자본 음수
    assert gp.cagr_pct == -100.0
    assert gp.max_dd_pct == 100.0
    assert gp.calmar is None


def test_growth_curve_and_optimal():
    strat = [1.015] * 36
    rf = [0.0005] * 36
    curve = growth_curve(strat, rf, leverages=[0.5, 1.0, 2.0, 3.0])
    assert len(curve) == 4
    opt = growth_optimal(curve)
    # 파산 없는 꾸준한 양의 수익 → 격자 안에서 최고 레버리지가 CAGR 최대.
    assert opt.leverage == 3.0


def test_drawdown_constrained_optimal_respects_budget():
    # 변동 있는 스트림: 낙폭 예산이 좁으면 낮은 레버리지를 고른다.
    strat = [1.10, 0.92, 1.08, 0.94, 1.06, 1.02] * 4
    rf = [0.001] * 24
    curve = growth_curve(strat, rf, leverages=[1.0, 2.0, 3.0, 4.0])
    tight = drawdown_constrained_optimal(curve, max_dd_pct=10.0)
    loose = drawdown_constrained_optimal(curve, max_dd_pct=90.0)
    assert tight is not None and loose is not None
    # 좁은 예산의 최적 레버리지 ≤ 넓은 예산의 최적 레버리지.
    assert tight.leverage <= loose.leverage
    assert tight.max_dd_pct <= 10.0


def test_drawdown_constrained_optimal_none_when_all_exceed():
    strat = [1.30, 0.70] * 12  # 변동 극심 → L=1 도 낙폭 큼
    rf = [0.0] * 24
    curve = growth_curve(strat, rf, leverages=[1.0, 2.0])
    assert drawdown_constrained_optimal(curve, max_dd_pct=1.0) is None


def test_compare_leverage_structure():
    a = [1.02, 0.99, 1.01, 1.03, 0.98, 1.02] * 4
    b = [1.01, 1.00, 1.005, 1.01, 0.995, 1.008] * 4
    rf = [0.0005] * 24
    cmp = compare_leverage("A", a, "B", b, rf, leverages=[1.0, 2.0, 3.0], max_dd_budget_pct=25.0)
    d = cmp.as_dict()
    assert d["max_dd_budget_pct"] == 25.0
    assert "A" in d["unlevered"] and "B" in d["unlevered"]
    assert "drawdown_constrained_optimal" in d
