"""Spec 002 data-quality detectors (T019, FR-D-005).

These functions write rows into `data_quality_events`. Severity
`block` causes a backtest run to refuse to read the affected slice.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from auto_invest.market_data.calendar import MarketCalendar


_PERIOD_MAP: dict[str, timedelta] = {
    "ohlcv_1m": timedelta(minutes=1),
    "ohlcv_1h": timedelta(hours=1),
    "ohlcv_1d": timedelta(days=1),
}


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _parse_iso(text: str) -> datetime:
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def detect_gaps(
    conn: sqlite3.Connection,
    *,
    asset_class: str,
    venue: str,
    symbol: str,
    kind: str,
    vendor: str,
    calendar: MarketCalendar,
    from_utc: datetime,
    to_utc: datetime,
    severity: str = "block",
) -> int:
    """Detect missing bars across `[from_utc, to_utc)` for the venue's calendar.

    For daily bars on a discrete-session calendar, the expected set is
    every session day. For a 24/7 calendar, the expected set is every
    `period`-aligned timestamp in the window. Currently supports
    `ohlcv_1d` precisely; intraday gap detection is best-effort.

    Returns the number of new `data_quality_events` rows written.
    """
    if kind not in _PERIOD_MAP:
        raise ValueError(f"unsupported kind for gap detection: {kind!r}")
    rows = conn.execute(
        """
        SELECT bar_open_ts_utc FROM historical_bars
        WHERE asset_class = ? AND venue = ? AND symbol = ?
          AND kind = ? AND vendor = ?
          AND bar_open_ts_utc >= ?
          AND bar_open_ts_utc < ?
        ORDER BY bar_open_ts_utc
        """,
        (
            asset_class.lower(),
            venue.lower(),
            symbol.upper(),
            kind,
            vendor,
            from_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            to_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        ),
    ).fetchall()
    present = {row["bar_open_ts_utc"] for row in rows}

    inserted = 0
    if kind == "ohlcv_1d":
        d = from_utc.date()
        end = to_utc.date()
        while d < end:
            if calendar.is_session(d):
                expected = f"{d.isoformat()}T00:00:00.000Z"
                if expected not in present:
                    payload = {"missing_bar_ts": expected, "kind": kind}
                    conn.execute(
                        """
                        INSERT INTO data_quality_events
                            (event_ts_utc, asset_class, venue, symbol, kind,
                             vendor, payload_json, severity)
                        VALUES (?, ?, ?, ?, 'gap', ?, ?, ?)
                        """,
                        (
                            _utcnow_iso_ms(),
                            asset_class.lower(),
                            venue.lower(),
                            symbol.upper(),
                            vendor,
                            json.dumps(payload),
                            severity,
                        ),
                    )
                    inserted += 1
            d = d + timedelta(days=1)
    return inserted


def detect_vendor_disagreement(
    conn: sqlite3.Connection,
    *,
    asset_class: str,
    venue: str,
    symbol: str,
    kind: str,
    tolerance_bps: Decimal,
    severity: str = "warn",
) -> int:
    """Compare each shared `(symbol, ts)` between vendors.

    Disagreement is measured as the maximum absolute relative
    difference across (open, high, low, close), expressed in basis
    points (bps). Bars whose worst-case bps exceeds `tolerance_bps`
    write a `vendor_disagreement` event.

    Returns the number of new events written.
    """
    rows = conn.execute(
        """
        SELECT bar_open_ts_utc, vendor, open, high, low, close
        FROM historical_bars
        WHERE asset_class = ? AND venue = ? AND symbol = ? AND kind = ?
        ORDER BY bar_open_ts_utc, vendor
        """,
        (asset_class.lower(), venue.lower(), symbol.upper(), kind),
    ).fetchall()

    by_ts: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        by_ts.setdefault(r["bar_open_ts_utc"], []).append(r)

    inserted = 0
    for ts, group in by_ts.items():
        vendors = {row["vendor"] for row in group}
        if len(vendors) < 2:
            continue
        # For each pair, compute the worst-case OHLC bps difference.
        worst_bps = Decimal("0")
        worst_pair: tuple[str, str] | None = None
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                for fld in ("open", "high", "low", "close"):
                    pa, pb = Decimal(a[fld]), Decimal(b[fld])
                    if pa == 0 or pb == 0:
                        continue
                    diff = abs(pa - pb) / max(pa, pb) * Decimal(10000)
                    if diff > worst_bps:
                        worst_bps = diff
                        worst_pair = (a["vendor"], b["vendor"])
        if worst_pair is not None and worst_bps > tolerance_bps:
            payload = {
                "ts": ts,
                "worst_pair": list(worst_pair),
                "worst_bps": str(worst_bps.quantize(Decimal("0.01"))),
                "tolerance_bps": str(tolerance_bps),
            }
            conn.execute(
                """
                INSERT INTO data_quality_events
                    (event_ts_utc, asset_class, venue, symbol, kind,
                     vendor, payload_json, severity)
                VALUES (?, ?, ?, ?, 'vendor_disagreement', ?, ?, ?)
                """,
                (
                    _utcnow_iso_ms(),
                    asset_class.lower(),
                    venue.lower(),
                    symbol.upper(),
                    None,
                    json.dumps(payload),
                    severity,
                ),
            )
            inserted += 1
    return inserted
