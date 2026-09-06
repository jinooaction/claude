"""Capital review must agree with execution arithmetic without authorizing it."""

import copy
import json
import os
import runpy
import socket
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_capital_review import SYMBOLS, load_prices, review

PRICE_FILE = Path("specs/182-intraday-kis-execution/capital-review/reference-prices.json")
NOW = datetime(2026, 9, 8, 14, 15, tzinfo=UTC)


@pytest.fixture
def prices():
    return load_prices(PRICE_FILE)


@pytest.mark.parametrize(
    ("capital", "quantity"),
    [("0", 0), ("100", 0), ("514.06", 0), ("514.07", 1), ("600", 1)],
)
def test_whole_share_boundary_and_no_activation(prices, capital, quantity):
    result = review(prices, capital, now=NOW)
    assert result["symbols"][3]["hypothetical_shares"] == quantity
    assert result["symbols"][3]["minimum_capital_for_one_reference_share_usd"] == "514.07"
    assert result["capital_change_usd"] == "0.00"
    assert result["orders_submitted"] == 0
    assert result["live_eligible"] is False
    assert result["approval_recorded"] is False
    assert result["account_nav_verified"] is False
    assert result["execution_quote_verified"] is False
    assert result["stop_is_loss_guarantee"] is False


@pytest.mark.parametrize("capital", ["0", "100", "514.06", "514.07", "600", "4816.57", "10000"])
def test_matches_actual_signal_compiler(prices, capital, monkeypatch):
    from auto_invest.analytics.intraday_paper_challenger import (
        build_candidate_registry,
        load_preregistration,
    )
    from auto_invest.execution import intraday_signals
    from auto_invest.market_data.intraday import SYMBOLS as ENGINE_SYMBOLS
    from auto_invest.market_data.intraday import iso

    assert tuple(ENGINE_SYMBOLS) == SYMBOLS
    monkeypatch.setattr(intraday_signals, "_entry_signal", lambda *_: True)
    candidate = build_candidate_registry(
        load_preregistration(
            Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
        )
    )[0]
    opening = NOW.replace(hour=13, minute=30)
    bars = [
        dict(
            symbol=symbol,
            timestamp_utc=iso(opening + timedelta(minutes=5 * index)),
            open=float(prices["prices"][symbol]),
            high=float(prices["prices"][symbol]),
            low=float(prices["prices"][symbol]),
            close=float(prices["prices"][symbol]),
            volume=100000,
        )
        for index in range(9)
        for symbol in SYMBOLS
    ]
    decision = intraday_signals.compile_decision(
        candidate,
        provider="kis-nasdaq-partial-unadjusted",
        bars=bars,
        now=NOW,
        owned={},
        entry_times={},
        entered_symbols=set(),
        capital=Decimal(capital),
        cash=Decimal(capital),
    )
    result = review(prices, capital, now=NOW)
    assert decision.targets == {r["symbol"]: r["hypothetical_shares"] for r in result["symbols"]}
    for row in result["symbols"]:
        if row["hypothetical_shares"]:
            assert decision.limits[row["symbol"]] == Decimal(row["illustrative_buy_limit_usd"])
    assert Decimal(result["hypothetical_remaining_cash_usd"]) >= 0


@pytest.mark.parametrize("amount", [True, 600, "NaN", "Infinity", "-1", "1e3", "0.001", "1,000"])
def test_reject_invalid_budget(prices, amount):
    with pytest.raises(ValueError):
        review(prices, amount, now=NOW)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", True),
        ("currency", "KRW"),
        ("prices", {"TLT": "82.21"}),
        ("prices", None),
        ("quote_as_of", "2026-09-05"),
        ("quote_as_of", "2099-01-01T00:00:00Z"),
        ("quote_as_of", None),
        ("quote_source", ""),
        ("approved", True),
        ("live_eligible", True),
    ],
)
def test_reject_bad_metadata_and_authority_fields(prices, key, value):
    prices[key] = value
    with pytest.raises(ValueError):
        review(prices, "600", now=NOW)


@pytest.mark.parametrize("value", ["0", "-1", "NaN", 82.21, True, "0.001"])
def test_reject_bad_price(prices, value):
    prices["prices"]["TLT"] = value
    with pytest.raises(ValueError):
        review(prices, "600", now=NOW)


def test_old_prices_remain_explicitly_reference_only(prices):
    original = copy.deepcopy(prices)
    prices["quote_as_of"] = "2020-01-01T00:00:00Z"
    result = review(prices, "600", now=NOW)
    assert result["quote_age_seconds"] > 365 * 24 * 3600
    assert result["execution_quote_verified"] is False
    assert result["live_eligible"] is False
    assert original["prices"] == prices["prices"]


def test_duplicate_fields_and_oversized_input_rejected(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text('{"currency":"USD","currency":"KRW"}')
    with pytest.raises(ValueError, match="DUPLICATE_INPUT_FIELD"):
        load_prices(path)
    path.write_text(" " * 16_385)
    with pytest.raises(ValueError, match="INPUT_TOO_LARGE"):
        load_prices(path)


def test_cli_reads_no_account_network_or_secret(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("Capital review accessed account, network or environment")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(
        sys, "argv", ["review", "--prices", str(PRICE_FILE), "--capital-usd", "600"]
    )
    before = PRICE_FILE.read_bytes()
    with pytest.raises(SystemExit) as result:
        runpy.run_path("scripts/intraday_capital_review.py", run_name="__main__")
    assert result.value.code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "capital_review_only"
    assert output["live_eligible"] is False
    assert PRICE_FILE.read_bytes() == before


@pytest.mark.parametrize("extra", ["--live", "--approve"])
def test_cli_has_no_activation_switch(extra, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["review", "--prices", str(PRICE_FILE), "--capital-usd", "600", extra]
    )
    with pytest.raises(SystemExit) as result:
        runpy.run_path("scripts/intraday_capital_review.py", run_name="__main__")
    assert result.value.code == 2
    assert not capsys.readouterr().out
