"""Read-only comparison of reported executions, local fills and transaction rows.

An equality is scoped to the supplied broker reports. It does not prove that
their registration/order-date windows cover every trade or account cash flow.
No fee is assigned to an individual order without a broker order identifier.
"""

import re
import sqlite3
from decimal import Decimal, localcontext
from pathlib import Path

from auto_invest.broker.intraday_transactions import audit_settlements
from auto_invest.broker.models import BrokerExecution
from auto_invest.persistence.fill_amounts import fill_amounts


class CostReconciliationError(ValueError):
    pass


def _decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,18}(\.[0-9]{1,36})?", value):
        raise CostReconciliationError("COST_LEDGER_AMOUNT_INVALID")
    try:
        result = Decimal(value)
    except Exception:
        raise CostReconciliationError("COST_LEDGER_AMOUNT_INVALID") from None
    if not result.is_finite() or result < 0:
        raise CostReconciliationError("COST_LEDGER_AMOUNT_INVALID")
    return result


def reconcile_cost_inputs(database: Path, executions, transaction_rows):
    """Compare original rows, never trust an input report's prior MATCH flag.

    SQLite mode=ro and a read transaction preserve one snapshot without changing
    user data. Fill timestamps are intentionally unused: KIS order timestamps
    and locally observed timestamps do not establish actual execution instants.
    """
    if (not isinstance(executions, list) or len(executions) > 10000
            or any(not isinstance(value, BrokerExecution) for value in executions)):
        raise CostReconciliationError("COST_EXECUTIONS_INVALID")
    ids = [value.kis_order_id for value in executions]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise CostReconciliationError("COST_ORDER_IDENTITY_INVALID")
    settlement = audit_settlements(transaction_rows)
    connection = None
    issues, matched, broker_groups, transaction_groups = set(), 0, {}, {}
    try:
        path = Path(database).resolve(strict=True)
        if not path.is_file():
            raise CostReconciliationError("COST_LEDGER_UNAVAILABLE")
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        try:
            amounts = fill_amounts(connection)
        except ValueError:
            raise CostReconciliationError("COST_LEDGER_AMOUNT_INVALID") from None
        with localcontext() as context:
            context.prec = 80
            for execution in executions:
                if (execution.side is None or execution.market not in {"NASD", "NYSE", "AMEX"}
                        or not execution.avg_fill_price_usd.is_finite()
                        or execution.avg_fill_price_usd < 0):
                    raise CostReconciliationError("COST_EXECUTION_CONTRACT_INVALID")
                if not execution.filled_qty:
                    continue
                if execution.filled_qty > 10**18:
                    raise CostReconciliationError("COST_EXECUTION_CONTRACT_INVALID")
                if execution.avg_fill_price_usd == 0:
                    raise CostReconciliationError("COST_EXECUTION_CONTRACT_INVALID")
                key = (execution.symbol, execution.side.value)
                qty = Decimal(execution.filled_qty)
                notional = qty * _decimal(str(execution.avg_fill_price_usd))
                group = broker_groups.setdefault(key, [Decimal(0), Decimal(0)])
                group[0] += qty
                group[1] += notional
                orders = connection.execute(
                    "SELECT correlation_id, symbol, side FROM orders WHERE kis_order_id=?",
                    (execution.kis_order_id,),
                ).fetchall()
                if len(orders) != 1:
                    issues.add("BROKER_ORDER_NOT_UNIQUELY_IN_LEDGER")
                    continue
                order = orders[0]
                if (order["symbol"], order["side"]) != key:
                    issues.add("LEDGER_ORDER_IDENTITY_MISMATCH")
                    continue
                local_qty, local_notional = Decimal(0), Decimal(0)
                for fill in connection.execute(
                    "SELECT kis_fill_id, qty, price_usd FROM fills WHERE order_correlation_id=?",
                    (order["correlation_id"],),
                ):
                    if type(fill["qty"]) is not int or not 0 < fill["qty"] <= 10**18:
                        raise CostReconciliationError("COST_LEDGER_QUANTITY_INVALID")
                    local_qty += fill["qty"]
                    local_notional += amounts[fill["kis_fill_id"]]
                if (local_qty, local_notional) != (qty, notional):
                    issues.add("LEDGER_FILL_TOTAL_MISMATCH")
                else:
                    matched += 1
            for row in transaction_rows:
                if row["crcy_cd"].strip() != "USD":
                    issues.add("NON_USD_TRANSACTION_SCOPE")
                    continue
                key = (row["pdno"].strip(), "BUY" if row["sll_buy_dvsn_cd"].strip() == "02"
                       else "SELL")
                group = transaction_groups.setdefault(key, [Decimal(0), Decimal(0)])
                group[0] += _decimal(row["ccld_qty"])
                group[1] += _decimal(row["tr_frcr_amt2"])
            if not broker_groups or not transaction_rows:
                issues.add("NO_COMPARABLE_TRADES")
            if broker_groups != transaction_groups:
                issues.add("TRANSACTION_EXECUTION_TOTAL_MISMATCH")
            if not settlement["arithmetic_verified"]:
                issues.add("SETTLEMENT_ARITHMETIC_UNVERIFIED")
    except CostReconciliationError:
        raise
    except (OSError, sqlite3.Error):
        raise CostReconciliationError("COST_LEDGER_UNAVAILABLE") from None
    finally:
        if connection is not None:
            connection.close()
    return dict(
        status="MATCH" if not issues else "MISMATCH", scope="SUPPLIED_BROKER_REPORTS",
        matched_order_count=matched, reported_order_count=len(executions),
        transaction_row_count=len(transaction_rows), issues=sorted(issues),
        report_totals_match=not issues, per_order_fees_verified=False,
        account_cash_verified=False, execution_parity_verified=False,
    )
