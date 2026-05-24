"""Spec 004 T014 [US1] — LLM 이 항상 실패해도 거래 경로가 v1 처럼 동작(0건 막힘)하고
JUDGMENT_FALLBACK 이 기록되는지 검증 (SC-001).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, JudgmentConfig, PriceTrigger, TradingRule
from auto_invest.judgment.client import JudgmentClient
from auto_invest.judgment.runner import VolatilityJudgmentRunner
from auto_invest.persistence import audit, db
from auto_invest.telemetry.prices import load_prices


@dataclass
class _Bar:
    close_usd: Decimal


def _bars() -> tuple[_Bar, ...]:
    return tuple(_Bar(close_usd=Decimal(p)) for p in ("100", "104", "98", "106"))


def _rule() -> TradingRule:
    return TradingRule(
        id="vol-rule",
        symbol="AAPL",
        stage=StrategyStage.CANARY,
        priority=10,
        enabled=True,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=60),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=10, limit_price="100.00"),
        judgment=JudgmentConfig(enabled=True, volatility_threshold=0.0),
    )


class _ExplodingMessages:
    async def create(self, **kwargs: Any):
        raise RuntimeError("anthropic down")


class _ExplodingClient:
    def __init__(self) -> None:
        self.messages = _ExplodingMessages()


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
async def test_failure_returns_none_and_records_fallback(conn, prices):
    runner = VolatilityJudgmentRunner(
        client=JudgmentClient(_ExplodingClient(), conn=conn, prices=prices),
        conn=conn,
    )
    advisory, cid = await runner.assess(_rule(), _bars(), current_price=Decimal("99"))
    # 자문 없음 → 거래 루프는 v1 동작(폴백).
    assert advisory is None
    # 폴백 사실이 감사에 남는다.
    fb = [r for r in audit.read_all(conn) if r["event_type"] == "JUDGMENT_FALLBACK"]
    assert fb and "failure" in fb[0]["payload_json"]


@pytest.mark.asyncio
async def test_failed_call_still_audited_as_llm_call(conn, prices):
    """TokenMeter 는 실패 호출도 error_class 와 함께 기록한다."""
    runner = VolatilityJudgmentRunner(
        client=JudgmentClient(_ExplodingClient(), conn=conn, prices=prices),
        conn=conn,
    )
    await runner.assess(_rule(), _bars(), current_price=Decimal("99"))
    llm = [r for r in audit.read_all(conn) if r["event_type"] == "LLM_CALL"]
    assert llm  # 실패해도 LLM_CALL 행 존재
    tu = conn.execute("SELECT error_class FROM token_usage").fetchone()
    assert tu["error_class"] == "RuntimeError"


@pytest.mark.asyncio
async def test_disabled_judgment_makes_no_call(conn, prices):
    """judgment 비활성 룰은 LLM 을 전혀 부르지 않는다 (v1)."""
    rule = TradingRule(
        id="r",
        symbol="AAPL",
        stage=StrategyStage.CANARY,
        priority=1,
        enabled=True,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("100"), cooldown_seconds=60),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=1, limit_price="1.00"),
        judgment=None,
    )
    runner = VolatilityJudgmentRunner(
        client=JudgmentClient(_ExplodingClient(), conn=conn, prices=prices),
        conn=conn,
    )
    advisory, cid = await runner.assess(rule, _bars(), current_price=Decimal("99"))
    assert advisory is None
    assert conn.execute("SELECT COUNT(*) c FROM token_usage").fetchone()["c"] == 0
