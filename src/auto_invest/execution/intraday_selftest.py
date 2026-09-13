"""Installed-program checks using fixed offline transport and disposable ledgers."""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_invest.execution.intraday_rehearsal import rehearsal_session, rehearse
from auto_invest.execution.intraday_runtime import run, status


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


async def self_test():
    """No external inputs, environment credentials, sockets, or production DB paths."""
    checks = []
    stage = "PARTIAL_FILL_AND_CANCELLATION"
    try:
        result = await rehearse(capital_limit=Decimal("600"), mark=Decimal("20"))
        require(result["partial_cancel_late_fill_liquidation"] == "PASS", stage)
        checks.append(stage)
        stage = "PERSISTENT_STOP_AND_RESTART"
        with TemporaryDirectory(prefix="intraday-self-test-") as directory:
            database = Path(directory) / "simulation.db"

            async def forbidden_collection():
                raise RuntimeError("DRAIN_MUST_NOT_COLLECT")

            async def cycle(book):
                return await run(
                    book.engine, candidate=None, provider="kis-nasdaq-partial-unadjusted",
                    collect_bars=forbidden_collection, max_cycles=1,
                )

            async with rehearsal_session(
                database, capital_limit=Decimal("600"), mark=Decimal("20"),
            ) as book:
                submitted = await book.engine.step(book.decision(5))
                require(submitted["actions"][0]["kind"] == "SUBMITTED", stage)
                book.fill("1", 2, "20")
                book.engine.request_drain()
                stopped = await cycle(book)
                require(stopped["phase"] == "NEEDS_ATTENTION", stage)
                require(book.engine.drain_requested(), stage)
                orders = book.orders

            # Reopen the real execution database; the simulated broker retains
            # its separate order state just as a broker survives a client exit.
            async with rehearsal_session(
                database, capital_limit=Decimal("600"), mark=Decimal("20"),
            ) as book:
                book.orders = orders
                require(book.engine.drain_requested(), stage)
                book.fill("1", 3, "20", terminal=True)
                pending = await cycle(book)
                require(pending["phase"] == "NEEDS_ATTENTION", stage)
                require(book.orders["2"]["qty"] == 3, stage)
                require(book.orders["2"]["sll_buy_dvsn_cd"] == "01", stage)
                book.fill("2", 3, "20")
                done = await cycle(book)
                require(done["phase"] == "STOPPED", stage)
                require(not book.engine._owned(), stage)
                require(not book.engine.drain_requested(), stage)
                require(status(database)["running"] is False, stage)
                require(len(book.orders) == 2, stage)
                require(book.conn.execute(
                    "SELECT COUNT(*) FROM intraday_execution_events "
                    "WHERE kind='STOP_COMPLETED'"
                ).fetchone()[0] == 1, stage)
        checks.append(stage)
    except Exception:
        return dict(status="FAILED", mode="OFFLINE_SELF_TEST", checks=checks,
                    failed_check=stage, live_eligible=False, orders_submitted=0)
    return dict(status="SELF_TEST_PASSED", mode="OFFLINE_SELF_TEST", checks=checks,
                live_eligible=False, orders_submitted=0)
