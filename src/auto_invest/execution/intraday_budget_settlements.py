"""Match closed intraday groups to reported net settlements, without NAV claims."""

import asyncio
import hashlib
import json
from datetime import datetime
from decimal import Decimal, localcontext

from auto_invest.broker.intraday_inputs import EXCHANGES
from auto_invest.broker.intraday_transactions import _row, audit_settlements, observe_transactions
from auto_invest.broker.overseas import get_order_executions_resolving_market
from auto_invest.execution.intraday_budget import BudgetSettlements, SettlementGroup
from auto_invest.market_data.intraday import NY
from auto_invest.persistence.fill_amounts import fill_amounts


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _day(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() is None:
        raise ValueError("BUDGET_SETTLEMENT_ORDER_DATE")
    return stamp.astimezone(NY).date().strftime("%Y%m%d")


def assess_budget_settlements(connection, *, account, executions, transactions, now):
    if (now.utcoffset() is None or transactions.get("pagination_complete") is not True
            or not isinstance(transactions.get("rows"), list)):
        raise ValueError("BUDGET_SETTLEMENT_REPORT_INVALID")
    rows = [_row(row) for row in transactions["rows"]]
    if rows and not audit_settlements(rows)["arithmetic_verified"]:
        raise ValueError("BUDGET_SETTLEMENT_ARITHMETIC")
    today = now.astimezone(NY).strftime("%Y%m%d")
    local, local_groups, broker_groups, report_groups = {}, {}, {}, {}
    blocked = set()
    with localcontext() as context:
        context.prec = 100
        for raw in connection.execute("SELECT o.*,r.order_exchange FROM orders o "
                                      "LEFT JOIN order_routing r USING(correlation_id)"):
            order = dict(raw)
            if order["kis_order_id"] in local:
                raise ValueError("BUDGET_SETTLEMENT_ORDER_IDENTITY")
            if order["kis_order_id"] is None:
                continue
            local[order["kis_order_id"]] = order
            if order["rule_id"].startswith("intraday:"):
                key = (_day(order["submitted_at_utc"]), order["symbol"], order["side"])
                local_groups.setdefault(key, set()).add(order["kis_order_id"])
        identities = set()
        for execution in executions:
            if execution.kis_order_id in identities:
                raise ValueError("BUDGET_SETTLEMENT_ORDER_IDENTITY")
            identities.add(execution.kis_order_id)
            if execution.reported_order_date is None or execution.side is None:
                if execution.filled_qty:
                    raise ValueError("BUDGET_SETTLEMENT_ORDER_DATE")
                continue
            key = (execution.reported_order_date.strftime("%Y%m%d"), execution.symbol,
                   execution.side.value)
            order = local.get(execution.kis_order_id)
            if (not execution.terminal or execution.unfilled_qty != 0 or not order
                    or not order["rule_id"].startswith("intraday:")
                    or order["state"] not in {"FILLED", "EXPIRED"}
                    or order["symbol"] != execution.symbol or order["side"] != execution.side.value
                    or execution.market != (order["order_exchange"]
                                             or EXCHANGES.get(order["symbol"]))
                    or _day(order["submitted_at_utc"]) != key[0]
                    or order["qty"] != execution.reported_order_quantity):
                blocked.add(key)
                continue
            amounts = fill_amounts(connection, correlation_id=order["correlation_id"])
            quantity = connection.execute("SELECT COALESCE(SUM(qty),0) FROM fills "
                "WHERE order_correlation_id=?", (order["correlation_id"],)).fetchone()[0]
            gross = sum(amounts.values(), Decimal(0))
            if (quantity != execution.filled_qty
                    or gross != execution.filled_qty * execution.avg_fill_price_usd):
                blocked.add(key)
                continue
            group = broker_groups.setdefault(key, dict(ids=set(), correlations=[], qty=0,
                                                       gross=Decimal(0)))
            group["ids"].add(execution.kis_order_id)
            if quantity:
                group["correlations"].append(order["correlation_id"])
            group["qty"] += quantity
            group["gross"] += gross
        for row in rows:
            key = (row["trad_dt"], row["pdno"],
                   "BUY" if row["sll_buy_dvsn_cd"] == "02" else "SELL")
            if (row["crcy_cd"] != "USD" or row["sttl_dt"] >= today
                    or row["sttl_dt"] < row["trad_dt"]):
                blocked.add(key)
            value = report_groups.setdefault(key, dict(qty=Decimal(0), gross=Decimal(0),
                                                       fees=Decimal(0)))
            value["qty"] += Decimal(row["ccld_qty"])
            value["gross"] += Decimal(row["tr_frcr_amt2"])
            value["fees"] += Decimal(row["dmst_frcr_fee1"]) + Decimal(row["frcr_fee1"])
        groups = []
        for key, broker in broker_groups.items():
            report = report_groups.get(key)
            if (key in blocked or not report or broker["ids"] != local_groups.get(key)
                    or broker["qty"] != report["qty"] or broker["gross"] != report["gross"]
                    or broker["gross"] <= 0):
                continue
            groups.append(SettlementGroup(tuple(sorted(broker["correlations"])), key[2],
                                          broker["gross"], report["fees"]))
    source = dict(executions=[row.model_dump(mode="json") for row in executions],
                  transactions=transactions)
    return BudgetSettlements(hashlib.sha256(account.encode()).hexdigest(),
        _digest(source), now, tuple(groups), json.dumps(source, sort_keys=True, default=str))


def _ledger_digest(connection):
    return _digest({table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
                    for table in ("orders", "fills", "fill_notionals", "order_state_history")})


async def read_budget_settlements(observer, connection):
    """GET only. Unknown/unfinished groups receive no credit, rather than a guess."""
    now = observer.now()
    today = now.astimezone(NY).strftime("%Y%m%d")
    if connection.execute("SELECT 1 FROM orders WHERE state IN "
                          "('INTENT','SUBMITTING','SUBMISSION_UNKNOWN','SUBMITTED',"
                          "'PARTIALLY_FILLED') LIMIT 1").fetchone():
        return None
    dates = [_day(row[0]) for row in connection.execute(
        "SELECT DISTINCT o.submitted_at_utc FROM orders o JOIN fills f "
        "ON o.correlation_id=f.order_correlation_id WHERE substr(o.rule_id,1,9)='intraday:'")]
    if not dates or min(dates) >= today:
        return None
    before = _ledger_digest(connection)
    async with asyncio.timeout(30):
        await observer.refresh_credentials()
        arguments = dict(
            account=observer.account, access_token=observer.authority.access_token,
            app_key=observer.authority.app_key, app_secret=observer.authority.app_secret,
        )
        query = dict(order_date_yyyymmdd=min(dates), end_date_yyyymmdd=today, strict_contract=True)
        executions = await get_order_executions_resolving_market(
            observer.broker, **arguments, **query)
        transactions = await observe_transactions(observer.broker, **arguments,
                           start_date=min(dates), end_date=today, now=observer.now)
        repeat = await get_order_executions_resolving_market(observer.broker, **arguments, **query)
    observer._check_connection()
    if executions != repeat or before != _ledger_digest(connection):
        raise ValueError("BUDGET_SETTLEMENT_SOURCE_CHANGED")
    return assess_budget_settlements(connection, account=observer.account, executions=executions,
                                     transactions=transactions, now=observer.now())
