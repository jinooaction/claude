from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.performance.engine import FillRecord, compute_performance
from auto_invest.performance.measurement_contract import (
    MeasurementContractError,
    build_strategy_measurement_contract,
)
from auto_invest.performance.opening_positions import OpeningPosition

OPENING = (
    OpeningPosition("BHP", 1, Decimal("47.97")),
    OpeningPosition("ORANY", 28, Decimal("11.195")),
)
ROOT = Path(__file__).resolve().parents[2]


def _fill(symbol: str, side: str, qty: int, price: str) -> FillRecord:
    return FillRecord(
        symbol=symbol,
        side=side,
        qty=qty,
        price_usd=Decimal(price),
        ts_utc="2026-06-23T02:20:15.000Z",
        rule_id=f"rebalance:micro-gtaa:{symbol}",
    )


def test_contract_is_deterministic_and_rejects_strategy_overlap() -> None:
    first = build_strategy_measurement_contract(OPENING, strategy_universe=("SPY", "IEF", "GLD"))
    second = build_strategy_measurement_contract(
        tuple(reversed(OPENING)), strategy_universe=("GLD", "SPY", "IEF")
    )

    assert first.contract_id == second.contract_id
    assert first.excluded_symbols == ("BHP", "ORANY")
    assert first.contract_id.startswith("sha256:")

    with pytest.raises(MeasurementContractError, match="overlap"):
        build_strategy_measurement_contract(OPENING, strategy_universe=("ORANY", "SPY"))


def test_strategy_report_excludes_opening_holdings_and_their_liquidations() -> None:
    report = compute_performance(
        [_fill("BHP", "SELL", 1, "82.68"), _fill("SPYM", "BUY", 1, "90.00")],
        {"ORANY": Decimal("18.86"), "SPYM": Decimal("91.00")},
        mode="live",
        since=datetime(1970, 1, 1, tzinfo=UTC),
        until=datetime(2026, 8, 22, tzinfo=UTC),
        starting_capital=Decimal("293"),
        opening_positions=OPENING,
        excluded_symbols=frozenset({"BHP", "ORANY"}),
        measurement_contract_id="sha256:test",
    )

    assert report.fills_count == 1
    assert report.realized_pnl_usd == Decimal("0")
    assert report.unrealized_pnl_usd == Decimal("1")
    assert report.excluded_fills_count == 1
    assert report.excluded_realized_pnl_usd == Decimal("34.71")
    assert report.excluded_unrealized_pnl_usd == Decimal("214.620")
    assert report.measurement_contract_id == "sha256:test"
    assert [row.symbol for row in report.per_symbol] == ["SPYM"]


def test_production_measurement_paths_require_strategy_scope() -> None:
    observe = (ROOT / "deploy/observe-on-instance.sh").read_text()
    canary = (ROOT / "deploy/live-canary-on-instance.sh").read_text()

    measure = observe.split("live_canary_measure()", 1)[1].split("promote_readiness()", 1)[0]
    profit = canary.split("measure_profit()", 1)[1].split("main()", 1)[0]
    for command in (measure, profit):
        assert "--strategy-scope" in command
        assert "--opening-positions deploy/live-opening-positions.toml" in command
        assert "--portfolio deploy/canary-live-portfolio.toml" in command
    assert "resume-readiness" in measure
    assert "resume --confirm" not in measure
