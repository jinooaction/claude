"""Tests for `auto_invest.config.whitelist` (T019)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from auto_invest.config.enums import OrderType, Session
from auto_invest.config.whitelist import Whitelist


def test_default_order_types_and_sessions():
    w = Whitelist(symbols={"AAPL"}, accounts={"acct-1"})
    assert w.order_types == frozenset({OrderType.LIMIT})
    assert w.sessions == frozenset({Session.REGULAR})


def test_symbols_uppercased():
    w = Whitelist(symbols=["aapl", "msft"], accounts={"acct-1"})
    assert w.symbols == frozenset({"AAPL", "MSFT"})


def test_duplicate_symbols_after_normalization_rejected():
    with pytest.raises(ValidationError, match="duplicate symbols"):
        Whitelist(symbols=["AAPL", "aapl"], accounts={"acct-1"})


def test_symbol_with_illegal_characters_rejected():
    with pytest.raises(ValidationError, match="illegal characters"):
        Whitelist(symbols=["AAPL!"], accounts={"acct-1"})


def test_symbol_starting_with_digit_rejected():
    with pytest.raises(ValidationError, match="illegal characters"):
        Whitelist(symbols=["1AAPL"], accounts={"acct-1"})


def test_symbol_too_long_rejected():
    with pytest.raises(ValidationError, match="illegal characters"):
        Whitelist(symbols=["A" * 11], accounts={"acct-1"})


def test_non_string_symbol_rejected():
    with pytest.raises(ValidationError):
        Whitelist(symbols=[123], accounts={"acct-1"})  # type: ignore[list-item]


def test_whitelist_is_frozen():
    w = Whitelist(symbols={"AAPL"}, accounts={"acct-1"})
    with pytest.raises(ValidationError):
        w.symbols = frozenset({"MSFT"})  # type: ignore[misc]


def test_whitelist_extra_field_rejected():
    with pytest.raises(ValidationError):
        Whitelist(  # type: ignore[call-arg]
            symbols={"AAPL"},
            accounts={"acct-1"},
            unexpected="nope",
        )


def test_order_type_string_coerces_to_enum():
    w = Whitelist(
        symbols={"AAPL"},
        accounts={"acct-1"},
        order_types=frozenset({"LIMIT", "MARKET"}),
    )
    assert OrderType.LIMIT in w.order_types
    assert OrderType.MARKET in w.order_types


def test_session_string_coerces_to_enum():
    w = Whitelist(
        symbols={"AAPL"},
        accounts={"acct-1"},
        sessions=frozenset({"REGULAR", "EXTENDED"}),
    )
    assert Session.REGULAR in w.sessions
    assert Session.EXTENDED in w.sessions


def test_invalid_order_type_rejected():
    with pytest.raises(ValidationError):
        Whitelist(
            symbols={"AAPL"},
            accounts={"acct-1"},
            order_types=frozenset({"GTD"}),  # not in enum
        )


def test_empty_whitelist_allowed():
    # The loader rejects rules referencing symbols outside the whitelist,
    # but an empty whitelist itself is structurally valid.
    w = Whitelist()
    assert w.symbols == frozenset()
    assert w.accounts == frozenset()
