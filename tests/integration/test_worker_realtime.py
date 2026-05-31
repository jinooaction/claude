"""스펙 031 슬라이스 1 — 워커 시세 소스 폴백 통합 테스트 (SC-031-07).

realtime feed 가 available + 캐시 시세가 있으면 그 시세를, 아니면 REST get_quote 로
폴백한다. realtime_feed=None 이면 항상 REST(byte 동일).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.models import Quote
from auto_invest.config.caps import SizingCaps
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.worker.loop import Worker, WorkerSettings

BASE = "https://api.example"
ACCOUNT = "1234567801"
QUOTE = "/uapi/overseas-price/v1/quotations/price"


class FakeFeed:
    """RealtimeQuoteSource 를 만족하는 가짜 feed."""

    def __init__(self, *, available: bool, quotes: dict[str, Quote]) -> None:
        self._available = available
        self._quotes = quotes

    @property
    def available(self) -> bool:
        return self._available

    def latest_quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(symbol)


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )


def _rt_quote(last: str) -> Quote:
    return Quote(
        symbol="AAPL",
        last_price_usd=Decimal(last),
        bid_usd=None,
        ask_usd=None,
        quoted_at_utc=datetime.now(UTC),
    )


@asynccontextmanager
async def _worker(tmp_path: Path, feed) -> AsyncIterator[Worker]:
    settings = WorkerSettings(
        config=LoadedConfig(
            caps=_caps(),
            whitelist=Whitelist(symbols={"AAPL"}, accounts={ACCOUNT}),
            rules=(),
        ),
        db_path=tmp_path / "t.db",
        halt_path=tmp_path / "halt.flag",
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal("100000"),
        require_session_open=False,
        paper_mode=False,
        realtime_feed=feed,
    )
    async with httpx.AsyncClient(base_url=BASE) as inner:
        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        worker = Worker(
            settings, broker=broker, access_token="tok", app_key="app",
            app_secret="sec", account_no=ACCOUNT,
        )
        try:
            yield worker
        finally:
            worker.close()


def _rest_quote_response() -> httpx.Response:
    return httpx.Response(
        200, json={"output": {"last": "200", "bidp": "199", "askp": "201"}}
    )


@pytest.mark.asyncio
async def test_uses_realtime_quote_when_available(tmp_path: Path) -> None:
    """realtime available + 캐시 시세 → 그 시세 사용, REST 호출 안 함."""
    feed = FakeFeed(available=True, quotes={"AAPL": _rt_quote("150.25")})
    async with _worker(tmp_path, feed) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            rest = mock.get(QUOTE).mock(return_value=_rest_quote_response())
            q = await worker._fetch_quote("AAPL")
        assert q.last_price_usd == Decimal("150.25")
        assert rest.called is False


@pytest.mark.asyncio
async def test_falls_back_to_rest_when_unavailable(tmp_path: Path) -> None:
    """realtime unavailable → REST 폴백."""
    feed = FakeFeed(available=False, quotes={"AAPL": _rt_quote("150.25")})
    async with _worker(tmp_path, feed) as worker:
        with respx.mock(base_url=BASE) as mock:
            rest = mock.get(QUOTE).mock(return_value=_rest_quote_response())
            q = await worker._fetch_quote("AAPL")
        assert rest.called is True
        assert q.last_price_usd == Decimal("200")


@pytest.mark.asyncio
async def test_falls_back_to_rest_when_symbol_missing(tmp_path: Path) -> None:
    """available 이어도 해당 종목 캐시가 없으면 REST 폴백."""
    feed = FakeFeed(available=True, quotes={})  # 캐시 비어 있음.
    async with _worker(tmp_path, feed) as worker:
        with respx.mock(base_url=BASE) as mock:
            rest = mock.get(QUOTE).mock(return_value=_rest_quote_response())
            q = await worker._fetch_quote("AAPL")
        assert rest.called is True
        assert q.last_price_usd == Decimal("200")


@pytest.mark.asyncio
async def test_no_feed_uses_rest(tmp_path: Path) -> None:
    """realtime_feed=None(기본) → 항상 REST(byte 동일)."""
    async with _worker(tmp_path, None) as worker:
        with respx.mock(base_url=BASE) as mock:
            rest = mock.get(QUOTE).mock(return_value=_rest_quote_response())
            q = await worker._fetch_quote("AAPL")
        assert rest.called is True
        assert q.last_price_usd == Decimal("200")
