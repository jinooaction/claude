"""스펙 050×044 — 자본 사다리 순 복리 시뮬레이션 단위 테스트.

순수·결정론. 사다리 동역학(승격/강등/정지)과 "낮은 낙폭이 단을 유지해 순 복리를 지킨다"는
핵심 메커니즘을 합성 스트림으로 못 박는다.
"""

from __future__ import annotations

from auto_invest.analytics.ladder_simulation import (
    LadderGrowthResult,
    simulate_ladder_growth,
)
from auto_invest.portfolio.capital_ladder import MAX_RUNG, RUNG_FRACTIONS


def test_smooth_strategy_climbs_and_holds_top_rung() -> None:
    # 낙폭 없는 꾸준한 +1%/월 → 매 calm 월 승격, 단 3 도달 후 유지.
    res = simulate_ladder_growth([0.01] * 12, start_rung=1)
    assert res.demotions == 0
    assert res.halts == 0
    assert res.promotions == 3  # 1→2, 2→3, 3→4
    assert res.rung_months[4] == 9  # 네 번째 달부터 단 4
    assert res.avg_rung > 2.0


def test_drawdown_over_half_budget_demotes() -> None:
    # 단 1 진입 직후 -12% → 낙폭 12% ≥ 예산/2(10%) → 강등(단 0).
    res = simulate_ladder_growth([-0.12], start_rung=1, dd_budget_pct=20.0)
    assert res.demotions == 1
    assert res.halts == 0


def test_drawdown_over_full_budget_halts() -> None:
    # 단 1 진입 직후 -22% → 낙폭 22% ≥ 예산(20%) → 정지(단 0).
    res = simulate_ladder_growth([-0.22], start_rung=1, dd_budget_pct=20.0)
    assert res.halts == 1
    assert res.demotions == 0


def test_unconstrained_is_raw_full_deployment() -> None:
    # unconstrained 는 항상 100% 배포(사다리 없음) = raw 전략 복리.
    rets = [0.02, -0.01, 0.03, 0.00, 0.015]
    res = simulate_ladder_growth(rets, start_rung=1)
    raw = 1.0
    for r in rets:
        raw *= 1.0 + r
    assert abs(res.unconstrained_nav_multiple - raw) < 1e-12


def test_zero_returns_grow_nothing_but_climb() -> None:
    res = simulate_ladder_growth([0.0] * 6, start_rung=1)
    assert abs(res.final_nav_multiple - 1.0) < 1e-12
    assert res.demotions == 0 and res.halts == 0
    assert res.avg_rung > 1.0  # 낙폭 0 이라 계속 승격


def test_low_drawdown_holds_higher_rung_than_choppy() -> None:
    # 핵심 메커니즘: 같은 길이에서 낮은 낙폭 스트림이 더 높은 평균 단을 유지한다.
    smooth = [0.005] * 24
    choppy = ([0.06, -0.115] * 12)  # 주기적 11.5% 낙폭 → 반복 강등
    s = simulate_ladder_growth(smooth, start_rung=1)
    c = simulate_ladder_growth(choppy, start_rung=1)
    assert s.demotions == 0
    assert c.demotions >= 1
    assert s.avg_rung > c.avg_rung


def test_protective_ladder_beats_raw_on_sustained_decline() -> None:
    # 지속 하락(-8%/월)에선 사다리가 강등으로 노출을 단계적으로 컷 → raw 보유보다 NAV 보존.
    # (느린 하락은 단 진입 후 낙폭이 리셋돼 강등 churn 을 내고, 빠른 ≥20% 하락에서만 정지.)
    decline = [-0.08] * 10
    res = simulate_ladder_growth(decline, start_rung=1)
    assert res.final_nav_multiple > res.unconstrained_nav_multiple
    assert res.demotions >= 1  # 노출이 단계적으로 컷됨(보호 작동)


def test_single_deep_month_halts() -> None:
    # 단 진입 후 한 달에 ≥20% 빠지면 정지(강등 churn 과 달리 즉시 단 0).
    res = simulate_ladder_growth([0.0, -0.22], start_rung=1, dd_budget_pct=20.0)
    assert res.halts == 1


def test_deterministic_and_dict_shape() -> None:
    rets = [0.02, -0.05, 0.03, -0.11, 0.04, 0.01] * 4
    a = simulate_ladder_growth(rets, start_rung=1)
    b = simulate_ladder_growth(rets, start_rung=1)
    assert a.as_dict() == b.as_dict()
    d = a.as_dict()
    assert set(d) >= {
        "final_nav_multiple", "cagr_pct", "demotions", "halts", "promotions",
        "avg_rung", "rung_months", "unconstrained_nav_multiple",
    }
    assert isinstance(a, LadderGrowthResult)


def test_reuses_spec050_rung_fractions() -> None:
    # 사다리 비율은 스펙 050 단일 출처를 재사용(여기서 재정의 안 함).
    assert RUNG_FRACTIONS[MAX_RUNG] == 1
    assert set(RUNG_FRACTIONS) == {0, 1, 2, 3, 4}
