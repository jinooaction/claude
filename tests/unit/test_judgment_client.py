"""Spec 004 T005 — 견고한 Anthropic 판단 클라이언트 (헌법 VII)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from auto_invest.broker.client import CircuitBreaker
from auto_invest.judgment.client import JudgmentClient
from auto_invest.persistence import db
from auto_invest.telemetry.prices import load_prices


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "test.db"
    c = db.get_connection(path)
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def prices():
    return load_prices(Path("config/llm_prices.toml"))


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _Response:
    def __init__(self, text: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self.content = [_Block(text)]
        self.model = model
        self.usage = {
            "input_tokens": 100,
            "output_tokens": 30,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }


class _FakeMessages:
    def __init__(self, *, response=None, exc=None, delay=0.0) -> None:
        self._response = response
        self._exc = exc
        self._delay = delay

    async def create(self, **kwargs: Any):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc is not None:
            raise self._exc
        return self._response


class _FakeClient:
    def __init__(self, **kwargs: Any) -> None:
        self.messages = _FakeMessages(**kwargs)


async def _call(client, conn, prices, **overrides):
    jc = JudgmentClient(client, conn=conn, prices=prices, **overrides.pop("client_kwargs", {}))
    return await jc.call(
        decision_class=overrides.get("decision_class", "volatility_assessment"),
        system_prompt="sys",
        user_prompt="user",
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
        latency_budget_ms=overrides.get("latency_budget_ms", 2000),
        correlation_id=overrides.get("correlation_id"),
    )


@pytest.mark.asyncio
async def test_success_records_both_rows(conn: sqlite3.Connection, prices: Any):
    client = _FakeClient(
        response=_Response('{"action": "hold", "confidence": 0.5, "reason": "ok"}')
    )
    result = await _call(client, conn, prices, correlation_id="cid-ok")
    assert result.ok is True
    assert result.text and "hold" in result.text
    assert result.cost_usd > 0

    tu = conn.execute("SELECT * FROM token_usage WHERE correlation_id='cid-ok'").fetchone()
    assert tu is not None
    assert tu["decision_class"] == "volatility_assessment"
    al = conn.execute(
        "SELECT * FROM audit_log WHERE event_type='LLM_CALL' AND correlation_id='cid-ok'"
    ).fetchone()
    assert al is not None


@pytest.mark.asyncio
async def test_failure_returns_fallback_and_records_call(
    conn: sqlite3.Connection, prices: Any
):
    client = _FakeClient(exc=RuntimeError("api boom"))
    result = await _call(client, conn, prices, correlation_id="cid-fail")
    assert result.ok is False
    assert result.fallback_reason == "failure"
    # TokenMeter 는 실패 호출도 error_class 와 함께 기록한다.
    tu = conn.execute(
        "SELECT error_class FROM token_usage WHERE correlation_id='cid-fail'"
    ).fetchone()
    assert tu is not None
    assert tu["error_class"] == "RuntimeError"


@pytest.mark.asyncio
async def test_timeout_returns_fallback(conn: sqlite3.Connection, prices: Any):
    client = _FakeClient(
        response=_Response('{"action": "hold", "confidence": 0.1, "reason": "x"}'),
        delay=0.5,
    )
    result = await _call(client, conn, prices, latency_budget_ms=10)  # 10ms < 500ms delay
    assert result.ok is False
    assert result.fallback_reason == "timeout"


@pytest.mark.asyncio
async def test_circuit_open_short_circuits(conn: sqlite3.Connection, prices: Any):
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=1000.0)
    jc = JudgmentClient(
        _FakeClient(exc=RuntimeError("boom")),
        conn=conn,
        prices=prices,
        breaker=breaker,
    )
    # 첫 호출 실패 → breaker open.
    r1 = await jc.call(
        decision_class="volatility_assessment",
        system_prompt="s",
        user_prompt="u",
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
        latency_budget_ms=2000,
    )
    assert r1.fallback_reason == "failure"
    # 두 번째 호출은 서킷이 열려 호출 자체를 안 함.
    r2 = await jc.call(
        decision_class="volatility_assessment",
        system_prompt="s",
        user_prompt="u",
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
        latency_budget_ms=2000,
        correlation_id="cid-open",
    )
    assert r2.fallback_reason == "circuit_open"
    # 서킷오픈은 호출 안 했으므로 token_usage 미기록.
    tu = conn.execute(
        "SELECT * FROM token_usage WHERE correlation_id='cid-open'"
    ).fetchone()
    assert tu is None
