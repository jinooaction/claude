import json
import socket
from decimal import Decimal

import pytest

from auto_invest.execution.intraday_rehearsal import rehearsal_session
from auto_invest.execution.preparation import CONFIRMED, confirmed_budget, preflight


def test_confirmed_values_are_preparation_only():
    budget = confirmed_budget()
    assert budget["capital_limit_usd"] == "600.00"
    assert budget["daily_stop_trigger_usd"] == "12.00"
    assert budget["orders_enabled"] is False
    assert budget["approval_scope"] == "preparation_parameters"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("capital_limit_usd", "601.00"),
        ("daily_stop_trigger_usd", "13.00"),
        ("orders_enabled", True),
        ("approval_scope", "live"),
        ("schema_version", True),
        ("order_limit_usd", "121.00"),
        ("approved", True),
    ],
)
def test_reject_budget_change_or_activation(tmp_path, key, value):
    budget = dict(CONFIRMED)
    budget[key] = value
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(budget))
    with pytest.raises(ValueError):
        confirmed_budget(path)


@pytest.mark.asyncio
async def test_preflight_runs_real_engine_under_confirmed_cap_without_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = await preflight()
    assert result["budget_parameters_confirmed"] is True
    assert result["capital_change_usd"] == "0.00"
    assert result["live_eligible"] is False
    assert result["rehearsal"]["simulated_capital_limit_usd"] == "600.00"
    assert result["rehearsal"]["partial_cancel_late_fill_liquidation"] == "PASS"
    assert result["rehearsal"]["final_owned_positions"] == {}
    assert result["rehearsal"]["duplicate_broker_requests"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("mark", "halted"), [("17.66", False), ("17.65", True)])
async def test_actual_engine_daily_twelve_dollar_stop(tmp_path, mark, halted):
    async with rehearsal_session(
        tmp_path / "test.db", capital_limit=Decimal("600"), mark=Decimal("20")
    ) as book:
        first = await book.engine.step(book.decision(5))
        assert first["actions"][0]["kind"] == "SUBMITTED"
        book.fill("1", 5, "20")
        await book.engine.step(book.decision(5))
        # Five shares: $11.75 price loss + $0.25 estimated entry fee = $12.
        book.mark = Decimal(mark)
        await book.engine.step(book.decision(5))
        rows = book.conn.execute(
            "SELECT * FROM intraday_execution_events WHERE kind='LOSS_HALT'"
        ).fetchall()
        assert bool(rows) is halted
        if halted:
            assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"


@pytest.mark.asyncio
async def test_actual_engine_rejects_over_120_dollars(tmp_path):
    async with rehearsal_session(
        tmp_path / "test.db", capital_limit=Decimal("600"), mark=Decimal("20")
    ) as book:
        await book.engine.step(book.decision(7))
        assert book.requests == []
