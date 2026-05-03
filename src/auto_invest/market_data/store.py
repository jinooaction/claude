"""PriceBar persistence: insert-or-skip, first-write-wins.

Per `data-model.md`, the price_bars table uses
`(symbol, timeframe, bar_open_utc)` as PRIMARY KEY. A second insert
with the same key is silently ignored — late-arriving corrections are
NOT applied; if a correction is needed, the operator records a
discrepancy event in the audit log instead. This keeps the historical
indicator inputs stable and reproducible.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    timeframe: str
    bar_open_utc: str
    open_usd: Decimal
    high_usd: Decimal
    low_usd: Decimal
    close_usd: Decimal
    volume: int


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _row_to_bar(row: sqlite3.Row) -> PriceBar:
    return PriceBar(
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        bar_open_utc=row["bar_open_utc"],
        open_usd=Decimal(row["o"]),
        high_usd=Decimal(row["h"]),
        low_usd=Decimal(row["l"]),
        close_usd=Decimal(row["c"]),
        volume=int(row["volume"]),
    )


def insert_bar(conn: sqlite3.Connection, bar: PriceBar) -> bool:
    """Insert a price bar. Returns True if inserted, False if a row
    with the same (symbol, timeframe, bar_open_utc) already exists."""
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO price_bars
            (symbol, timeframe, bar_open_utc, o, h, l, c, volume, ingested_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bar.symbol,
            bar.timeframe,
            bar.bar_open_utc,
            str(bar.open_usd),
            str(bar.high_usd),
            str(bar.low_usd),
            str(bar.close_usd),
            bar.volume,
            _utcnow_iso_ms(),
        ),
    )
    return cursor.rowcount == 1


def get_bars(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
    since_utc: str | None = None,
    limit: int | None = None,
) -> list[PriceBar]:
    """Return bars in ascending bar_open_utc order."""
    query = (
        "SELECT symbol, timeframe, bar_open_utc, o, h, l, c, volume "
        "FROM price_bars WHERE symbol = ? AND timeframe = ?"
    )
    params: list[Any] = [symbol, timeframe]
    if since_utc is not None:
        query += " AND bar_open_utc >= ?"
        params.append(since_utc)
    query += " ORDER BY bar_open_utc"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [_row_to_bar(r) for r in rows]


def get_latest_bar(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
) -> PriceBar | None:
    """Most recent bar for (symbol, timeframe), or None when none exist."""
    row = conn.execute(
        """
        SELECT symbol, timeframe, bar_open_utc, o, h, l, c, volume
        FROM price_bars
        WHERE symbol = ? AND timeframe = ?
        ORDER BY bar_open_utc DESC
        LIMIT 1
        """,
        (symbol, timeframe),
    ).fetchone()
    return _row_to_bar(row) if row else None
