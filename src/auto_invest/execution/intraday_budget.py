"""Reconstruct an allocation's usage; never certify account cash or NAV.

Until authenticated net-settlement credits are connected, sales do not replenish
the allocation. The 0.3% reservation is the existing order policy, not a claim
that actual broker charges cannot exceed it. Recorded larger charges prevail.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, localcontext

from auto_invest.persistence.fill_amounts import fill_amounts

PENDING = frozenset({"INTENT", "SUBMITTING", "SUBMISSION_UNKNOWN", "SUBMITTED",
                     "PARTIALLY_FILLED"})
TERMINAL = frozenset({"FILLED", "EXPIRED", "REJECTED_BY_GATE", "REJECTED_BY_BROKER"})
RESERVE_RATE = Decimal(".003")


@dataclass(frozen=True)
class BudgetUsage:
    limit: Decimal
    gross_purchases: Decimal
    pending_purchases: Decimal
    cost_reserve: Decimal
    available: Decimal
    overrun: Decimal
    settled_sales: Decimal = Decimal(0)


@dataclass(frozen=True)
class SettlementGroup:
    correlations: tuple[str, ...]
    side: str
    gross: Decimal
    fees: Decimal


@dataclass(frozen=True)
class BudgetSettlements:
    """Trusted in-process GET reader output, never an operator-imported credit."""

    account_digest: str
    source_digest: str
    observed_at: datetime
    groups: tuple[SettlementGroup, ...]
    source_json: str = field(default="{}", repr=False)


def _amount(value, *, zero=False):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,18}(\.[0-9]{1,12})?", value):
        raise ValueError("BUDGET_AMOUNT_INVALID")
    result = Decimal(value)
    if not zero and result == 0:
        raise ValueError("BUDGET_AMOUNT_INVALID")
    return result


def budget_usage(connection, limit: Decimal, *, settlements=None, account=None) -> BudgetUsage:
    """Read a consistent snapshot of all intraday fingerprints in the shared DB.

No daily reset, caller-provided credit, or sale-proceeds assumption is allowed.
Call within the executor's existing account/instance locks before reserving a
new order. This calculation itself grants neither ownership nor write authority.
"""
    if (not isinstance(limit, Decimal) or not limit.is_finite() or not 0 < limit < 10**18
            or limit.as_tuple().exponent < -12):
        raise ValueError("BUDGET_LIMIT_INVALID")
    if settlements is not None and (
            not isinstance(settlements, BudgetSettlements) or not isinstance(account, str)
            or not re.fullmatch(r"[0-9]{10}", account)
            or settlements.account_digest != hashlib.sha256(account.encode()).hexdigest()
            or not isinstance(settlements.source_digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", settlements.source_digest)
            or not isinstance(settlements.observed_at, datetime)
            or settlements.observed_at.utcoffset() is None
            or not isinstance(settlements.groups, tuple)):
        raise ValueError("BUDGET_SETTLEMENT_ACCOUNT")
    connection.execute("SAVEPOINT intraday_budget_read")
    try:
        with localcontext() as context:
            context.prec = 100
            return _usage(connection, limit, settlements)
    finally:
        connection.execute("RELEASE intraday_budget_read")


def _usage(connection, limit, settlements):
    if connection.execute("SELECT 1 FROM fills f LEFT JOIN orders o "
                          "ON o.correlation_id=f.order_correlation_id "
                          "WHERE o.correlation_id IS NULL LIMIT 1").fetchone():
        raise ValueError("BUDGET_ORPHAN_FILL")
    spent = pending = costs = Decimal(0)
    eligible = {}
    for raw in connection.execute("SELECT * FROM orders WHERE substr(rule_id,1,9)='intraday:'"):
        row = dict(raw)
        key, state, quantity = row["correlation_id"], row["state"], row["qty"]
        if (not re.fullmatch(r"intraday:[a-f0-9]{64}:.+", row["rule_id"])
                or row["side"] not in {"BUY", "SELL"} or row["order_type"] != "LIMIT"
                or state not in PENDING | TERMINAL
                or type(quantity) is not int or not 0 < quantity <= 10**18):
            raise ValueError("BUDGET_ORDER_INVALID")
        price = _amount(row["limit_price_usd"])
        history = connection.execute("SELECT to_state FROM order_state_history "
                                     "WHERE order_correlation_id=? ORDER BY seq DESC LIMIT 1",
                                     (key,)).fetchone()
        if not history or history[0] != state:
            raise ValueError("BUDGET_STATE_HISTORY")
        amounts = fill_amounts(connection, correlation_id=key)
        filled, gross, charges = 0, Decimal(0), Decimal(0)
        for trade in connection.execute("SELECT * FROM fills WHERE order_correlation_id=?",
                                        (key,)):
            filled += trade["qty"]
            amount = amounts[trade["kis_fill_id"]]
            gross += amount
            fee = trade["commission_usd"]
            charges += max(amount * RESERVE_RATE,
                           _amount(fee, zero=True) if fee is not None else Decimal(0))
        if (filled > quantity or state == "FILLED" and filled != quantity
                or state.startswith("REJECTED_") and filled):
            raise ValueError("BUDGET_FILL_QUANTITY")
        costs += charges
        if state in {"FILLED", "EXPIRED"} and filled:
            eligible[key] = (row["side"], gross, charges)
        if row["side"] == "BUY":
            spent += gross
            if state in PENDING:
                outstanding = (quantity - filled) * price
                pending += outstanding
                costs += outstanding * RESERVE_RATE
    sales = Decimal(0)
    seen = set()
    if settlements is not None:
        for group in settlements.groups:
            if (not isinstance(group, SettlementGroup) or not group.correlations
                    or len(set(group.correlations)) != len(group.correlations)
                    or seen.intersection(group.correlations)
                    or set(group.correlations) - eligible.keys()
                    or group.side not in {"BUY", "SELL"}
                    or not isinstance(group.fees, Decimal) or not group.fees.is_finite()
                    or not 0 <= group.fees < 10**18
                    or not isinstance(group.gross, Decimal) or not group.gross.is_finite()
                    or group.gross <= 0):
                raise ValueError("BUDGET_SETTLEMENT_INVALID")
            values = [eligible[key] for key in group.correlations]
            if (any(value[0] != group.side for value in values)
                    or sum((value[1] for value in values), Decimal(0)) != group.gross):
                raise ValueError("BUDGET_SETTLEMENT_LEDGER_MISMATCH")
            seen.update(group.correlations)
            costs += group.fees - sum((value[2] for value in values), Decimal(0))
            if group.side == "SELL":
                sales += group.gross
    used = spent + pending + costs - sales
    return BudgetUsage(limit, spent, pending, costs, min(limit, max(Decimal(0), limit - used)),
                       max(Decimal(0), used - limit), sales)
