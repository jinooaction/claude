from decimal import Decimal, localcontext

import pytest

from auto_invest.execution.intraday_budget import budget_usage
from auto_invest.persistence import db


@pytest.fixture
def book(tmp_path):
    conn = db.get_connection(tmp_path / "budget.db")
    db.migrate(conn)
    yield conn
    conn.close()


def order(conn, key="one", *, state="SUBMITTED", qty=5, side="BUY", prefix="a"):
    conn.execute(
        "INSERT INTO orders(correlation_id,rule_id,symbol,side,order_type,qty,"
        "limit_price_usd,state) VALUES(?,?,'SPY',?,'LIMIT',?,'20',?)",
        (key, "intraday:" + prefix * 64 + ":" + key, side, qty, state),
    )
    conn.execute("INSERT INTO order_state_history(order_correlation_id,to_state,ts_utc) "
                 "VALUES(?,?,'2026-09-01T14:00:00Z')", (key, state))


def fill(conn, key="one", *, qty=2, price="19", fee=None):
    conn.execute("INSERT INTO fills(order_correlation_id,kis_fill_id,qty,price_usd,"
                 "executed_at_utc,commission_usd) VALUES(?,?,?,?,?,?)",
                 (key, "K:" + key, qty, price, "2026-09-01T14:00:00Z", fee))


def test_partial_fill_reserves_remaining_and_survives_reopen(book):
    order(book, state="PARTIALLY_FILLED")
    fill(book)
    result = budget_usage(book, Decimal("600"))
    assert result.gross_purchases == Decimal("38")
    assert result.pending_purchases == Decimal("60")
    assert result.cost_reserve == Decimal(".294")
    assert result.available == Decimal("501.706")
    path = book.execute("PRAGMA database_list").fetchone()[2]
    other = db.get_connection(path)
    try:
        assert budget_usage(other, Decimal("600")) == result
    finally:
        other.close()


@pytest.mark.parametrize("state", ["INTENT", "SUBMITTING", "SUBMISSION_UNKNOWN", "SUBMITTED"])
def test_uncertain_orders_keep_the_entire_reservation(book, state):
    order(book, state=state)
    assert budget_usage(book, Decimal("600")).available == Decimal("499.7")


def test_terminal_partial_only_releases_unused_quantity(book):
    order(book, state="EXPIRED")
    fill(book)
    result = budget_usage(book, Decimal("600"))
    assert result.pending_purchases == 0
    assert result.available == Decimal("561.886")


def test_sales_do_not_credit_unverified_settlement_and_new_fingerprint_does_not_reset(book):
    order(book, state="FILLED", qty=2)
    fill(book, fee="1")
    order(book, "sold", state="FILLED", qty=2, side="SELL")
    fill(book, "sold", price="21", fee="2")
    order(book, "new", prefix="b")
    result = budget_usage(book, Decimal("600"))
    assert result.gross_purchases == 38
    assert result.pending_purchases == 100
    assert result.cost_reserve == Decimal("3.3")
    assert result.available == Decimal("458.7")


@pytest.mark.parametrize("state,quantity", [("FILLED", 1), ("EXPIRED", 6),
                                           ("REJECTED_BY_BROKER", 1), ("UNRECOGNIZED", 1)])
def test_bad_state_or_fill_quantity_does_not_release_budget(book, state, quantity):
    order(book, state=state)
    fill(book, qty=quantity)
    with pytest.raises(ValueError, match="BUDGET_"):
        budget_usage(book, Decimal("600"))


def test_cached_terminal_state_without_history_cannot_release_reservation(book):
    order(book)
    book.execute("UPDATE orders SET state='EXPIRED'")
    with pytest.raises(ValueError, match="BUDGET_STATE_HISTORY"):
        budget_usage(book, Decimal("600"))


def test_precision_independent_and_overrun_is_visible(book):
    order(book, state="FILLED", qty=5)
    fill(book, qty=5, price="20", fee="0.31")
    with localcontext() as context:
        context.prec = 3
        result = budget_usage(book, Decimal("100"))
    assert result.available == 0
    assert result.overrun == Decimal(".31")


@pytest.mark.parametrize("capital", [Decimal("0"), Decimal("NaN"), Decimal("Infinity"),
                                     Decimal("-1"), "600", True])
def test_bad_budget_is_not_account_cash(book, capital):
    with pytest.raises(ValueError, match="BUDGET_LIMIT_INVALID"):
        budget_usage(book, capital)
