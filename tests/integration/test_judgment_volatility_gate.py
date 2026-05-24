"""Spec 004 T013 [US1] — volatility 자문이 order_router 에서 결정론적으로 소비되고
K1 포지션 캡이 자문과 무관하게 그대로 바인딩되는지 검증.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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
from auto_invest.config.rules import Action, JudgmentConfig, PriceTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderRouter
from auto_invest.judgment.schemas import VolatilityAdvisory
from auto_invest.persistence import audit, db

BASE = "https://api.example"
ACCOUNT = "1234567801"


def _rule(
    *,
    qty: int = 10,
    stage: StrategyStage = StrategyStage.CANARY,
    judgment: JudgmentConfig | None = None,
) -> TradingRule:
    return TradingRule(
        id="vol-rule",
        symbol="AAPL",
        stage=stage,
        priority=10,
        enabled=True,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=60),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=qty, limit_price="10.00"),
        judgment=judgment
        or JudgmentConfig(enabled=True, halt_min_confidence=0.7, size_down_factor=0.5),
    )


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )


@asynccontextmanager
async def _router(tmp_path: Path) -> AsyncIterator[OrderRouter]:
    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)
    async with httpx.AsyncClient(base_url=BASE) as inner:
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        yield OrderRouter(
            conn=conn,
            broker=client,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no=ACCOUNT,
            whitelist=Whitelist(symbols={"AAPL"}, accounts={ACCOUNT}),
            caps=_caps(),
            halt_path=tmp_path / "halt.flag",
            market="NASD",
        )
    conn.close()


async def _submit(router: OrderRouter, rule: TradingRule, advisory, **over):
    return await router.submit_order(
        rule=rule,
        quote_price_usd=Decimal("10"),
        total_capital_usd=Decimal("10000"),
        current_symbol_exposure_usd=Decimal("0"),
        current_global_exposure_usd=Decimal("0"),
        volatility_advisory=advisory,
        judgment_correlation_id=over.get("jcid", "jcid-1"),
    )


@pytest.mark.asyncio
async def test_size_down_reduces_qty(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-1"}})
            )
            advisory = VolatilityAdvisory(action="size_down", confidence=0.6, reason="vol up")
            outcome = await _submit(router, _rule(qty=10), advisory)
        assert outcome.state == "SUBMITTED"
        # qty 10 * 0.5 = 5 — order 행에 축소된 수량이 기록된다.
        order_row = router.conn.execute("SELECT qty FROM orders").fetchone()
        assert order_row["qty"] == 5
        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert "JUDGMENT_ADVISORY_APPLIED" in events


@pytest.mark.asyncio
async def test_halt_high_confidence_skips_order(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )
            advisory = VolatilityAdvisory(action="halt", confidence=0.95, reason="crash")
            outcome = await _submit(router, _rule(qty=10), advisory)
        assert outcome.state == "SKIPPED_BY_JUDGMENT"
        assert placed.call_count == 0  # broker 도달 안 함
        applied = [
            r for r in audit.read_all(router.conn)
            if r["event_type"] == "JUDGMENT_ADVISORY_APPLIED"
        ]
        assert applied and "skip" in applied[0]["payload_json"]


@pytest.mark.asyncio
async def test_halt_low_confidence_no_effect(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-2"}})
            )
            # confidence 0.5 < halt_min_confidence 0.7 → 무효과, 정상 주문.
            advisory = VolatilityAdvisory(action="halt", confidence=0.5, reason="maybe")
            outcome = await _submit(router, _rule(qty=10), advisory)
        assert outcome.state == "SUBMITTED"
        order_row = router.conn.execute("SELECT qty FROM orders").fetchone()
        assert order_row["qty"] == 10  # 변동 없음


@pytest.mark.asyncio
async def test_determinism_same_advisory_same_decision(tmp_path: Path):
    advisory = VolatilityAdvisory(action="size_down", confidence=0.6, reason="x")
    qtys = []
    for _ in range(2):
        sub = tmp_path / f"r{_}"
        sub.mkdir()
        async with _router(sub) as router:
            with respx.mock(base_url=BASE) as mock:
                mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                    return_value=httpx.Response(200, json={"output": {"ODNO": "K"}})
                )
                await _submit(router, _rule(qty=8), advisory)
            qtys.append(router.conn.execute("SELECT qty FROM orders").fetchone()["qty"])
    assert qtys[0] == qtys[1] == 4  # 8*0.5, 두 번 다 동일


@pytest.mark.asyncio
async def test_full_live_stage_ignores_advisory(tmp_path: Path):
    """헌법 VI — 캐너리 코호트만 자문 반영. FULL_LIVE 는 v1 동작."""
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-3"}})
            )
            advisory = VolatilityAdvisory(action="halt", confidence=0.99, reason="crash")
            rule = _rule(qty=10, stage=StrategyStage.FULL_LIVE)
            outcome = await _submit(router, rule, advisory)
        assert outcome.state == "SUBMITTED"  # halt 무시됨 (캐너리 아님)
        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert "JUDGMENT_ADVISORY_APPLIED" not in events


@pytest.mark.asyncio
async def test_k1_cap_still_binds_after_advisory(tmp_path: Path):
    """자문이 size_down 해도, 남은 수량이 per-trade 캡을 넘으면 K1 게이트가 거부.
    자문은 노출을 줄일 뿐 캡을 우회시키지 못한다."""
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )
            # qty 200 * price 10 = 2000; size_down 0.5 → 100*10 = 1000 > per_trade cap 500.
            advisory = VolatilityAdvisory(action="size_down", confidence=0.6, reason="x")
            outcome = await router.submit_order(
                rule=_rule(qty=200),
                quote_price_usd=Decimal("10"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
                volatility_advisory=advisory,
                judgment_correlation_id="jcid-k1",
            )
        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "per_trade_cap_gate"
        assert placed.call_count == 0
        # 자문은 게이트 전에 소비됐으나(축소 기록) K1 캡이 그대로 거부했다.
        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert "JUDGMENT_ADVISORY_APPLIED" in events
