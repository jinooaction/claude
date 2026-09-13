import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from auto_invest.broker.intraday_inputs import BuyingPower
from auto_invest.execution.intraday import BudgetObservation, IntradayExecutor
from auto_invest.execution.intraday_budget import budget_usage
from auto_invest.execution.intraday_rehearsal import FINGERPRINT, rehearsal_session


def budget_engine(book, *, transform=lambda value: value, external=None):
    async def observe():
        old = await book.observe()
        return BudgetObservation(old.observed_at, old.positions, old.marks, old.open_order_ids,
                                 old.sellable_positions, old.mark_times)

    async def power(*, symbol, limit_price):
        return transform(BuyingPower(symbol, "AMEX", limit_price, Decimal("999999"),
                                     99999, book.now, book.now))

    return IntradayExecutor(book.engine.router, fingerprint=FINGERPRINT, observe=observe,
                            authority_guard=lambda: None, capital_limit=Decimal("600"),
                            now=lambda: book.now, budget_mode=True, order_power=power,
                            external_holdings=external)


@pytest.mark.asyncio
async def test_budget_path_has_no_cash_or_nav_and_drain_survives_restart(tmp_path):
    async with rehearsal_session(tmp_path / "budget.db", mark=Decimal("20")) as book:
        engine = budget_engine(book)
        view = await engine.observe()
        assert not hasattr(view, "nav") and not hasattr(view, "cash")
        result = await engine.step(book.decision(5))
        assert result["actions"] == [{"kind": "SUBMITTED", "symbol": "SPY"}]
        assert budget_usage(book.conn, Decimal("600")).available == Decimal("499.7")
        book.fill("1", 2, "20", terminal=True)
        restarted = budget_engine(book)
        restarted.request_drain()
        result = await restarted.manage()
        assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"
        assert book.orders["2"]["qty"] == 2
        book.fill("2", 2, "19.99", terminal=True)
        assert (await restarted.manage())["status"] == "STOPPED"
        assert budget_usage(book.conn, Decimal("600")).available < Decimal("560")
        day = book.conn.execute("SELECT payload FROM intraday_execution_claims "
                                "WHERE id=?", (engine.prefix + str(book.now.date()),)).fetchone()
        assert json.loads(day[0])["nav"] is None
        assert json.loads(day[0])["funding_basis"] == "FIXED_BUDGET"


@pytest.mark.asyncio
@pytest.mark.parametrize("change,reason", [
    (dict(symbol="QQQ"), "BUDGET_BUYING_POWER_INVALID"),
    (dict(limit_price=Decimal("19")), "BUDGET_BUYING_POWER_INVALID"),
    (dict(foreign_orderable_qty=0), "BUDGET_BUYING_POWER_INSUFFICIENT"),
    (dict(foreign_orderable_amount=Decimal("1")), "BUDGET_BUYING_POWER_INSUFFICIENT"),
])
async def test_buying_power_must_match_this_order(tmp_path, change, reason):
    async with rehearsal_session(tmp_path / "budget.db", mark=Decimal("20")) as book:
        engine = budget_engine(book, transform=lambda value: replace(value, **change))
        assert (await engine.step(book.decision(5)))["reason"] == reason
        assert not book.orders


@pytest.mark.asyncio
async def test_budget_order_limit_survives_huge_broker_buying_power(tmp_path):
    async with rehearsal_session(tmp_path / "budget.db", mark=Decimal("20")) as book:
        engine = budget_engine(book)
        assert (await engine.step(book.decision(7)))["actions"] == [
            {"kind": "DENIED", "symbol": "SPY", "reason": "CASH_OR_EXPOSURE"}]
        assert not book.orders


@pytest.mark.asyncio
async def test_expired_buying_power_is_rejected(tmp_path):
    async with rehearsal_session(tmp_path / "budget.db", mark=Decimal("20")) as book:
        engine = budget_engine(book, transform=lambda value: replace(
            value, started_at=book.now - timedelta(seconds=31)))
        assert (await engine.step(book.decision(1)))["reason"] == "BUDGET_BUYING_POWER_INVALID"
        assert not book.orders


@pytest.mark.asyncio
async def test_default_account_mode_cannot_silently_accept_budget_view(tmp_path):
    async with rehearsal_session(tmp_path / "budget.db", mark=Decimal("20")) as book:
        provider = budget_engine(book).observe
        book.engine.observe = provider
        result = await book.engine.step(book.decision(1))
        assert result["reason"] == "ACCOUNT_FUNDING_MODE_MISMATCH"
        assert not book.orders


@pytest.mark.asyncio
async def test_external_holdings_still_count_against_global_budget_cap(tmp_path):
    async with rehearsal_session(tmp_path / "budget.db", mark=Decimal("20")) as book:
        engine = budget_engine(book, external={"QQQ": 20})
        original = engine.observe

        async def observe():
            value = await original()
            return replace(value, positions={"QQQ": 20}, sellable_positions={"QQQ": 20})

        engine.observe = observe
        result = await engine.step(book.decision(5))
        assert result["actions"] == [
            {"kind": "DENIED", "symbol": "SPY", "reason": "CASH_OR_EXPOSURE"}]
        assert not book.orders


@pytest.mark.asyncio
async def test_last_moment_guard_does_not_reuse_stale_buying_power(tmp_path):
    async with rehearsal_session(tmp_path / "budget.db", mark=Decimal("20")) as book:
        engine = budget_engine(book)
        original = engine.router.submit_order

        async def submit(**kwargs):
            power, clock = engine._last_power
            engine._last_power = power, clock - 31
            return await original(**kwargs)

        engine.router.submit_order = submit
        result = await engine.step(book.decision(5))
        assert not book.orders
        assert result["actions"][0]["kind"] == "REJECTED_BY_GATE"


@pytest.mark.asyncio
async def test_cost_collection_does_not_delay_management_or_operator_stop(tmp_path):
    async with rehearsal_session(tmp_path / "budget.db", mark=Decimal("20")) as book:
        engine = budget_engine(book)
        calls = []

        async def unavailable():
            calls.append("called")
            raise RuntimeError("private network failure")

        engine.refresh_budget = unavailable
        await engine.manage()
        assert calls == []
        await engine.step(book.decision(2))
        assert calls == ["called"]
        book.fill("1", 2, "20", terminal=True)
        engine.request_drain()
        await engine.manage()
        assert calls == ["called"]
        assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"
