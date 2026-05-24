"""Spec 004 T024 [US3] — news_screen 스탠스 소비(bear+고신뢰 → 당일 신규 매수 보류),
결정성, 공급원 부재 비활성, LLM 실패 neutral 폴백.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

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
from auto_invest.judgment.client import JudgmentClient
from auto_invest.judgment.points.news_screen import screen_headline
from auto_invest.judgment.schemas import NewsAdvisory
from auto_invest.persistence import audit, db
from auto_invest.telemetry.prices import load_prices

BASE = "https://api.example"
ACCOUNT = "1234567801"


def _rule(stage: StrategyStage = StrategyStage.CANARY) -> TradingRule:
    return TradingRule(
        id="news-rule",
        symbol="AAPL",
        stage=stage,
        priority=10,
        enabled=True,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=60),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=5, limit_price="10.00"),
        judgment=JudgmentConfig(enabled=True, block_min_confidence=0.8),
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
            caps=SizingCaps(
                per_trade_pct=Decimal("50"),
                per_symbol_pct=Decimal("80"),
                global_exposure_pct=Decimal("90"),
                canary_capital_pct=Decimal("5"),
                canary_min_duration_days=10,
                canary_acceptance_drawdown_pct=Decimal("3"),
            ),
            halt_path=tmp_path / "halt.flag",
            market="NASD",
        )
    conn.close()


@pytest.mark.asyncio
async def test_bear_high_confidence_blocks_buy(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )
            advisory = NewsAdvisory(stance="bear", confidence=0.9)
            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("10"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
                news_advisory=advisory,
                news_correlation_id="ncid-1",
            )
        assert outcome.state == "SKIPPED_BY_JUDGMENT"
        assert outcome.reason == "news_block_buy"
        assert placed.call_count == 0


@pytest.mark.asyncio
async def test_bear_low_confidence_allows_buy(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-1"}})
            )
            advisory = NewsAdvisory(stance="bear", confidence=0.5)  # < 0.8
            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("10"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
                news_advisory=advisory,
                news_correlation_id="ncid-2",
            )
        assert outcome.state == "SUBMITTED"


@pytest.mark.asyncio
async def test_bull_stance_allows_buy(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-2"}})
            )
            advisory = NewsAdvisory(stance="bull", confidence=0.95)
            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("10"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
                news_advisory=advisory,
                news_correlation_id="ncid-3",
            )
        assert outcome.state == "SUBMITTED"


# ---- judgment point parse + fallback (screen_headline) ----


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _Resp:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]
        self.model = "claude-haiku-4-5-20251001"
        self.usage = {
            "input_tokens": 50,
            "output_tokens": 10,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }


class _Messages:
    def __init__(self, *, text=None, exc=None) -> None:
        self._text = text
        self._exc = exc

    async def create(self, **kwargs: Any):
        if self._exc:
            raise self._exc
        return _Resp(self._text)


class _Client:
    def __init__(self, **kw: Any) -> None:
        self.messages = _Messages(**kw)


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def prices():
    return load_prices(Path("config/llm_prices.toml"))


@pytest.mark.asyncio
async def test_no_headline_source_disabled(conn, prices):
    jc = JudgmentClient(
        _Client(text='{"stance":"bear","confidence":0.9}'), conn=conn, prices=prices
    )
    advisory, cid = await screen_headline(jc, conn=conn, symbol="AAPL", headline=None)
    assert advisory is None
    # 공급원 부재 → 호출 안 함 → token_usage 없음.
    assert conn.execute("SELECT COUNT(*) c FROM token_usage").fetchone()["c"] == 0


@pytest.mark.asyncio
async def test_failure_falls_back_neutral(conn, prices):
    jc = JudgmentClient(_Client(exc=RuntimeError("boom")), conn=conn, prices=prices)
    advisory, cid = await screen_headline(
        jc, conn=conn, symbol="AAPL", headline="AAPL recalls product"
    )
    assert advisory is None  # neutral 폴백
    fb = [r for r in audit.read_all(conn) if r["event_type"] == "JUDGMENT_FALLBACK"]
    assert fb and "failure" in fb[0]["payload_json"]


@pytest.mark.asyncio
async def test_success_parses_stance(conn, prices):
    jc = JudgmentClient(
        _Client(text='{"stance":"bear","confidence":0.88}'), conn=conn, prices=prices
    )
    advisory, cid = await screen_headline(
        jc, conn=conn, symbol="AAPL", headline="AAPL faces probe"
    )
    assert advisory is not None
    assert advisory.stance == "bear"
    assert cid is not None
