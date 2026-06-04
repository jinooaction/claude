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
from datetime import datetime, timedelta
from decimal import Decimal

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.models import Quote
from auto_invest.broker.overseas import get_daily_bars, get_quote
from auto_invest.market_data.quality import QualityReport, assess_quality
from auto_invest.market_data.store import PriceBar, get_bars, insert_bar

DEFAULT_BACKFILL_EXCHANGES: tuple[str, ...] = ("NAS", "NYS", "AMS")


async def _paginate_deep(
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    symbol: str,
    market: str,
    first_page: list,
    min_bars: int,
) -> list:
    """스펙 041 — KIS 기준일(BYMD)을 과거로 돌려 ≥min_bars 최신 일봉을 모은다.

    가장 오래된 세션 −1일을 다음 기준일로 써 더 과거 100세션을 받고, session_date 로 중복을
    제거하며 누적한다. 새 과거 바가 안 나오면(상장 이력 끝) 또는 페이지 한도에 닿으면 멈춘다.
    """
    by_date = {b.session_date: b for b in first_page}
    # 페이지당 ~100세션 → 여유 있게 한도(무한 루프 방지). min_bars 300 ≈ 4페이지.
    max_pages = max(3, min_bars // 80 + 3)
    for _ in range(max_pages):
        if len(by_date) >= min_bars:
            break
        oldest = min(by_date)
        base = (oldest - timedelta(days=1)).strftime("%Y%m%d")
        older = await get_daily_bars(
            client,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            symbol=symbol,
            market=market,
            base_date=base,
        )
        new = [b for b in older if b.session_date not in by_date]
        if not new:  # 더 과거 데이터 없음 → 종료(상장 이력 한계).
            break
        for b in new:
            by_date[b.session_date] = b
    return [by_date[d] for d in sorted(by_date)]


async def backfill_daily_bars(
    conn: sqlite3.Connection,
    client: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    symbols: list[str],
    exchanges: tuple[str, ...] = DEFAULT_BACKFILL_EXCHANGES,
    min_bars: int = 0,
) -> list[dict]:
    """Fetch recent daily OHLCV from KIS into ``price_bars`` (read-only; idempotent).

    For each symbol, tries each KIS EXCD in ``exchanges`` until one returns bars
    (so per-symbol exchange need not be hardcoded), then insert-or-skips each bar
    as a ``1d`` ``PriceBar``. Read-only market data — no order is placed, no money
    moves. Returns ``[{symbol, exchange, fetched, inserted}, ...]``. Shared by the
    `backfill-bars` CLI and the worker's once-per-session refresh.

    스펙 041 — ``min_bars`` > 0 이면 *최신* 일봉을 그만큼 깊게 채운다(KIS 기준일 BYMD 를
    점점 과거로 돌려 페이지네이션). KIS 한 번 호출은 ~100세션만 주므로, 6~12개월 모멘텀에
    필요한 ≥252 바를 얻으려면 여러 페이지가 필요하다. 새 과거 바가 안 나오거나 한도에 닿으면
    멈춘다(중복은 session_date 로 제거). 데이터는 *최신*(오늘 기준 과거로) — 오래된 데이터 아님.
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
        if used is not None and min_bars > 0 and len(bars) < min_bars:
            bars = await _paginate_deep(
                client,
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                symbol=sym,
                market=used,
                first_page=bars,
                min_bars=min_bars,
            )
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
