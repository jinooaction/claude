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
from collections.abc import Sequence
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


def bar_summary(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
) -> tuple[int, str | None, str | None]:
    """(count, earliest bar_open_utc, latest bar_open_utc) for (symbol, timeframe).

    Read-only diagnostic — answers "does the instance hold enough stored bars to
    score this symbol?". Returns (0, None, None) when no bars exist.
    """
    row = conn.execute(
        "SELECT COUNT(*) AS n, MIN(bar_open_utc) AS lo, MAX(bar_open_utc) AS hi "
        "FROM price_bars WHERE symbol = ? AND timeframe = ?",
        (symbol, timeframe),
    ).fetchone()
    if row is None or int(row["n"]) == 0:
        return 0, None, None
    return int(row["n"]), row["lo"], row["hi"]


def bar_counts(
    conn: sqlite3.Connection,
    *,
    symbols: Sequence[str],
    timeframe: str,
) -> dict[str, int]:
    """{symbol: stored bar count} for the given symbols/timeframe (0 if absent).

    스펙 041 — 대형 유니버스(예: S&P 500) 백필을 needy-first 로 바운딩하기 위한 진단.
    바가 적은(또는 0인) 종목을 먼저 채우면, 매 실행을 제한해도 여러 실행에 걸쳐 유니버스
    전체가 고르게 채워진다. 단일 GROUP BY 쿼리(종목당 질의 N번이 아니라 1번).
    """
    counts = {s: 0 for s in symbols}
    if not symbols:
        return counts
    placeholders = ",".join("?" for _ in symbols)
    rows = conn.execute(
        f"SELECT symbol, COUNT(*) AS n FROM price_bars "
        f"WHERE timeframe = ? AND symbol IN ({placeholders}) GROUP BY symbol",
        (timeframe, *symbols),
    ).fetchall()
    for row in rows:
        counts[row["symbol"]] = int(row["n"])
    return counts


def available_timeframes(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """All (timeframe, total bar count) present in price_bars, busiest first.

    Diagnostic: when the requested timeframe has 0 bars, this reveals whether the
    instance stores bars under a DIFFERENT timeframe label (config mismatch) or
    stores no bars at all (empty table)."""
    rows = conn.execute(
        "SELECT timeframe, COUNT(*) AS n FROM price_bars GROUP BY timeframe ORDER BY n DESC"
    ).fetchall()
    return [(r["timeframe"], int(r["n"])) for r in rows]


def distinct_symbols(
    conn: sqlite3.Connection,
    *,
    timeframe: str | None = None,
    limit: int = 20,
) -> list[str]:
    """A sample of distinct symbols held (optionally for one timeframe)."""
    if timeframe is not None:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM price_bars WHERE timeframe = ? ORDER BY symbol LIMIT ?",
            (timeframe, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM price_bars ORDER BY symbol LIMIT ?", (limit,)
        ).fetchall()
    return [r["symbol"] for r in rows]
