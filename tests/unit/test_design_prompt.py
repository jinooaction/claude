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


def test_system_prompt_includes_time_trigger_for_dca():
    """적립(DCA) 의도를 룰로 표현할 수 있도록 시간 트리거 사용법이 명시돼야 함.

    회귀 방어: 이 가이드가 없으면 Claude가 'kind=schedule' 또는
    at_time='MON_09:35' 같은 스키마 위반 룰을 만들어 검증 3회 모두 실패한다
    (2026-05-23 design 호출 run 26330304139에서 실제 발생).
    """
    p = build_system_prompt()
    assert 'kind = "time"' in p
    assert "at_time" in p
    assert "weekdays" in p
    assert "604800" in p  # 매주 1회 cooldown 예시
    assert "적립" in p
    # kind는 셋 중 하나만 — schedule 등 금지 명시
    assert "schedule" in p and "절대 쓰지 마세요" in p


def test_system_prompt_includes_holdings_utilization_patterns():
    """보유 종목 활용 패턴 3종(추가 매수·익절·분산 안전장치)이 모두 가이드돼야 함."""
    p = build_system_prompt()
    assert "보유 종목 활용 패턴" in p
    assert "averaging-down" in p or "averaging_down" in p
    assert "추가 매수" in p
    assert "take-profit" in p or "take_profit" in p
    assert "익절" in p
    assert "concentration cap" in p or "concentration_cap" in p
    assert "분산 안전장치" in p
    # holdings_applied 키 사용 가이드 + 예시
    assert "holdings_applied" in p
    # 기본 하락폭/익절폭 명시 (Claude가 임의 값 못 만들도록)
    assert "5%" in p  # averaging-down 기본 하락폭
    assert "10%" in p  # take-profit 기본 익절폭
    # 운영자가 averaging-down 명시 거부할 수 있는 단서 표현
    assert "물타기 금지" in p or "추가 매수 안 함" in p


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
