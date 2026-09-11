"""Real strategy exits must survive an unfilled order and ledger reopening."""

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.execution.intraday import Decision, IntradayExecutor
from auto_invest.execution.intraday_rehearsal import rehearsal_session
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import CALENDAR, SYMBOLS, iso

PROVIDER = "kis-nasdaq-partial-unadjusted"
OPEN = CALENDAR.session_open("2026-09-08").to_pydatetime()
PREREG = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")


def setup_engine(book):
    candidate = build_candidate_registry(load_preregistration(PREREG))[0]
    book.engine = IntradayExecutor(
        book.engine.router, fingerprint=execution_fingerprint(candidate, PROVIDER),
        observe=book.observe, authority_guard=lambda: None, capital_limit=book.initial_cash,
        now=lambda: book.now,
    )
    return candidate


def bars(count, *, last=100):
    return [dict(symbol=s, timestamp_utc=iso(OPEN + timedelta(minutes=5 * n)),
                 open=last if n == count - 1 else 100, high=101, low=97,
                 close=last if n == count - 1 else 100, volume=100000)
            for n in range(count) for s in SYMBOLS]


def buy(book, quantity):
    return Decision(book.engine.fingerprint, book.now, {"SPY": quantity},
                    {"SPY": Decimal("100")})


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [0, 2])
@pytest.mark.parametrize("resume", ["bars", "manage"])
@pytest.mark.parametrize("interruption", [None, "stale_quote", "unsellable", "authority"])
async def test_cancelled_strategy_exit_keeps_original_price_after_reopen(
    tmp_path, partial, resume, interruption,
):
    database = tmp_path / "strategy-exit.db"
    async with rehearsal_session(database) as book:
        candidate = setup_engine(book)
        book.now = OPEN + timedelta(minutes=5)
        assert (await book.engine.step(buy(book, 5)))["actions"][0]["kind"] == "SUBMITTED"
        book.fill("1", 5, "100")
        await book.engine.manage()
        book.now = OPEN + timedelta(minutes=45)
        result = await book.engine.on_bars(candidate, provider=PROVIDER, bars=bars(9))
        assert result["actions"][0]["kind"] == "SUBMITTED", result
        assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"
        limit = book.orders["2"]["ft_ord_unpr3"]
        book.now += timedelta(minutes=5)
        assert (await book.engine.manage())["actions"][0]["kind"] == "CANCEL_REQUEST"
        book.fill("2", partial, limit if partial else "0", terminal=True)
        original_orders = book.orders
    async with rehearsal_session(database) as book:
        book.orders = original_orders
        candidate = setup_engine(book)
        book.now = OPEN + timedelta(minutes=50)
        book.mark = Decimal("98")

        async def resume_exit():
            if resume == "manage":
                return await book.engine.manage()
            return await book.engine.on_bars(candidate, provider=PROVIDER, bars=bars(10, last=98))

        async def restricted():
            view = await book.observe()
            if interruption == "stale_quote":
                return replace(view, mark_times={
                    s: book.now - timedelta(seconds=31) for s in view.marks
                })
            return replace(view, sellable_positions={"SPY": 0})

        if interruption is not None:
            if interruption == "authority":
                book.engine.guard = lambda: "TEST_AUTHORITY_REFUSED"
            else:
                book.engine.observe = restricted
            refused = await resume_exit()
            assert len(book.orders) == 2, refused
            if interruption == "unsellable":
                assert refused["actions"][0]["reason"] == "SELLABLE_QUANTITY_INSUFFICIENT"
            else:
                assert refused["status"] in {"HALTED", "DENIED"}
            book.engine.guard = lambda: None
            book.engine.observe = book.observe
        result = await resume_exit()
        assert len(book.orders) == 3, result
        assert book.orders["3"]["sll_buy_dvsn_cd"] == "01"
        assert book.orders["3"]["qty"] == 5 - partial
        assert book.orders["3"]["ft_ord_unpr3"] == limit
        intents = [json.loads(row[0]) for row in book.conn.execute(
            "SELECT payload FROM intraday_execution_claims WHERE fingerprint=?",
            (book.engine.fingerprint,),
        )]
        exits = [intent for intent in intents if intent.get("side") == "SELL"]
        assert len(exits) == 2
        assert all(intent["decision_kind"] == "STRATEGY_EXIT" for intent in exits)
        assert {intent["signal_bar_end"] for intent in exits} == {
            (OPEN + timedelta(minutes=45)).isoformat(),
        }
        again = await book.engine.on_bars(candidate, provider=PROVIDER, bars=bars(10, last=98))
        assert again["status"] == "WAIT_BROKER" and len(book.orders) == 3
        book.fill("3", 5 - partial, limit)
        await book.engine.manage()
        assert book.engine._owned() == {}
        # A later position is a new holding cycle, not the old liquidation.
        book.now = OPEN + timedelta(minutes=55)
        book.mark = Decimal("100")
        assert (await book.engine.step(buy(book, 3)))["actions"][0]["kind"] == "SUBMITTED"
        book.fill("4", 3, "100")
        result = await book.engine.on_bars(candidate, provider=PROVIDER, bars=bars(11))
        assert result["status"] == "PROCESSED" and len(book.orders) == 4
        assert book.engine._owned() == {"SPY": 3}
        assert book.conn.execute(
            "SELECT COUNT(*) FROM intraday_execution_events WHERE kind='STRATEGY_EXIT_REQUESTED'"
        ).fetchone()[0] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["price", "cycle", "duplicate"])
async def test_invalid_saved_exit_is_refused_without_overwriting_evidence(tmp_path, fault):
    async with rehearsal_session(tmp_path / "invalid-exit.db") as book:
        setup_engine(book)
        book.now = OPEN + timedelta(minutes=5)
        await book.engine.step(buy(book, 5))
        book.fill("1", 5, "100")
        await book.engine.manage()
        cycle = book.conn.execute("SELECT MIN(seq) FROM fills").fetchone()[0]
        key = book.engine.prefix + f"strategy-exit:SPY:{cycle}"
        payload = dict(symbol="SPY", buy_fill_seq=cycle, limit="99.94")
        if fault == "price":
            payload["limit"] = "NaN"
        elif fault == "cycle":
            payload["buy_fill_seq"] += 1
        book.engine._event(key, "STRATEGY_EXIT_REQUESTED", **payload)
        if fault == "duplicate":
            book.engine._event(key, "STRATEGY_EXIT_REQUESTED", **payload)
        before = [tuple(row) for row in book.conn.execute(
            "SELECT * FROM intraday_execution_events WHERE claim_id=?", (key,),
        )]
        result = await book.engine.manage()
        assert result == dict(status="HALTED", reason="STRATEGY_EXIT_STATE_INVALID", actions=[])
        assert len(book.orders) == 1
        assert before == [tuple(row) for row in book.conn.execute(
            "SELECT * FROM intraday_execution_events WHERE claim_id=?", (key,),
        )]
        # Explicit operator liquidation uses its own guarded path; malformed
        # normal-strategy metadata must not disable that existing response.
        book.engine.request_drain()
        result = await book.engine.manage()
        assert result["status"] == "EXIT_ONLY" and len(book.orders) == 2
        assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"
        assert book.orders["2"]["qty"] == 5
