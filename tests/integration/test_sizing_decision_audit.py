"""Spec 018 슬라이스 2: SIZING_DECISION 감사 기록 통합 테스트.

target_vol / inverse_vol 사이징 룰이 submit_order를 통과할 때
SIZING_DECISION 행이 정확히 1건 기록되는지 확인한다.
fixed/None 모드는 SIZING_DECISION을 기록하지 않는다.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, SizingConfig, TimeTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderRouter
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import audit, db

BASE = "https://api.example"
ACCOUNT = "1234567801"


def _rule(
    *,
    sizing: SizingConfig | None = None,
    symbol: str = "AAPL",
    qty: int = 100,
) -> TradingRule:
    return TradingRule(
        id="size-audit-rule",
        symbol=symbol,
        stage=StrategyStage.CANARY,
        priority=10,
        enabled=True,
        trigger=TimeTrigger(
            at_time="09:00",
            cooldown_seconds=0,
        ),
        action=Action(
            side=Side.BUY,
            order_type=OrderType.MARKET,
            qty=qty,
            limit_price="0",
        ),
        sizing=sizing,
    )


def _whitelist(symbol: str = "AAPL") -> Whitelist:
    return Whitelist(
        symbols={symbol},
        accounts={ACCOUNT},
        order_types=frozenset({OrderType.MARKET, OrderType.LIMIT}),
    )


@asynccontextmanager
async def _router(conn, rules, tmp_path, symbol: str = "AAPL"):
    halt_path = tmp_path / "halt.flag"
    async with httpx.AsyncClient(base_url=BASE) as inner:
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        caps = SizingCaps(
            per_trade_pct=Decimal("5"),
            per_symbol_pct=Decimal("20"),
            global_exposure_pct=Decimal("80"),
            canary_capital_pct=Decimal("5"),
            canary_min_duration_days=10,
            canary_acceptance_drawdown_pct=Decimal("3"),
        )
        router = OrderRouter(
            conn=conn,
            broker=client,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no=ACCOUNT,
            whitelist=_whitelist(symbol),
            caps=caps,
            halt_path=halt_path,
            market="NASD",
            paper_mode=True,
            paper_session_id=42,
        )
        yield router


def _insert_volatile_bars(conn, symbol: str = "AAPL", n: int = 25) -> None:
    for i in range(n):
        price = Decimal("100") if i % 2 == 0 else Decimal("80")
        ts = (datetime(2026, 5, 1, tzinfo=UTC) + timedelta(days=i)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        insert_bar(
            conn,
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=ts,
                open_usd=price,
                high_usd=price,
                low_usd=price,
                close_usd=price,
                volume=1000,
            ),
        )


@pytest.fixture()
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "test.db")
    db.migrate(c)
    yield c
    c.close()


@pytest.mark.asyncio
async def test_sizing_decision_recorded_for_target_vol(conn, tmp_path):
    """target_vol 사이징 → SIZING_DECISION 행 1건 기록."""
    _insert_volatile_bars(conn)
    sizing = SizingConfig(
        mode="target_vol",
        target_volatility_pct=Decimal("2.0"),
        lookback_bars=5,
        min_scale=Decimal("0"),
        max_scale=Decimal("1"),
    )
    rule = _rule(sizing=sizing)
    async with _router(conn, [rule], tmp_path) as router:
        await router.submit_order(
            rule=rule,
            quote_price_usd=Decimal("100"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )

    rows = audit.read_all(conn)
    sizing_rows = [r for r in rows if r["event_type"] == "SIZING_DECISION"]
    assert len(sizing_rows) == 1
    payload = json.loads(sizing_rows[0]["payload_json"])
    assert payload["sizing_mode"] == "target_vol"
    assert payload["base_qty"] == 100
    assert payload["realized_vol_pct"] is not None
    assert payload["vol_scale"] is not None


@pytest.mark.asyncio
async def test_no_sizing_decision_for_fixed_mode(conn, tmp_path):
    """fixed 모드(사이징 없음) → SIZING_DECISION 행 없음."""
    rule = _rule(sizing=None)
    async with _router(conn, [rule], tmp_path) as router:
        await router.submit_order(
            rule=rule,
            quote_price_usd=Decimal("100"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )

    rows = audit.read_all(conn)
    sizing_rows = [r for r in rows if r["event_type"] == "SIZING_DECISION"]
    assert len(sizing_rows) == 0


@pytest.mark.asyncio
async def test_sizing_decision_final_qty_zero_still_recorded(conn, tmp_path):
    """변동성이 너무 높아 final_qty=0이 돼도 SIZING_DECISION은 기록된다."""
    _insert_volatile_bars(conn)
    # min_scale=0, target 0.01% — 아주 낮은 타깃 → 거의 항상 0으로 스로틀
    sizing = SizingConfig(
        mode="target_vol",
        target_volatility_pct=Decimal("0.01"),
        lookback_bars=5,
        min_scale=Decimal("0"),
        max_scale=Decimal("1"),
    )
    rule = _rule(sizing=sizing, qty=1)
    async with _router(conn, [rule], tmp_path) as router:
        await router.submit_order(
            rule=rule,
            quote_price_usd=Decimal("100"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )

    rows = audit.read_all(conn)
    sizing_rows = [r for r in rows if r["event_type"] == "SIZING_DECISION"]
    assert len(sizing_rows) == 1
    payload = json.loads(sizing_rows[0]["payload_json"])
    assert payload["final_qty"] == 0
