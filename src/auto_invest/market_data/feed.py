"""Market data feed glue (FR-016, FR-017).

Pulls quotes and bars via `broker/overseas.py`, persists through
`store.py`, and runs `quality.py` to decide if a symbol is armed.

Note on the v1 surface: KIS exposes overseas-equity quotes through a
single REST endpoint that returns the *current* price. Until we wire
in the dedicated bar-history endpoint, indicator-based rules
accumulate a synthetic OHLC history by capturing one quote per
poll into a single bar (open=high=low=close=last_price). This is
adequate for the canary slice and explicit in the docstring of
`store_synthetic_bar` so the limitation is reviewable.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.models import Quote
from auto_invest.broker.overseas import get_quote
from auto_invest.market_data.quality import QualityReport, assess_quality
from auto_invest.market_data.store import PriceBar, get_bars, insert_bar


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
