"""Exposure reservation helpers for unresolved BUY orders.

The risk gates remain the authority for K1 caps. This module only computes the
stricter exposure snapshot they should receive: current positions plus open BUY
orders that can still become positions.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

OPEN_BUY_RESERVATION_STATES = frozenset(
    {"INTENT", "SUBMITTED", "PARTIALLY_FILLED", "SUBMISSION_UNKNOWN"}
)

_UNKNOWN_NOTIONAL = Decimal("Infinity")


@dataclass(frozen=True)
class OpenBuyReservation:
    """Aggregated unresolved BUY notional reserved against exposure caps."""

    symbol_exposure_usd: dict[str, Decimal] = field(default_factory=dict)
    global_exposure_usd: Decimal = Decimal("0")
    order_count: int = 0
    unknown_price_count: int = 0


def open_buy_order_reservations(
    conn: sqlite3.Connection,
    *,
    quote_prices: Mapping[str, Decimal] | None = None,
    exclude_correlation_ids: Iterable[str] = (),
) -> OpenBuyReservation:
    """Return reserved exposure from unresolved BUY orders.

    ``exclude_correlation_ids`` prevents the order currently being gated from
    being counted once as an open order and again as the gate's request delta.
    """

    excluded = frozenset(exclude_correlation_ids)
    quote_prices = quote_prices or {}
    placeholders = ",".join("?" for _ in OPEN_BUY_RESERVATION_STATES)
    rows = conn.execute(
        f"""
        SELECT correlation_id, symbol, qty, limit_price_usd, state
        FROM orders
        WHERE side = 'BUY'
          AND state IN ({placeholders})
        ORDER BY seq
        """,
        tuple(sorted(OPEN_BUY_RESERVATION_STATES)),
    ).fetchall()

    by_symbol: dict[str, Decimal] = {}
    total = Decimal("0")
    count = 0
    unknown = 0
    for row in rows:
        if row["correlation_id"] in excluded:
            continue
        qty = Decimal(int(row["qty"]))
        price = _order_price(row, quote_prices)
        if price is None or price <= 0:
            notional = _UNKNOWN_NOTIONAL
            unknown += 1
        else:
            notional = qty * price
        symbol = str(row["symbol"])
        by_symbol[symbol] = by_symbol.get(symbol, Decimal("0")) + notional
        total += notional
        count += 1

    return OpenBuyReservation(
        symbol_exposure_usd=by_symbol,
        global_exposure_usd=total,
        order_count=count,
        unknown_price_count=unknown,
    )


def _order_price(
    row: sqlite3.Row,
    quote_prices: Mapping[str, Decimal],
) -> Decimal | None:
    raw_limit = row["limit_price_usd"]
    if raw_limit not in (None, ""):
        try:
            return Decimal(str(raw_limit))
        except InvalidOperation:
            return None
    return quote_prices.get(str(row["symbol"]))


__all__ = [
    "OPEN_BUY_RESERVATION_STATES",
    "OpenBuyReservation",
    "open_buy_order_reservations",
]
