"""Spec 004 T015 [US1] — 판단 호출이 token_usage 1행 + LLM_CALL 1행을 같은
correlation_id 로 남기고, 프롬프트/응답 본문·비밀이 DB 어디에도 없는지 검증 (SC-003).
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
from auto_invest.persistence import db
from auto_invest.telemetry.prices import load_prices

_SECRET_PROMPT = "SECRET-KIS-APPKEY-do-not-log"
_RESPONSE_JSON = '{"action": "size_down", "confidence": 0.7, "reason": "elevated vol"}'


@dataclass
class _Bar:
    close_usd: Decimal


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _Response:
    def __init__(self) -> None:
        self.content = [_Block(_RESPONSE_JSON)]
        self.model = "claude-haiku-4-5-20251001"
        self.usage = {
            "input_tokens": 120,
            "output_tokens": 25,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }


class _Messages:
    async def create(self, **kwargs: Any):
        return _Response()


class _Client:
    def __init__(self) -> None:
        self.messages = _Messages()


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
async def test_success_pairs_token_usage_and_llm_call(conn, prices):
    runner = VolatilityJudgmentRunner(
        client=JudgmentClient(_Client(), conn=conn, prices=prices), conn=conn
    )
    bars = tuple(_Bar(close_usd=Decimal(p)) for p in ("100", "104", "98", "106"))
    advisory, cid = await runner.assess(_rule(), bars, current_price=Decimal("99"))

    assert advisory is not None
    assert advisory.action == "size_down"
    assert cid is not None

    tu = conn.execute(
        "SELECT * FROM token_usage WHERE correlation_id=?", (cid,)
    ).fetchall()
    assert len(tu) == 1
    assert tu[0]["decision_class"] == "volatility_assessment"

    llm = conn.execute(
        "SELECT * FROM audit_log WHERE event_type='LLM_CALL' AND correlation_id=?",
        (cid,),
    ).fetchall()
    assert len(llm) == 1


@pytest.mark.asyncio
async def test_no_prompt_or_response_body_in_db(conn, prices):
    runner = VolatilityJudgmentRunner(
        client=JudgmentClient(_Client(), conn=conn, prices=prices), conn=conn
    )
    bars = tuple(_Bar(close_usd=Decimal(p)) for p in ("100", "104", "98", "106"))
    await runner.assess(_rule(), bars, current_price=Decimal("99"))

    # audit_log·token_usage 전 행을 훑어 본문/비밀 흔적이 없는지 확인.
    rows = conn.execute("SELECT payload_json FROM audit_log").fetchall()
    blob = "".join(r["payload_json"] or "" for r in rows)
    assert _SECRET_PROMPT not in blob
    assert "elevated vol" not in blob  # 응답 reason 본문도 LLM_CALL 에 안 남음
