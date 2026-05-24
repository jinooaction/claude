"""Spec 004 T003 — 판단 지점 출력 스키마 검증."""

from __future__ import annotations

import pytest

from auto_invest.judgment.schemas import (
    DailySummaryAdvisory,
    JudgmentSchemaError,
    NewsAdvisory,
    VolatilityAdvisory,
    parse_and_validate,
    schema_for,
)


def test_schema_for_known_classes():
    assert schema_for("volatility_assessment") is VolatilityAdvisory
    assert schema_for("news_screen") is NewsAdvisory
    assert schema_for("daily_summary") is DailySummaryAdvisory


def test_schema_for_unknown_raises():
    with pytest.raises(JudgmentSchemaError):
        schema_for("nope")


def test_volatility_valid():
    adv = parse_and_validate(
        "volatility_assessment",
        '{"action": "size_down", "confidence": 0.8, "reason": "vol spike"}',
    )
    assert isinstance(adv, VolatilityAdvisory)
    assert adv.action == "size_down"
    assert adv.confidence == 0.8


def test_volatility_bad_enum_rejected():
    with pytest.raises(JudgmentSchemaError):
        parse_and_validate(
            "volatility_assessment",
            '{"action": "buy_more", "confidence": 0.5, "reason": "x"}',
        )


def test_volatility_confidence_out_of_range_rejected():
    with pytest.raises(JudgmentSchemaError):
        parse_and_validate(
            "volatility_assessment",
            '{"action": "hold", "confidence": 1.5, "reason": "x"}',
        )


def test_daily_summary_too_long_rejected():
    long_narrative = "x" * 501
    with pytest.raises(JudgmentSchemaError):
        parse_and_validate(
            "daily_summary",
            '{"narrative": "' + long_narrative + '", "alerts": []}',
        )


def test_news_valid():
    adv = parse_and_validate(
        "news_screen", '{"stance": "bear", "confidence": 0.9}'
    )
    assert isinstance(adv, NewsAdvisory)
    assert adv.stance == "bear"


def test_extract_json_from_surrounding_text():
    raw = (
        "Here is my assessment:\n```json\n"
        '{"action": "halt", "confidence": 0.95, "reason": "crash"}\n'
        "```\nDone."
    )
    adv = parse_and_validate("volatility_assessment", raw)
    assert adv.action == "halt"


def test_no_json_raises():
    with pytest.raises(JudgmentSchemaError):
        parse_and_validate("volatility_assessment", "no json here")


def test_extra_field_rejected():
    with pytest.raises(JudgmentSchemaError):
        parse_and_validate(
            "news_screen",
            '{"stance": "bull", "confidence": 0.5, "extra": "x"}',
        )
