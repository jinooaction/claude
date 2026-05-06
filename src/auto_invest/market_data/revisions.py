"""Point-in-time reads against the historical store (T017, FR-B-002).

Every read against the spec 002 historical tables flows through this
module so the `as_of_ts_pin` barrier can be enforced uniformly.

The contract:

  * `iter_bars(..., as_of_ts_pin)` yields the *latest* row whose
    `as_of_ts_utc <= as_of_ts_pin` for each
    `(asset_class, venue, symbol, kind, vendor, bar_open_ts_utc)`.
  * `iter_events` and `iter_corporate_actions` are analogous.
  * Bars whose `bar_open_ts_utc` is *outside* the requested
    `[from_utc, to_utc)` window are filtered out.
  * If a row's most recent `as_of_ts_utc` exceeds the pin but an
    older revision exists at or before the pin, the older revision is
    returned. Late-arriving revisions are invisible during replay.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class HistoricalBar:
    asset_class: str
    venue: str
    symbol: str
    kind: str
    vendor: str
    bar_open_ts_utc: str
    as_of_ts_utc: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_adjusted: bool


@dataclass(frozen=True)
class HistoricalEvent:
    kind: str
    asset_class: str | None
    venue: str | None
    symbol: str | None
    vendor: str
    event_ts_utc: str
    as_of_ts_utc: str
    payload: dict


@dataclass(frozen=True)
class HistoricalCorporateAction:
    asset_class: str
    venue: str
    symbol: str
    vendor: str
    action_kind: str
    effective_ts_utc: str
    as_of_ts_utc: str
    payload: dict


def iter_bars(
    conn: sqlite3.Connection,
    *,
    asset_class: str,
    venue: str,
    symbol: str,
    kind: str,
    vendor: str,
    from_utc: datetime,
    to_utc: datetime,
    as_of_ts_pin: datetime,
    is_adjusted: bool = False,
) -> Iterator[HistoricalBar]:
    """Yield bars in ascending `bar_open_ts_utc` order, point-in-time pinned.

    Window is `[from_utc, to_utc)` (inclusive of from, exclusive of to).
    Late revisions (`as_of_ts_utc > as_of_ts_pin`) are invisible.
    """
    pin = _iso_utc(as_of_ts_pin)
    f = _iso_utc(from_utc)
    t = _iso_utc(to_utc)
    q = """
    WITH latest AS (
        SELECT
            asset_class, venue, symbol, kind, vendor, bar_open_ts_utc,
            MAX(as_of_ts_utc) AS pin_as_of
        FROM historical_bars
        WHERE asset_class = ?
          AND venue       = ?
          AND symbol      = ?
          AND kind        = ?
          AND vendor      = ?
          AND is_adjusted = ?
          AND bar_open_ts_utc >= ?
          AND bar_open_ts_utc < ?
          AND as_of_ts_utc <= ?
        GROUP BY asset_class, venue, symbol, kind, vendor, bar_open_ts_utc
    )
    SELECT b.asset_class, b.venue, b.symbol, b.kind, b.vendor,
           b.bar_open_ts_utc, b.as_of_ts_utc,
           b.open, b.high, b.low, b.close, b.volume, b.is_adjusted
    FROM historical_bars b
    JOIN latest l
      ON b.asset_class = l.asset_class
     AND b.venue       = l.venue
     AND b.symbol      = l.symbol
     AND b.kind        = l.kind
     AND b.vendor      = l.vendor
     AND b.bar_open_ts_utc = l.bar_open_ts_utc
     AND b.as_of_ts_utc    = l.pin_as_of
    ORDER BY b.bar_open_ts_utc
    """
    rows = conn.execute(
        q,
        (
            asset_class.lower(),
            venue.lower(),
            symbol.upper(),
            kind,
            vendor,
            1 if is_adjusted else 0,
            f,
            t,
            pin,
        ),
    )
    for row in rows:
        yield HistoricalBar(
            asset_class=row["asset_class"],
            venue=row["venue"],
            symbol=row["symbol"],
            kind=row["kind"],
            vendor=row["vendor"],
            bar_open_ts_utc=row["bar_open_ts_utc"],
            as_of_ts_utc=row["as_of_ts_utc"],
            open=Decimal(row["open"]),
            high=Decimal(row["high"]),
            low=Decimal(row["low"]),
            close=Decimal(row["close"]),
            volume=Decimal(row["volume"]),
            is_adjusted=bool(row["is_adjusted"]),
        )


def iter_corporate_actions(
    conn: sqlite3.Connection,
    *,
    asset_class: str,
    venue: str,
    symbol: str,
    vendor: str,
    from_utc: datetime,
    to_utc: datetime,
    as_of_ts_pin: datetime,
) -> Iterator[HistoricalCorporateAction]:
    """Yield corporate actions in ascending `effective_ts_utc` order, pin-aware."""
    pin = _iso_utc(as_of_ts_pin)
    f = _iso_utc(from_utc)
    t = _iso_utc(to_utc)
    q = """
    WITH latest AS (
        SELECT asset_class, venue, symbol, vendor, action_kind, effective_ts_utc,
               MAX(as_of_ts_utc) AS pin_as_of
        FROM corporate_actions
        WHERE asset_class = ?
          AND venue       = ?
          AND symbol      = ?
          AND vendor      = ?
          AND effective_ts_utc >= ?
          AND effective_ts_utc < ?
          AND as_of_ts_utc <= ?
        GROUP BY asset_class, venue, symbol, vendor, action_kind, effective_ts_utc
    )
    SELECT c.asset_class, c.venue, c.symbol, c.vendor, c.action_kind,
           c.effective_ts_utc, c.as_of_ts_utc, c.payload_json
    FROM corporate_actions c
    JOIN latest l
      ON c.asset_class = l.asset_class
     AND c.venue       = l.venue
     AND c.symbol      = l.symbol
     AND c.vendor      = l.vendor
     AND c.action_kind = l.action_kind
     AND c.effective_ts_utc = l.effective_ts_utc
     AND c.as_of_ts_utc     = l.pin_as_of
    ORDER BY c.effective_ts_utc
    """
    rows = conn.execute(
        q,
        (asset_class.lower(), venue.lower(), symbol.upper(), vendor, f, t, pin),
    )
    for row in rows:
        yield HistoricalCorporateAction(
            asset_class=row["asset_class"],
            venue=row["venue"],
            symbol=row["symbol"],
            vendor=row["vendor"],
            action_kind=row["action_kind"],
            effective_ts_utc=row["effective_ts_utc"],
            as_of_ts_utc=row["as_of_ts_utc"],
            payload=json.loads(row["payload_json"]),
        )


def iter_events(
    conn: sqlite3.Connection,
    *,
    kind: str,
    vendor: str,
    asset_class: str | None,
    venue: str | None,
    symbol: str | None,
    from_utc: datetime,
    to_utc: datetime,
    as_of_ts_pin: datetime,
) -> Iterator[HistoricalEvent]:
    """Yield events in ascending `event_ts_utc` order, pin-aware. NULL-aware filters."""
    pin = _iso_utc(as_of_ts_pin)
    f = _iso_utc(from_utc)
    t = _iso_utc(to_utc)
    # COALESCE-and-equal makes NULL fields match against an empty string sentinel.
    q = """
    WITH latest AS (
        SELECT kind, vendor,
               COALESCE(asset_class,'') AS ac, COALESCE(venue,'') AS vn,
               COALESCE(symbol,'') AS sy, event_ts_utc,
               MAX(as_of_ts_utc) AS pin_as_of
        FROM event_series
        WHERE kind   = ?
          AND vendor = ?
          AND COALESCE(asset_class,'') = ?
          AND COALESCE(venue,'')       = ?
          AND COALESCE(symbol,'')      = ?
          AND event_ts_utc >= ?
          AND event_ts_utc <  ?
          AND as_of_ts_utc <= ?
        GROUP BY kind, vendor, ac, vn, sy, event_ts_utc
    )
    SELECT e.asset_class, e.venue, e.symbol, e.kind, e.vendor,
           e.event_ts_utc, e.as_of_ts_utc, e.payload_json
    FROM event_series e
    JOIN latest l
      ON e.kind = l.kind
     AND e.vendor = l.vendor
     AND COALESCE(e.asset_class,'') = l.ac
     AND COALESCE(e.venue,'')       = l.vn
     AND COALESCE(e.symbol,'')      = l.sy
     AND e.event_ts_utc = l.event_ts_utc
     AND e.as_of_ts_utc = l.pin_as_of
    ORDER BY e.event_ts_utc
    """
    rows = conn.execute(
        q,
        (
            kind,
            vendor,
            (asset_class or "").lower(),
            (venue or "").lower(),
            (symbol or "").upper(),
            f,
            t,
            pin,
        ),
    )
    for row in rows:
        yield HistoricalEvent(
            kind=row["kind"],
            asset_class=row["asset_class"],
            venue=row["venue"],
            symbol=row["symbol"],
            vendor=row["vendor"],
            event_ts_utc=row["event_ts_utc"],
            as_of_ts_utc=row["as_of_ts_utc"],
            payload=json.loads(row["payload_json"]),
        )


def latest_as_of(
    conn: sqlite3.Connection,
    *,
    asset_class: str,
    venue: str,
    symbol: str,
    kind: str,
    vendor: str,
    bar_open_ts_utc: str,
) -> str | None:
    """Latest `as_of_ts_utc` recorded for one bar key (no pin filter)."""
    row = conn.execute(
        """
        SELECT MAX(as_of_ts_utc) AS pin_as_of
        FROM historical_bars
        WHERE asset_class = ? AND venue = ? AND symbol = ?
          AND kind = ? AND vendor = ? AND bar_open_ts_utc = ?
        """,
        (asset_class.lower(), venue.lower(), symbol.upper(), kind, vendor, bar_open_ts_utc),
    ).fetchone()
    return row["pin_as_of"] if row else None
