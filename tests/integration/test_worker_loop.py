"""Integration tests for the worker loop (T045)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.rules import (
    Action,
    PriceTrigger,
    TradingRule,
)
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import audit
from auto_invest.worker.halt import set_halt
from auto_invest.worker.loop import Worker, WorkerSettings

BASE = "https://api.example"
ACCOUNT = "1234567801"


def _config(symbols: set[str], rules: list[TradingRule]) -> LoadedConfig:
    return LoadedConfig(
        caps=SizingCaps(
            per_trade_pct=Decimal("5"),
            per_symbol_pct=Decimal("20"),
            global_exposure_pct=Decimal("80"),
            canary_capital_pct=Decimal("5"),
            canary_min_duration_days=10,
            canary_acceptance_drawdown_pct=Decimal("3"),
        ),
        whitelist=Whitelist(symbols=symbols, accounts={ACCOUNT}),
        rules=tuple(rules),
    )


def _rule(*, symbol: str = "AAPL", qty: int = 5,
          threshold: str = "100") -> TradingRule:
    return TradingRule(
        id=f"{symbol.lower()}-rule",
        symbol=symbol,
        stage=StrategyStage.CANARY,
        priority=10,
        enabled=True,
        trigger=PriceTrigger(
            direction="<=",
            threshold=Decimal(threshold),
            cooldown_seconds=60,
        ),
        action=Action(
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            qty=qty,
            limit_price="100.00",
        ),
    )


@asynccontextmanager
async def _worker(
    tmp_path: Path,
    *,
    rules: list[TradingRule],
    halt_set: bool = False,
    require_session_open: bool = False,
) -> AsyncIterator[Worker]:
    halt_path = tmp_path / "halt.flag"
    if halt_set:
        set_halt(halt_path, "test halt")
    settings = WorkerSettings(
        config=_config(symbols={r.symbol for r in rules}, rules=rules),
        db_path=tmp_path / "t.db",
        halt_path=halt_path,
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal("10000"),
        require_session_open=require_session_open,
    )
    async with httpx.AsyncClient(base_url=BASE) as inner:
        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        worker = Worker(
            settings,
            broker=broker,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no=ACCOUNT,
        )
        try:
            yield worker
        finally:
            worker.close()


# ----------------------------------------------------------- skip predicates


@pytest.mark.asyncio
async def test_tick_skips_when_halted(tmp_path: Path):
    async with _worker(tmp_path, rules=[_rule()], halt_set=True) as worker:
        report = await worker.tick(datetime(2026, 6, 3, 15, 0, tzinfo=UTC))
    assert report.skipped_reason == "halt_flag_set"
    assert report.rules_evaluated == 0


@pytest.mark.asyncio
async def test_tick_skips_when_session_closed(tmp_path: Path):
    async with _worker(
        tmp_path, rules=[_rule()], require_session_open=True
    ) as worker:
        # Saturday — session closed.
        report = await worker.tick(datetime(2024, 6, 8, 15, 0, tzinfo=UTC))
    assert report.skipped_reason == "session_closed"


# ----------------------------------------------------------- happy path


@pytest.mark.asyncio
async def test_tick_fires_rule_and_routes_order(tmp_path: Path):
    rule = _rule(threshold="200")  # always fires when quote <= 200
    async with _worker(tmp_path, rules=[rule]) as worker:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-price/v1/quotations/price").mock(
                return_value=httpx.Response(
                    200,
                    json={"output": {"last": "150.00", "bidp": "149.99",
                                     "askp": "150.01"}},
                )
            )
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ODNO": "K-001"}}
                )
            )

            report = await worker.tick(
                datetime(2026, 6, 3, 15, 0, tzinfo=UTC)
            )

        assert report.skipped_reason is None
        assert report.rules_evaluated == 1
        assert report.rules_fired == 1
        assert report.outcomes[0].state == "SUBMITTED"

        events = [r["event_type"] for r in audit.read_all(worker.conn)]
        assert "ORDER_INTENT" in events
        assert "ORDER_SUBMITTED" in events


# ----------------------------------------------------------- non-firing trigger


@pytest.mark.asyncio
async def test_tick_does_not_fire_when_price_above_threshold(tmp_path: Path):
    rule = _rule(threshold="100")  # quote 150 > 100 -> no fire
    async with _worker(tmp_path, rules=[rule]) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            mock.get("/uapi/overseas-price/v1/quotations/price").mock(
                return_value=httpx.Response(
                    200,
                    json={"output": {"last": "150.00", "bidp": "149.99",
                                     "askp": "150.01"}},
                )
            )
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ODNO": "x"}}
                )
            )

            report = await worker.tick(
                datetime(2026, 6, 3, 15, 0, tzinfo=UTC)
            )

        assert report.rules_evaluated == 1
        assert report.rules_fired == 0
        assert placed.call_count == 0


# ----------------------------------------------------------- cooldown


@pytest.mark.asyncio
async def test_cooldown_suppresses_refire(tmp_path: Path):
    rule = _rule(threshold="200")
    async with _worker(tmp_path, rules=[rule]) as worker:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-price/v1/quotations/price").mock(
                return_value=httpx.Response(
                    200,
                    json={"output": {"last": "150.00", "bidp": "149.99",
                                     "askp": "150.01"}},
                )
            )
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ODNO": "K-001"}}
                )
            )

            now = datetime(2026, 6, 3, 15, 0, tzinfo=UTC)
            await worker.tick(now)
            # Second tick within cooldown — should not re-fire.
            report = await worker.tick(
                datetime(2026, 6, 3, 15, 0, 30, tzinfo=UTC)
            )

        assert report.rules_fired == 0
        assert placed.call_count == 1


# ----------------------------------------------------------- lifecycle audit


@pytest.mark.asyncio
async def test_record_start_writes_lifecycle_rows(tmp_path: Path):
    rule = _rule()
    async with _worker(tmp_path, rules=[rule]) as worker:
        worker.record_start(secret_keys=["KIS_APP_KEY"])
        worker.record_stop("test_complete")

        events = [r["event_type"] for r in audit.read_all(worker.conn)]
        assert events == [
            "SECRETS_LOADED",
            "WORKER_STARTED",
            "RULE_LOAD",
            "WORKER_STOPPED",
        ]
