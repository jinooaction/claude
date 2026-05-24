"""Spec 004 T007 — 판단 지점 레지스트리 (헌법 III 계약 선언)."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.judgment import registry
from auto_invest.judgment.schemas import (
    DailySummaryAdvisory,
    NewsAdvisory,
    VolatilityAdvisory,
)


def test_three_points_registered():
    classes = set(registry.decision_classes())
    assert classes == {"volatility_assessment", "daily_summary", "news_screen"}


def test_each_point_declares_full_contract():
    """헌법 III: 트리거·입력·출력 스키마·지연 예산·비용 예산이 전부 선언됨."""
    for jp in registry.all_points():
        assert jp.decision_class
        assert jp.output_schema is not None
        assert jp.latency_budget_ms > 0
        assert jp.cost_budget_usd > Decimal("0")
        assert jp.model
        assert jp.max_tokens > 0
        assert jp.trigger_description
        assert jp.input_contract
        assert jp.fallback_description


def test_volatility_contract():
    jp = registry.get("volatility_assessment")
    assert jp.output_schema is VolatilityAdvisory
    assert jp.latency_budget_ms == 2_000
    assert jp.cost_budget_usd == Decimal("0.01")
    assert jp.affects_capital is True


def test_daily_summary_does_not_affect_capital():
    jp = registry.get("daily_summary")
    assert jp.output_schema is DailySummaryAdvisory
    assert jp.affects_capital is False


def test_news_screen_contract():
    jp = registry.get("news_screen")
    assert jp.output_schema is NewsAdvisory
    assert jp.affects_capital is False
