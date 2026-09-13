from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from auto_invest.broker.models import BrokerExecution
from auto_invest.config.enums import Side
from auto_invest.execution.intraday_budget import budget_usage
from auto_invest.execution.intraday_budget_settlements import assess_budget_settlements
from auto_invest.persistence import db

ACCOUNT = "1234567801"
NOW = datetime(2026, 9, 5, 15, tzinfo=UTC)


@pytest.fixture
def settled_book(tmp_path):
    connection = db.get_connection(tmp_path / "settled.db")
    db.migrate(connection)
    executions, rows = [], []
    for key, side, price, net in (("1", "BUY", "20", "41"), ("2", "SELL", "21", "41")):
        connection.execute("INSERT INTO orders(correlation_id,rule_id,symbol,side,order_type,"
            "qty,limit_price_usd,state,kis_order_id,submitted_at_utc) "
            "VALUES(?,?,'SPY',?,'LIMIT',2,?,'FILLED',?,'2026-09-01T14:00:00Z')",
            (key, "intraday:" + "a" * 64 + ":" + key, side, price, key))
        connection.execute("INSERT INTO order_state_history(order_correlation_id,to_state,ts_utc) "
                           "VALUES(?,'FILLED','2026-09-01T14:00:00Z')", (key,))
        connection.execute("INSERT INTO fills(order_correlation_id,kis_fill_id,qty,price_usd,"
                           "executed_at_utc) VALUES(?,?,2,?,'2026-09-01T14:00:00Z')",
                           (key, "K:" + key, price))
        executions.append(BrokerExecution(kis_order_id=key, symbol="SPY", side=Side(side),
            filled_qty=2, avg_fill_price_usd=Decimal(price), unfilled_qty=0, terminal=True,
            reported_order_quantity=2, reported_order_date=date(2026, 9, 1), market="AMEX"))
        rows.append(dict(trad_dt="20260901", sttl_dt="20260902", pdno="SPY", crcy_cd="USD",
            sll_buy_dvsn_cd="02" if side == "BUY" else "01", ccld_qty="2",
            tr_frcr_amt2=str(2 * Decimal(price)), frcr_excc_amt_1=net,
            dmst_frcr_fee1="1", frcr_fee1="0"))
    yield connection, executions, dict(pagination_complete=True, rows=rows)
    connection.close()


def assess(book):
    connection, executions, transactions = book
    return assess_budget_settlements(connection, account=ACCOUNT, executions=executions,
                                      transactions=transactions, now=NOW)


def test_reported_net_settlement_restores_budget_once_and_after_reopen(settled_book):
    connection, _, _ = settled_book
    before = budget_usage(connection, Decimal("600"))
    assert before.available < 560
    evidence = assess(settled_book)
    assert len(evidence.groups) == 2
    kwargs = dict(settlements=evidence, account=ACCOUNT)
    result = budget_usage(connection, Decimal("600"), **kwargs)
    assert result.available == Decimal("600")
    assert result.cost_reserve == Decimal("2")
    assert result.settled_sales == Decimal("42")
    assert budget_usage(connection, Decimal("600"), **kwargs) == result
    other = db.get_connection(connection.execute("PRAGMA database_list").fetchone()[2])
    try:
        assert budget_usage(other, Decimal("600"), **kwargs) == result
        # Restart without a fresh reader result cannot recreate the credit itself.
        assert budget_usage(other, Decimal("600")) == before
    finally:
        other.close()


@pytest.mark.parametrize("field,value", [
    ("sttl_dt", "20260905"), ("sttl_dt", "20260906"), ("sttl_dt", "20260831"),
    ("trad_dt", "20260903"), ("crcy_cd", "KRW"), ("pdno", "QQQ"),
])
def test_unmatched_or_unmatured_sales_never_credit_budget(settled_book, field, value):
    connection, executions, transactions = settled_book
    changed = deepcopy(transactions)
    changed["rows"][1][field] = value
    evidence = assess((connection, executions, changed))
    assert all(group.side != "SELL" for group in evidence.groups)


@pytest.mark.parametrize("change", [
    dict(market="NASD"), dict(reported_order_quantity=None), dict(terminal=False),
    dict(avg_fill_price_usd=Decimal("20.5")), dict(kis_order_id="unknown"),
])
def test_broker_order_must_match_recorded_sale(settled_book, change):
    connection, executions, transactions = settled_book
    changed = [executions[0], executions[1].model_copy(update=change)]
    evidence = assess((connection, changed, transactions))
    assert all(group.side != "SELL" for group in evidence.groups)


def test_other_strategy_in_same_group_is_not_our_credit(settled_book):
    connection, _, _ = settled_book
    connection.execute("UPDATE orders SET rule_id='external' WHERE side='SELL'")
    evidence = assess(settled_book)
    assert all(group.side != "SELL" for group in evidence.groups)


def test_duplicate_or_wrong_account_credit_is_rejected(settled_book):
    connection, _, _ = settled_book
    evidence = assess(settled_book)
    with pytest.raises(ValueError, match="BUDGET_SETTLEMENT_ACCOUNT"):
        budget_usage(connection, Decimal("600"), settlements=evidence, account="8765432101")
    with pytest.raises(ValueError, match="BUDGET_SETTLEMENT_INVALID"):
        budget_usage(connection, Decimal("600"), account=ACCOUNT,
                     settlements=replace(evidence, groups=evidence.groups * 2))


def test_net_amount_must_include_reported_costs(settled_book):
    connection, executions, transactions = settled_book
    transactions["rows"][1]["frcr_excc_amt_1"] = "42"
    with pytest.raises(ValueError, match="BUDGET_SETTLEMENT_ARITHMETIC"):
        assess((connection, executions, transactions))


def test_profits_do_not_automatically_increase_the_confirmed_allocation(settled_book):
    connection, _, transactions = settled_book
    for row in transactions["rows"]:
        row["dmst_frcr_fee1"] = "0"
        row["frcr_excc_amt_1"] = row["tr_frcr_amt2"]
    usage = budget_usage(connection, Decimal("600"), account=ACCOUNT,
                         settlements=assess(settled_book))
    assert usage.available == 600


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [False, True])
async def test_authenticated_reader_brackets_transactions_with_same_orders(
    settled_book, monkeypatch, changed,
):
    from auto_invest.execution import intraday_budget_settlements as source

    connection, executions, transactions = settled_book
    calls = []

    async def authenticate():
        calls.append("authentication")

    async def orders(broker, **kwargs):
        assert kwargs["account"] == ACCOUNT and kwargs["strict_contract"] is True
        assert kwargs["order_date_yyyymmdd"] == "20260901"
        calls.append("orders")
        return executions[:-1] if changed and calls.count("orders") == 2 else executions

    async def report(broker, **kwargs):
        assert kwargs["account"] == ACCOUNT and kwargs["start_date"] == "20260901"
        assert kwargs["end_date"] == "20260905"
        calls.append("transactions")
        return transactions

    monkeypatch.setattr(source, "get_order_executions_resolving_market", orders)
    monkeypatch.setattr(source, "observe_transactions", report)
    observer = SimpleNamespace(account=ACCOUNT, broker=object(), now=lambda: NOW,
        authority=SimpleNamespace(access_token="offline", app_key="offline", app_secret="offline"),
        refresh_credentials=authenticate, _check_connection=lambda: None)
    if changed:
        with pytest.raises(ValueError, match="BUDGET_SETTLEMENT_SOURCE_CHANGED"):
            await source.read_budget_settlements(observer, connection)
    else:
        evidence = await source.read_budget_settlements(observer, connection)
        assert budget_usage(connection, Decimal("600"), account=ACCOUNT,
                            settlements=evidence).available == 600
    assert calls == ["authentication", "orders", "transactions", "orders"]
