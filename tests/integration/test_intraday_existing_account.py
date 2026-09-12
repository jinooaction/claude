"""Existing KIS account ownership contracts; transport is always MockTransport."""

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from auto_invest.execution.intraday import IntradayExecutor
from auto_invest.execution.intraday_rehearsal import FINGERPRINT, rehearsal_session
from auto_invest.reconciliation.external_holdings import load_external_holdings


def existing_account(book, baseline, actual=None, *, authorized=True):
    actual = dict(baseline) if actual is None else actual

    async def observe():
        view = await book.observe()
        positions, marks, stamps = dict(view.positions), dict(view.marks), dict(view.mark_times)
        for symbol, qty in actual.items():
            positions[symbol] = positions.get(symbol, 0) + qty
            marks[symbol], stamps[symbol] = book.mark, book.now
        return replace(
            view,
            positions=positions,
            sellable_positions=dict(positions),
            marks=marks,
            mark_times=stamps,
            nav=view.nav + sum(actual.values()) * book.mark,
        )

    engine = IntradayExecutor(
        book.engine.router,
        fingerprint=FINGERPRINT,
        observe=observe,
        external_holdings=baseline,
        capital_limit=book.initial_cash,
        authority_guard=(lambda: None) if authorized else None,
        now=lambda: book.now,
    )
    book.engine = engine
    return engine


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["target", "closing", "halt"])
async def test_existing_shares_are_never_adopted_or_liquidated(tmp_path, trigger):
    async with rehearsal_session(tmp_path / "test.db") as book:
        engine = existing_account(book, {"SPY": 4, "BHP": 3})
        if trigger == "closing":
            book.now = book.now.replace(hour=19, minute=45)
        if trigger == "halt":
            engine.router.halt_path.touch()
        result = await engine.step(book.decision(0))
        assert result["status"] in {"PROCESSED", "EXIT_ONLY"}, result
        assert result["actions"] == []
        assert engine._owned() == {}
        assert book.requests == []
        assert book.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0] == 0
        payload = json.loads(
            book.conn.execute("SELECT payload FROM intraday_execution_claims").fetchone()[0]
        )
        assert payload["profit"] == "0"
        assert payload["external_holdings_digest"] == engine.external_holdings_digest


@pytest.mark.asyncio
async def test_partial_fill_cancel_late_fill_restart_closes_only_intraday_shares(tmp_path):
    baseline_path = tmp_path / "external-holdings.toml"
    baseline_path.write_text('[[holdings]]\nsymbol = "spy"\nqty = 4\n')
    baseline = load_external_holdings(baseline_path)
    database = tmp_path / "shared.db"
    async with rehearsal_session(database) as book:
        engine = existing_account(book, baseline)
        assert (await engine.step(book.decision(5)))["actions"][0]["kind"] == "SUBMITTED"
        book.fill("1", 2, "99")
        assert (await engine.step(book.decision(5)))["status"] == "WAIT_BROKER"
        cancel = await engine.step(book.decision(0))
        assert cancel["actions"] == [dict(kind="CANCEL_REQUEST", result="ACKNOWLEDGED")]
        book.fill("1", 3, "99.30", terminal=True)
        # Preserve broker state but actually close and reopen the local database.
        orders, requests = book.orders, list(book.requests)
    async with rehearsal_session(database) as book:
        book.orders, book.requests = orders, requests
        book.now = book.now.replace(hour=19, minute=45)
        engine = existing_account(book, load_external_holdings(baseline_path))
        result = await engine.step(book.decision(5))
        assert result["status"] == "EXIT_ONLY", result
        assert result["actions"][0]["kind"] == "SUBMITTED"
        assert book.orders["2"]["qty"] == 3
        assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"
        book.fill("2", 3, "100")
        done = await engine.step(book.decision(0))
        assert done["actions"] == []
        assert engine._owned() == {}
        assert (await engine.observe()).positions == {"SPY": 4}
        before = len(book.requests)
        assert (await engine.step(book.decision(0)))["actions"] == []
        assert len(book.requests) == before == 3
        events = book.conn.execute(
            "SELECT payload FROM intraday_execution_events WHERE kind='ROUTER_RESULT'"
        ).fetchall()
        assert len(events) == 2
        assert all(
            json.loads(row[0])["external_holdings_digest"] == engine.external_holdings_digest
            for row in events
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("actual", [{"SPY": 3}, {"SPY": 5}, {"SPY": 4, "BHP": 1}, {}])
async def test_undeclared_holdings_changes_still_halt_before_order(tmp_path, actual):
    async with rehearsal_session(tmp_path / "test.db") as book:
        engine = existing_account(book, {"SPY": 4}, actual)
        result = await engine.step(book.decision(5))
        assert result["reason"] == "POSITION_RECONCILIATION_MISMATCH"
        assert book.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("baseline", [{"SPY": 19}, {"BHP": 79}])
async def test_account_exposure_includes_existing_holdings(tmp_path, baseline):
    async with rehearsal_session(tmp_path / "test.db") as book:
        engine = existing_account(book, baseline)
        result = await engine.step(book.decision(5))
        assert result["actions"] == [dict(kind="DENIED", symbol="SPY", reason="CASH_OR_EXPOSURE")]
        assert book.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "baseline",
    [{"SPY": 0}, {"SPY": -1}, {"SPY": True}, {"SPY": 1.5}, {"spy": 4}, {"": 4}, {1: 4}, []],
)
async def test_invalid_baseline_rejected_before_router_or_database_changes(tmp_path, baseline):
    async with rehearsal_session(tmp_path / "test.db") as book:
        guard = book.engine.router.live_order_guard
        before = book.conn.total_changes
        with pytest.raises(ValueError, match="^INVALID_EXTERNAL_HOLDINGS$"):
            existing_account(book, baseline)
        assert book.engine.router.live_order_guard is guard
        assert book.conn.total_changes == before
        assert book.requests == []


@pytest.mark.asyncio
async def test_baseline_copy_cannot_change_from_caller_mutation(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        baseline = {"SPY": 4}
        engine = existing_account(book, baseline)
        digest = engine.external_holdings_digest
        baseline["SPY"] = 100
        assert engine.external_holdings == {"SPY": 4}
        assert engine.external_holdings_digest == digest
        with pytest.raises(TypeError):
            engine.external_holdings["SPY"] = 100
        assert (await engine.step(book.decision(5)))["actions"][0]["kind"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_default_empty_baseline_does_not_silently_adopt_existing_account(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        engine = existing_account(book, {}, {"SPY": 4})
        result = await engine.step(book.decision(5))
        assert result["reason"] == "POSITION_RECONCILIATION_MISMATCH"
        assert book.requests == []


@pytest.mark.asyncio
async def test_baseline_does_not_grant_execution_authority(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        engine = existing_account(book, {"SPY": 4}, authorized=False)
        result = await engine.step(book.decision(5))
        assert result == dict(status="DENIED", reason="INTRADAY_AUTHORIZATION_REQUIRED", actions=[])
        assert book.requests == []


@pytest.mark.asyncio
async def test_baseline_price_changes_are_not_intraday_profit(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        engine = existing_account(book, {"SPY": 4})
        assert (await engine.step(book.decision(0)))["status"] == "PROCESSED"
        book.now = book.now.replace(day=9)
        book.mark = Decimal("200")
        assert (await engine.step(book.decision(0)))["status"] == "PROCESSED"
        rows = book.conn.execute("SELECT payload FROM intraday_execution_claims").fetchall()
        assert len(rows) == 2
        assert [json.loads(row[0])["profit"] for row in rows] == ["0", "0"]
        assert [json.loads(row[0])["nav"] for row in rows] == ["10400", "10800"]


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [False, True])
async def test_existing_nontradable_asset_still_needs_a_fresh_valuation(tmp_path, missing):
    async with rehearsal_session(tmp_path / "test.db") as book:
        engine = existing_account(book, {"BHP": 4})
        observe = engine.observe

        async def incomplete():
            view = await observe()
            if missing:
                return replace(
                    view,
                    marks={s: v for s, v in view.marks.items() if s != "BHP"},
                    mark_times={s: v for s, v in view.mark_times.items() if s != "BHP"},
                )
            return replace(
                view, mark_times={**view.mark_times, "BHP": book.now - timedelta(seconds=31)}
            )

        engine.observe = incomplete
        result = await engine.step(book.decision(5))
        assert result["reason"] == ("MISSING_MARKS" if missing else "STALE_EXECUTION_MARK")
        assert book.requests == []


@pytest.mark.asyncio
async def test_baseline_does_not_hide_whole_account_loss_or_raise_confirmed_budget(tmp_path):
    async with rehearsal_session(tmp_path / "test.db", capital_limit=Decimal("600")) as book:
        engine = existing_account(book, {"SPY": 4})
        result = await engine.step(book.decision(1))
        assert result["actions"] == [dict(kind="DENIED", symbol="SPY", reason="CASH_OR_EXPOSURE")]
        assert engine.capital_limit == Decimal("600")
        book.mark = Decimal("90")  # Existing holdings lose $40 of the $1000 account NAV.
        result = await engine.step(book.decision(1))
        assert result["status"] == "EXIT_ONLY"
        assert result["actions"] == []
        assert book.conn.execute(
            "SELECT COUNT(*) FROM intraday_execution_events WHERE kind='LOSS_HALT'"
        ).fetchone()[0] == 1
        assert book.requests == []
