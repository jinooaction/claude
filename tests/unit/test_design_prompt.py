"""Spec 010 T008 + T027 — Claude prompt 조립 + 응답 파싱.

contracts/claude-prompt.md 명세대로 동작하는지 검증.
"""

from __future__ import annotations

from decimal import Decimal

from auto_invest.design.prompt import (
    build_system_prompt,
    build_user_prompt,
    parse_claude_response,
)

# ---------------------------------------------------------- system prompt


def test_system_prompt_includes_safety_constraints():
    p = build_system_prompt()
    # 헌법 I·II·III·VI 안전 제약이 모두 언급
    assert "per_trade_pct" in p
    assert "whitelist" in p
    assert "CANARY" in p
    assert "ERROR:" in p  # 잔고 부족 응답 양식 명시
    assert "INTERPRETATION:" in p


# ---------------------------------------------------------- user prompt


def test_user_prompt_includes_intent_and_balance():
    p = build_user_prompt(
        intent="자본 100달러, 미국 대형주 분산",
        kis_balance_usd=Decimal("102.45"),
        kis_holdings=[
            {"symbol": "VOO", "qty": 0.2, "avg_cost_usd": "450.00"},
        ],
    )
    assert "자본 100달러" in p
    assert "102.45 USD" in p
    assert "VOO" in p


def test_user_prompt_empty_holdings():
    p = build_user_prompt(
        intent="x",
        kis_balance_usd=Decimal("100"),
        kis_holdings=[],
    )
    assert "보유 종목 없음" in p


def test_user_prompt_includes_retry_context_only_on_retry():
    # 1회차 호출: retry block 없음
    p1 = build_user_prompt(
        intent="x", kis_balance_usd=Decimal("100"), kis_holdings=[],
    )
    assert "직전 시도" not in p1

    # 2회차+: retry block 포함
    p2 = build_user_prompt(
        intent="x",
        kis_balance_usd=Decimal("100"),
        kis_holdings=[],
        retry_context={
            "reason": "parse_error",
            "detail": "TOML 파싱 실패",
            "previous_toml": "[invalid",
        },
    )
    assert "직전 시도" in p2
    assert "parse_error" in p2
    assert "[invalid" in p2


# ---------------------------------------------------------- response parsing


def test_parse_normal_response():
    text = """\
# INTERPRETATION: {"max_drawdown_pct": 5, "per_symbol_pct": 20, "universe": ["VOO", "QQQ"]}

[caps]
per_trade_pct = 5
per_symbol_pct = 20

[whitelist]
symbols = ["VOO", "QQQ"]
"""
    result = parse_claude_response(text)
    assert result.error is None
    assert result.interpretation["max_drawdown_pct"] == 5
    assert result.interpretation["universe"] == ["VOO", "QQQ"]
    assert "[caps]" in result.rules_toml
    # INTERPRETATION 주석은 본문에서 제거되어야 함
    assert "INTERPRETATION" not in result.rules_toml


def test_parse_error_response():
    text = "ERROR: 잔고 부족 (현재 잔고 $5, 의도 자본 $100)"
    result = parse_claude_response(text)
    assert result.error is not None
    assert "잔고 부족" in result.error


def test_parse_missing_interpretation_returns_empty_dict():
    """INTERPRETATION 주석이 없어도 파서가 죽지 않아야 함 (Claude가 빼먹은 경우).

    그러면 interpretation은 {} 이 되고 본문이 그대로 TOML로 들어감.
    """
    text = "[caps]\nper_trade_pct = 5\n"
    result = parse_claude_response(text)
    assert result.error is None
    assert result.interpretation == {}
    assert "[caps]" in result.rules_toml


def test_parse_invalid_json_in_interpretation():
    """INTERPRETATION이 JSON 파싱 실패하면 interpretation={} + 본문은 그대로."""
    text = """\
# INTERPRETATION: {invalid json

[caps]
per_trade_pct = 5
"""
    result = parse_claude_response(text)
    assert result.interpretation == {}
    assert "[caps]" in result.rules_toml
