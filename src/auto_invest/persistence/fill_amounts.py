"""Preserve reported cumulative gross amounts without claiming settled cash."""

import re
from decimal import Decimal, localcontext


def _amount(value):
    if (not isinstance(value, str) or len(value) > 96 or not re.fullmatch(
            r"[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]{1,2})?", value)):
        raise ValueError("FILL_NOTIONAL_INVALID")
    result = Decimal(value)
    if (result <= 0 or result.adjusted() > 53 or result.as_tuple().exponent < -36
            or len(result.as_tuple().digits) > 90):
        raise ValueError("FILL_NOTIONAL_INVALID")
    return result


def fill_amounts(connection, *, correlation_id=None):
    """Return gross amounts by fill id, checking each cumulative source chain.

    Legacy rows retain their stored quantity-times-price basis. They acquire no
    reported-amount evidence. New evidence must exactly extend the prior book;
    neither source average rounding nor commissions are certified by this sum.
    """
    has_evidence = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fill_notionals'"
    ).fetchone()
    query = (
        "SELECT f.*,n.notional_usd,n.cumulative_qty,n.cumulative_avg_price_usd "
        "FROM fills f LEFT JOIN fill_notionals n ON n.kis_fill_id=f.kis_fill_id"
        if has_evidence else "SELECT f.* FROM fills f"
    )
    params = ()
    if correlation_id is not None:
        query += " WHERE f.order_correlation_id=?"
        params = (correlation_id,)
    totals, quantities, result = {}, {}, {}
    with localcontext() as context:
        context.prec = 100
        for raw in connection.execute(query + " ORDER BY f.seq", params):
            row = dict(raw)
            qty, corr = row["qty"], row["order_correlation_id"]
            if type(qty) is not int or not 0 < qty <= 10**18:
                raise ValueError("FILL_NOTIONAL_QUANTITY_INVALID")
            price = _amount(row["price_usd"])
            previous = totals.get(corr, Decimal(0))
            count = quantities.get(corr, 0) + qty
            value = row.get("notional_usd")
            if value is None:
                amount = qty * price
            else:
                amount = _amount(value)
                if (type(row["cumulative_qty"]) is not int
                        or row["cumulative_qty"] != count
                        or previous + amount != count * _amount(row["cumulative_avg_price_usd"])):
                    raise ValueError("FILL_NOTIONAL_CUMULATIVE_MISMATCH")
            totals[corr], quantities[corr] = previous + amount, count
            result[row["kis_fill_id"]] = amount
    return result
