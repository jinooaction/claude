"""Spec 004 T006 — 판단 지점 롤링 비용 예산 가드."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.judgment.budget import BudgetTracker


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_no_budget_means_never_disabled():
    bt = BudgetTracker()
    bt.record("volatility_assessment", Decimal("100"))
    assert bt.is_disabled("volatility_assessment") is False


def test_under_budget_not_disabled():
    bt = BudgetTracker(rolling_budget_usd={"volatility_assessment": Decimal("0.10")})
    bt.record("volatility_assessment", Decimal("0.03"))
    bt.record("volatility_assessment", Decimal("0.04"))
    assert bt.rolling_cost("volatility_assessment") == Decimal("0.07")
    assert bt.is_disabled("volatility_assessment") is False


def test_over_budget_disabled():
    bt = BudgetTracker(rolling_budget_usd={"volatility_assessment": Decimal("0.10")})
    bt.record("volatility_assessment", Decimal("0.06"))
    bt.record("volatility_assessment", Decimal("0.05"))
    assert bt.is_disabled("volatility_assessment") is True


def test_window_eviction():
    clock = _Clock()
    bt = BudgetTracker(
        rolling_budget_usd={"x": Decimal("0.10")},
        window_seconds=100.0,
        clock=clock,
    )
    bt.record("x", Decimal("0.08"))
    assert bt.is_disabled("x") is False
    # 시간이 윈도를 넘어가면 옛 비용이 만료된다.
    clock.t += 200.0
    assert bt.rolling_cost("x") == Decimal("0")
    assert bt.is_disabled("x") is False


def test_per_class_isolation():
    bt = BudgetTracker(
        rolling_budget_usd={"a": Decimal("0.10"), "b": Decimal("0.10")}
    )
    bt.record("a", Decimal("0.20"))
    assert bt.is_disabled("a") is True
    assert bt.is_disabled("b") is False
