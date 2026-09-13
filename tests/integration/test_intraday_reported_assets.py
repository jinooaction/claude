import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from auto_invest.broker.intraday_inputs import EXCHANGES, PREFIXES, SourceQuote
from auto_invest.execution.intraday import (
    IntradayExecutor,
    Observation,
    ReportedAssetValue,
    portfolio_exposure,
    validate_observation,
)
from auto_invest.execution.intraday_observation import ObservationError, build_observation
from auto_invest.execution.intraday_rehearsal import FINGERPRINT, rehearsal_session

NOW = datetime(2026, 9, 8, 15, tzinfo=UTC)


def value(*, quantity=3, amount="120", started=None, completed=None):
    return ReportedAssetValue(quantity, Decimal(amount), started or NOW - timedelta(seconds=1),
                              completed or NOW)


def observation():
    return Observation(NOW - timedelta(seconds=2), Decimal("600"), Decimal("920"),
        {"SPY": 2, "ORANY": 3}, {"SPY": Decimal("100")}, (), {"SPY": 2, "ORANY": 0},
        {"SPY": NOW}, reported_asset_values={"ORANY": value()})


def test_reported_valuation_is_counted_without_creating_an_execution_quote():
    view = observation()
    validate_observation(view, NOW, {"SPY"})
    assert portfolio_exposure(view) == Decimal("320")
    assert "ORANY" not in view.marks and "ORANY" not in view.mark_times


def test_explicit_zero_report_is_preserved_and_zero_quantity_needs_no_price():
    view = observation()
    view.reported_asset_values["ORANY"] = value(amount="0")
    view.positions["EMPTY"] = view.sellable_positions["EMPTY"] = 0
    validate_observation(view, NOW, {"SPY"})
    assert portfolio_exposure(view) == Decimal("200")


@pytest.mark.parametrize("fault", [
    "target", "strategy_symbol", "duplicate_quote", "missing", "quantity", "boolean_quantity",
    "negative", "nonfinite", "stale", "before_account", "reversed", "future", "naive",
])
def test_invalid_reported_values_cannot_weaken_the_observation_contract(fault):
    view, required = observation(), {"SPY"}
    if fault == "target":
        required.add("ORANY")
    elif fault == "strategy_symbol":
        view.reported_asset_values["SPY"] = value(quantity=2)
    elif fault == "duplicate_quote":
        view.marks["ORANY"] = Decimal("40")
        view.mark_times["ORANY"] = NOW
    elif fault == "missing":
        view.reported_asset_values.clear()
    else:
        changes = {
            "quantity": dict(quantity=4), "boolean_quantity": dict(quantity=True),
            "negative": dict(amount="-1"), "nonfinite": dict(amount="NaN"),
            "stale": dict(started=NOW - timedelta(seconds=31)),
            "before_account": dict(started=NOW - timedelta(seconds=3)),
            "reversed": dict(started=NOW, completed=NOW - timedelta(seconds=1)),
            "future": dict(completed=NOW + timedelta(seconds=1)),
            "naive": dict(started=NOW.replace(tzinfo=None)),
        }
        view.reported_asset_values["ORANY"] = value(**changes[fault])
    with pytest.raises(ValueError):
        validate_observation(view, NOW, required)


def account():
    return dict(currency="USD", pagination_complete=True, full_account_scope_verified=True,
        cash_aggregation_verified=True, nav_verified=False, unverified_assets={},
        valuation_basis="net_cash_and_reported_equities", net_cash="600", execution_cash="600",
        observation_started_at=(NOW - timedelta(seconds=2)).isoformat(),
        observation_completed_at=NOW.isoformat(), open_orders=[],
        positions={"SPY": dict(quantity=2, sellable_quantity=2),
                   "ORANY": dict(quantity=3, sellable_quantity=0)},
        reported_asset_values={"ORANY": dict(quantity=3, amount_usd="120",
            observation_started_at=(NOW - timedelta(seconds=1)).isoformat(),
            observation_completed_at=NOW.isoformat())})


def quotes():
    return {s: SourceQuote(s, e, PREFIXES[e] + s, Decimal("100"), None, None,
        NOW, NOW, "20260909", "000000", "20260908", "110000", "1")
        for s, e in EXCHANGES.items()}


def test_verified_cash_and_reported_assets_reach_observation_nav():
    view = build_observation(account(), quotes(), now=NOW)
    assert view.nav == Decimal("920") and view.cash == Decimal("600")
    assert portfolio_exposure(view) == Decimal("320")
    assert "ORANY" not in view.marks and "ORANY" not in view.mark_times
    assert view.reported_asset_values["ORANY"].quantity == 3


@pytest.mark.parametrize("field", ["full_account_scope_verified", "cash_aggregation_verified"])
def test_reported_assets_do_not_approve_missing_cash_or_account_scope(field):
    raw = account()
    raw[field] = False
    with pytest.raises(ObservationError, match="UNVERIFIED"):
        build_observation(raw, quotes(), now=NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize("reported_amount,expected", [("100", "SUBMITTED"),
                                                       ("7990", "DENIED")])
async def test_actual_engine_counts_reported_assets_in_global_limit_and_never_trades_them(
    tmp_path, reported_amount, expected,
):
    async with rehearsal_session(tmp_path / "book.db") as book:
        async def observe():
            current = await book.observe()
            return replace(current, nav=current.nav + Decimal(reported_amount),
                positions=dict(current.positions, ORANY=3),
                sellable_positions=dict(current.sellable_positions, ORANY=0),
                reported_asset_values={"ORANY": ReportedAssetValue(
                    3, Decimal(reported_amount), book.now, book.now)})

        engine = IntradayExecutor(book.engine.router, fingerprint=FINGERPRINT, observe=observe,
            external_holdings={"ORANY": 3}, capital_limit=book.initial_cash,
            authority_guard=lambda: None, now=lambda: book.now)
        book.engine = engine
        result = await engine.step(book.decision(1))
        assert result["actions"][0]["kind"] == expected, result
        if expected == "DENIED":
            assert result["actions"][0]["reason"] == "CASH_OR_EXPOSURE"
            assert book.requests == []
        else:
            assert all(body["PDNO"] == "SPY" for _, body in book.requests)
        assert engine._owned().get("ORANY", 0) == 0
        evidence = json.loads(book.conn.execute(
            "SELECT payload FROM intraday_execution_events WHERE kind='REPORTED_VALUATION_USED'"
        ).fetchone()[0])
        reported = evidence["reported_assets"]["ORANY"]
        assert reported == dict(quantity=3, amount_usd=reported_amount,
            observation_started_at=book.now.isoformat(),
            observation_completed_at=book.now.isoformat())
        assert evidence["global_exposure"] == reported_amount


def test_reported_valuation_never_repairs_a_stale_order_quote():
    view = observation()
    view.mark_times["SPY"] = NOW - timedelta(seconds=31)
    with pytest.raises(ValueError, match="STALE_EXECUTION_MARK"):
        validate_observation(view, NOW, {"SPY"})
