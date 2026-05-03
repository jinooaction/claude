"""Performance smoke test (T060).

Verifies that trigger evaluation stays under the latency budget the
plan declares: trigger-eval p95 < 1 s for ~20 active rules.

The test stubs the broker (no network) and uses synthetic
PriceTrigger conditions that always fail, so each tick exercises:
  * 20x quote fetch (mocked)
  * 20x trigger evaluation
  * 20x bar persistence

with no order routing — exactly the steady-state cost the worker
pays during a quiet session.
"""

from __future__ import annotations

import time
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
from auto_invest.worker.loop import Worker, WorkerSettings

BASE = "https://api.example"


def _rule(symbol: str) -> TradingRule:
    return TradingRule(
        id=f"{symbol.lower()}-rule",
        symbol=symbol,
        stage=StrategyStage.CANARY,
        priority=10,
        enabled=True,
        # Trigger threshold below the mocked price so the trigger never fires.
        trigger=PriceTrigger(direction="<=", threshold=Decimal("1"), cooldown_seconds=60),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=1, limit_price="1.00"),
    )


@asynccontextmanager
async def _worker(tmp_path: Path, n_rules: int) -> AsyncIterator[Worker]:
    symbols = [f"SYM{i:02d}" for i in range(n_rules)]
    rules = [_rule(s) for s in symbols]
    config = LoadedConfig(
        caps=SizingCaps(
            per_trade_pct=Decimal("5"),
            per_symbol_pct=Decimal("20"),
            global_exposure_pct=Decimal("80"),
            canary_capital_pct=Decimal("5"),
            canary_min_duration_days=10,
            canary_acceptance_drawdown_pct=Decimal("3"),
        ),
        whitelist=Whitelist(symbols=set(symbols), accounts={"acct-1"}),
        rules=tuple(rules),
    )
    settings = WorkerSettings(
        config=config,
        db_path=tmp_path / "t.db",
        halt_path=tmp_path / "halt.flag",
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal("100000"),
        require_session_open=False,
    )
    async with httpx.AsyncClient(base_url=BASE) as inner:
        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=1000.0, capacity=100.0),
            breaker=CircuitBreaker(failure_threshold=10, cooldown_seconds=10.0),
            max_retries=1,
        )
        worker = Worker(
            settings,
            broker=broker,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no="acct-1",
        )
        try:
            yield worker
        finally:
            worker.close()


@pytest.mark.asyncio
async def test_trigger_eval_p95_under_one_second(tmp_path: Path):
    """20 rules, 30 ticks; per-tick p95 must stay under 1 s."""
    n_rules = 20
    n_ticks = 30
    durations: list[float] = []

    async with _worker(tmp_path, n_rules) as worker:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-price/v1/quotations/price").mock(
                return_value=httpx.Response(
                    200,
                    json={"output": {"last": "100.00", "bidp": "99.99", "askp": "100.01"}},
                )
            )
            now = datetime(2026, 6, 3, 15, 0, tzinfo=UTC)
            for _ in range(n_ticks):
                start = time.perf_counter()
                report = await worker.tick(now)
                durations.append(time.perf_counter() - start)
                assert report.rules_evaluated == n_rules
                assert report.rules_fired == 0

    durations.sort()
    p95 = durations[int(len(durations) * 0.95)]
    median = durations[len(durations) // 2]
    assert p95 < 1.0, (
        f"Trigger-eval p95 = {p95:.3f}s exceeds 1s budget "
        f"(median {median:.3f}s; n_rules={n_rules}, ticks={n_ticks})"
    )
