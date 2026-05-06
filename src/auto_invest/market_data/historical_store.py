"""Append-only writers for the spec 002 historical store (T016).

Writes are idempotent on the natural key
`(asset_class, venue, symbol, kind, vendor, ts, as_of_ts, [is_adjusted])`.
A second insert with the same key is a no-op (the trigger from
0002_data_and_backtest.sql blocks UPDATE/DELETE on `frozen=1`
rows, so we use INSERT OR IGNORE for idempotence).

A genuine *revision* of an existing `(asset_class, venue, symbol,
kind, vendor, ts)` is recorded by writing a NEW row with a fresh
`as_of_ts_utc` — never by mutating.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from auto_invest.market_data.adapters import (
    BarRecord,
    CorporateActionRecord,
    EventRecord,
)


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def write_bars(
    conn: sqlite3.Connection,
    records: Iterable[BarRecord],
    *,
    vendor: str,
    as_of_ts: datetime,
) -> int:
    """Insert (or skip-on-duplicate) bar records. Returns the number inserted."""
    inserted = 0
    as_of = _iso_utc(as_of_ts)
    for r in records:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO historical_bars
                (asset_class, venue, symbol, kind, vendor,
                 bar_open_ts_utc, as_of_ts_utc,
                 open, high, low, close, volume, is_adjusted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r.instrument.asset_class,
                r.instrument.venue,
                r.instrument.symbol,
                r.kind,
                vendor,
                _iso_utc(r.bar_open_ts_utc),
                as_of,
                str(r.open),
                str(r.high),
                str(r.low),
                str(r.close),
                str(r.volume),
                1 if r.is_adjusted else 0,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
    return inserted


def write_events(
    conn: sqlite3.Connection,
    records: Iterable[EventRecord],
    *,
    vendor: str,
    as_of_ts: datetime,
) -> int:
    inserted = 0
    as_of = _iso_utc(as_of_ts)
    for r in records:
        ac = r.instrument.asset_class if r.instrument else None
        v = r.instrument.venue if r.instrument else None
        s = r.instrument.symbol if r.instrument else None
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO event_series
                (asset_class, venue, symbol, kind, vendor,
                 event_ts_utc, as_of_ts_utc, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ac, v, s, r.kind, vendor, _iso_utc(r.event_ts_utc), as_of, json.dumps(r.payload)),
        )
        if cur.rowcount == 1:
            inserted += 1
    return inserted


def write_corporate_actions(
    conn: sqlite3.Connection,
    records: Iterable[CorporateActionRecord],
    *,
    vendor: str,
    as_of_ts: datetime,
) -> int:
    inserted = 0
    as_of = _iso_utc(as_of_ts)
    for r in records:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO corporate_actions
                (asset_class, venue, symbol, vendor, action_kind,
                 effective_ts_utc, as_of_ts_utc, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r.instrument.asset_class,
                r.instrument.venue,
                r.instrument.symbol,
                vendor,
                r.action_kind,
                _iso_utc(r.effective_ts_utc),
                as_of,
                json.dumps(r.payload),
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
    return inserted
