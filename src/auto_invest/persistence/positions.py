"""Position cache: aggregated holdings, rebuildable from fills.

Stores qty + avg_cost per symbol. Not the source of truth — that lives
in the append-only `fills` table — but a fast-read cache for risk
gates and reconciliation.

Two paths keep the cache in sync with reality:

  * `update_from_fill`  — incremental: called after each FILL audit
                          row is appended.
  * `rebuild_from_fills` — deterministic full recompute from
                          (orders JOIN fills); used at startup and
                          when reconciliation finds a discrepancy.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from auto_invest.config.enums import Side


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: int
    avg_cost_usd: Decimal
    last_updated_utc: str


def _row_to_position(row: sqlite3.Row) -> Position:
    return Position(
        symbol=row["symbol"],
        qty=int(row["qty"]),
        avg_cost_usd=Decimal(row["avg_cost_usd"]),
        last_updated_utc=row["last_updated_utc"],
    )


def get_position(conn: sqlite3.Connection, symbol: str) -> Position | None:
    row = conn.execute(
        "SELECT * FROM current_positions WHERE symbol = ?", (symbol,)
    ).fetchone()
    return _row_to_position(row) if row else None


def get_all_positions(conn: sqlite3.Connection) -> list[Position]:
    rows = conn.execute(
        "SELECT * FROM current_positions ORDER BY symbol"
    ).fetchall()
    return [_row_to_position(r) for r in rows]


def rebuild_from_fills(conn: sqlite3.Connection) -> None:
    """Wipe `current_positions` and recompute it from fills+orders."""
    rows = conn.execute(
        """
        SELECT o.symbol AS symbol, o.side AS side, f.qty AS qty,
               f.price_usd AS price_usd, f.executed_at_utc AS executed_at_utc
        FROM fills f
        JOIN orders o ON f.order_correlation_id = o.correlation_id
        ORDER BY f.executed_at_utc, f.seq
        """
    ).fetchall()

    aggregates: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = row["symbol"]
        side = row["side"]
        qty = int(row["qty"])
        price = Decimal(row["price_usd"])
        ts = row["executed_at_utc"]

        agg = aggregates.setdefault(
            symbol, {"qty": 0, "avg": Decimal("0"), "ts": ""}
        )
        if side == "BUY":
            new_qty = agg["qty"] + qty
            if new_qty > 0:
                agg["avg"] = (
                    Decimal(agg["qty"]) * agg["avg"] + Decimal(qty) * price
                ) / Decimal(new_qty)
            agg["qty"] = new_qty
        else:  # SELL
            agg["qty"] -= qty
            # avg_cost on remaining shares stays the same; if qty <= 0
            # the row is dropped below.
        agg["ts"] = ts

    conn.execute("DELETE FROM current_positions")
    for symbol, agg in aggregates.items():
        if agg["qty"] == 0:
            continue
        conn.execute(
            """
            INSERT INTO current_positions(symbol, qty, avg_cost_usd, last_updated_utc)
            VALUES (?, ?, ?, ?)
            """,
            (symbol, agg["qty"], str(agg["avg"]), agg["ts"]),
        )


def update_from_fill(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    side: Side,
    qty: int,
    price_usd: Decimal,
    ts_utc: str,
) -> Position | None:
    """Apply a single fill incrementally.

    Returns the updated Position, or None when the new qty is zero
    (the row is deleted).
    """
    existing = get_position(conn, symbol)
    old_qty = existing.qty if existing else 0
    old_avg = existing.avg_cost_usd if existing else Decimal("0")

    if side is Side.BUY:
        new_qty = old_qty + qty
        new_avg = (
            (Decimal(old_qty) * old_avg + Decimal(qty) * price_usd) / Decimal(new_qty)
            if new_qty > 0
            else Decimal("0")
        )
    else:  # SELL
        new_qty = old_qty - qty
        new_avg = old_avg

    if new_qty == 0:
        if existing is not None:
            conn.execute("DELETE FROM current_positions WHERE symbol = ?", (symbol,))
        return None

    if existing is None:
        conn.execute(
            """
            INSERT INTO current_positions(symbol, qty, avg_cost_usd, last_updated_utc)
            VALUES (?, ?, ?, ?)
            """,
            (symbol, new_qty, str(new_avg), ts_utc),
        )
    else:
        conn.execute(
            """
            UPDATE current_positions
            SET qty = ?, avg_cost_usd = ?, last_updated_utc = ?
            WHERE symbol = ?
            """,
            (new_qty, str(new_avg), ts_utc, symbol),
        )

    return Position(
        symbol=symbol,
        qty=new_qty,
        avg_cost_usd=new_avg,
        last_updated_utc=ts_utc,
    )
