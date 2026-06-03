"""스펙 033 — 워커 틱 일일 백필 (price_bars 신선 유지, 읽기 전용)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.config.caps import SizingCaps
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.market_data.store import bar_summary
from auto_invest.worker.loop import _BACKFILL_GAP_SECONDS, Worker, WorkerSettings

BASE = "https://api.example"
ACCOUNT = "1234567801"


def _config(symbols: set[str]) -> LoadedConfig:
    return LoadedConfig(
        caps=SizingCaps(
            per_trade_pct=Decimal("5"), per_symbol_pct=Decimal("20"),
            global_exposure_pct=Decimal("80"), canary_capital_pct=Decimal("5"),
            canary_min_duration_days=10, canary_acceptance_drawdown_pct=Decimal("3"),
        ),
        whitelist=Whitelist(symbols=symbols, accounts={ACCOUNT}),
        rules=(),
    )


def _make_worker(tmp_path: Path, *, backfill_enabled: bool, inner: httpx.AsyncClient) -> Worker:
    settings = WorkerSettings(
        config=_config({"AAPL", "MSFT"}),
        db_path=tmp_path / "t.db",
        halt_path=tmp_path / "halt.flag",
        config_path=tmp_path / "r.toml",
        total_capital_usd=Decimal("10000"),
        require_session_open=False,
        backfill_enabled=backfill_enabled,
        backfill_exchanges=("NAS",),
    )
    broker = ResilientClient(
        inner,
        rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
        max_retries=1,
    )
    return Worker(settings, broker=broker, access_token="tok", app_key="app",
                  app_secret="sec", account_no=ACCOUNT)


_PAYLOAD = {"output2": [
    {"xymd": "20260601", "open": "100", "high": "101", "low": "99", "clos": "100", "tvol": "1000"},
    {"xymd": "20260602", "open": "100", "high": "102", "low": "100", "clos": "101", "tvol": "1200"},
]}


@pytest.mark.asyncio
@respx.mock
async def test_worker_run_backfill_populates_price_bars(tmp_path: Path):
    respx.get(url__regex=r".*/quotations/dailyprice.*").mock(
        return_value=httpx.Response(200, json=_PAYLOAD)
    )
    async with httpx.AsyncClient(base_url=BASE) as inner:
        w = _make_worker(tmp_path, backfill_enabled=True, inner=inner)
        try:
            assert w._should_backfill_bars(datetime.now(UTC)) is True  # enabled + last None
            await w._run_backfill_bars()
            for sym in ("AAPL", "MSFT"):
                n, _lo, _hi = bar_summary(w.conn, symbol=sym, timeframe="1d")
                assert n == 2, sym
        finally:
            w.close()


@pytest.mark.asyncio
async def test_worker_backfill_disabled_is_noop(tmp_path: Path):
    async with httpx.AsyncClient(base_url=BASE) as inner:
        w = _make_worker(tmp_path, backfill_enabled=False, inner=inner)
        try:
            assert w._should_backfill_bars(datetime.now(UTC)) is False
        finally:
            w.close()


@pytest.mark.asyncio
async def test_worker_backfill_cadence_gate(tmp_path: Path):
    now = datetime.now(UTC)
    async with httpx.AsyncClient(base_url=BASE) as inner:
        w = _make_worker(tmp_path, backfill_enabled=True, inner=inner)
        try:
            w._last_backfill_at = now
            # 직후엔 막힘, gap 경과 후 허용.
            assert w._should_backfill_bars(now + timedelta(seconds=10)) is False
            assert w._should_backfill_bars(
                now + timedelta(seconds=_BACKFILL_GAP_SECONDS + 1)
            ) is True
        finally:
            w.close()
