"""Spec 010 T007 — 생성된 룰 TOML 정적 검증.

정상 통과 + 5가지 거부 시나리오 (parse·whitelist·cap·자본 부족·해외 종목).
"""

from __future__ import annotations

from decimal import Decimal

from auto_invest.design.validator import validate_generated_rules

_GOOD_TOML = """
[caps]
per_trade_pct = 5
per_symbol_pct = 20
global_exposure_pct = 80
canary_capital_pct = 5
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3

[whitelist]
symbols = ["VOO", "QQQ"]
accounts = ["1234567801"]
order_types = ["MARKET", "LIMIT"]
sessions = ["REGULAR"]

[[rules]]
id = "rule_voo_buy"
symbol = "VOO"
stage = "CANARY"
priority = 10
enabled = true

[rules.trigger]
kind = "price"
direction = "<="
threshold = 999999
cooldown_seconds = 60

[rules.action]
side = "BUY"
order_type = "MARKET"
qty = 1
limit_price = "0"
"""


def test_valid_toml_passes():
    result = validate_generated_rules(
        _GOOD_TOML,
        intent_capital_usd=Decimal("100"),
        kis_balance_usd=Decimal("102.45"),
    )
    assert result.ok is True
    assert result.reason is None


def test_balance_too_low():
    result = validate_generated_rules(
        _GOOD_TOML,
        intent_capital_usd=Decimal("5"),
        kis_balance_usd=Decimal("5"),
    )
    assert result.ok is False
    assert result.reason == "insufficient_balance"


def test_intent_capital_exceeds_balance():
    result = validate_generated_rules(
        _GOOD_TOML,
        intent_capital_usd=Decimal("200"),
        kis_balance_usd=Decimal("102.45"),
    )
    assert result.ok is False
    assert result.reason == "insufficient_balance"


def test_invalid_toml_parse_error():
    result = validate_generated_rules(
        "[caps\nbroken",
        intent_capital_usd=Decimal("100"),
        kis_balance_usd=Decimal("102.45"),
    )
    assert result.ok is False
    assert result.reason == "parse_error"


def test_rule_symbol_not_in_whitelist():
    """rules에 등장하지만 whitelist에 없는 종목."""
    bad = _GOOD_TOML.replace('symbols = ["VOO", "QQQ"]', 'symbols = ["VOO"]')
    bad = bad.replace('symbol = "VOO"', 'symbol = "TSLA"')
    result = validate_generated_rules(
        bad, intent_capital_usd=Decimal("100"), kis_balance_usd=Decimal("102.45"),
    )
    assert result.ok is False
    assert result.reason == "whitelist_violation"


def test_per_trade_cap_too_high():
    bad = _GOOD_TOML.replace("per_trade_pct = 5", "per_trade_pct = 50")
    result = validate_generated_rules(
        bad, intent_capital_usd=Decimal("100"), kis_balance_usd=Decimal("102.45"),
    )
    assert result.ok is False
    assert result.reason == "cap_violation"


def test_foreign_symbol_rejected():
    """비미국·6자 이상·숫자 포함 종목은 형식 휴리스틱으로 거부."""
    bad = _GOOD_TOML.replace(
        'symbols = ["VOO", "QQQ"]', 'symbols = ["VOO", "BTC-USD"]',
    )
    bad = bad.replace('symbol = "VOO"', 'symbol = "BTC-USD"')
    result = validate_generated_rules(
        bad, intent_capital_usd=Decimal("100"), kis_balance_usd=Decimal("102.45"),
    )
    assert result.ok is False
    assert result.reason == "whitelist_violation"


def test_long_symbol_rejected():
    """6자 이상 ticker는 형식 휴리스틱으로 거부."""
    bad = _GOOD_TOML.replace(
        'symbols = ["VOO", "QQQ"]', 'symbols = ["BERKSHIRE"]',
    )
    bad = bad.replace('symbol = "VOO"', 'symbol = "BERKSHIRE"')
    result = validate_generated_rules(
        bad, intent_capital_usd=Decimal("100"), kis_balance_usd=Decimal("102.45"),
    )
    assert result.ok is False
    assert result.reason == "whitelist_violation"


def test_global_exposure_above_100():
    bad = _GOOD_TOML.replace("global_exposure_pct = 80", "global_exposure_pct = 150")
    result = validate_generated_rules(
        bad, intent_capital_usd=Decimal("100"), kis_balance_usd=Decimal("102.45"),
    )
    assert result.ok is False
    assert result.reason == "cap_violation"
