"""Market data feed glue (FR-016, FR-017).

Pulls quotes and bars via `broker/overseas.py`, persists through
`store.py`, and runs `quality.py` to decide if a symbol is armed.

Note on the v1 surface: KIS exposes overseas-equity quotes through a
single REST endpoint that returns the *current* price. Indicator-based
rules can accumulate a synthetic OHLC history (`store_synthetic_bar`,
one quote per poll), but spec 033 adds `backfill_daily_bars` here, which
pulls REAL daily OHLCV history from KIS 기간별시세 — the preferred source
when available (synthetic bars remain a fallback for the canary slice).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.models import Quote
from auto_invest.broker.overseas import get_daily_bars, get_quote
from auto_invest.market_data.quality import QualityReport, assess_quality
from auto_invest.market_data.store import PriceBar, get_bars, insert_bar

DEFAULT_BACKFILL_EXCHANGES: tuple[str, ...] = ("NAS", "NYS", "AMS")


async def backfill_daily_bars(
    conn: sqlite3.Connection,
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    symbols: list[str],
    exchanges: tuple[str, ...] = DEFAULT_BACKFILL_EXCHANGES,
) -> list[dict]:
    """Fetch recent daily OHLCV from KIS into ``price_bars`` (read-only; idempotent).

    For each symbol, tries each KIS EXCD in ``exchanges`` until one returns bars
    (so per-symbol exchange need not be hardcoded), then insert-or-skips each bar
    as a ``1d`` ``PriceBar``. Read-only market data — no order is placed, no money
    moves. Returns ``[{symbol, exchange, fetched, inserted}, ...]``. Shared by the
    `backfill-bars` CLI and the worker's once-per-session refresh.
    """
    out: list[dict] = []
    for sym in symbols:
        bars: list = []
        used: str | None = None
        for excd in exchanges:
            bars = await get_daily_bars(
                client,
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                symbol=sym,
                market=excd,
            )
            if bars:
                used = excd
                break
        inserted = 0
        for b in bars:
            pb = PriceBar(
                symbol=b.symbol,
                timeframe="1d",
                bar_open_utc=f"{b.session_date.isoformat()}T00:00:00.000Z",
                open_usd=b.open,
                high_usd=b.high,
                low_usd=b.low,
                close_usd=b.close,
                volume=b.volume,
            )
            if insert_bar(conn, pb):
                inserted += 1
        out.append(
            {"symbol": sym, "exchange": used, "fetched": len(bars), "inserted": inserted}
        )
    return out


async def fetch_quote(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    symbol: str,
    market: str = "NAS",
) -> Quote:
    """Pure broker call; no persistence."""
    return await get_quote(
        client,
        access_token=access_token,
        app_key=app_key,
        app_secret=app_secret,
        symbol=symbol,
        market=market,
    )


def store_synthetic_bar(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
    bar_open_utc: str,
    last_price_usd: Decimal,
    volume: int = 0,
) -> bool:
    """Persist a synthetic single-tick bar derived from a quote.

    Open == high == low == close == last_price. A future iteration
    swaps this for the real bar-history endpoint; the indicator
    facade does not care which path produced the bar.
    """
    bar = PriceBar(
        symbol=symbol,
        timeframe=timeframe,
        bar_open_utc=bar_open_utc,
        open_usd=last_price_usd,
        high_usd=last_price_usd,
        low_usd=last_price_usd,
        close_usd=last_price_usd,
        volume=volume,
    )
    return insert_bar(conn, bar)


def assess_symbol_quality(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
    now: datetime,
    min_bars: int = 1,
) -> QualityReport:
    """Read bar history for the symbol/timeframe and run the quality check."""
    bars = get_bars(conn, symbol=symbol, timeframe=timeframe)
    return assess_quality(bars, timeframe=timeframe, now=now, min_bars=min_bars)
