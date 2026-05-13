"""Tests for `auto_invest.telemetry.meter.TokenMeter` (T203)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from auto_invest.persistence import db
from auto_invest.telemetry.meter import TokenMeter
from auto_invest.telemetry.prices import load_prices


class _FakeUsage(dict):
    """Anthropic SDK exposes usage as a dict-like; emulate."""


class _FakeResponse:
    def __init__(self, model: str, usage: dict[str, int]) -> None:
        self.model = model
        self.usage = usage


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


@pytest.mark.asyncio
async def test_success_path_persists_both_rows(conn: sqlite3.Connection, prices: Any):
    async with TokenMeter(
        conn=conn,
        prices=prices,
        decision_class="news_screen",
        correlation_id="cid-success",
    ) as call:
        response = _FakeResponse(
            model="claude-opus-4-7",
            usage=_FakeUsage(
                input_tokens=100,
                output_tokens=50,
                cache_read_input_tokens=10,
                cache_creation_input_tokens=20,
            ),
        )
        call.record_response(response)

    tu = conn.execute("SELECT * FROM token_usage").fetchone()
    assert tu["model"] == "claude-opus-4-7"
    assert tu["decision_class"] == "news_screen"
    assert tu["input_tokens"] == 100
    assert tu["output_tokens"] == 50
    assert tu["cache_read_tokens"] == 10
    assert tu["cache_write_tokens"] == 20
    assert tu["correlation_id"] == "cid-success"
    assert tu["error_class"] is None
    assert tu["latency_ms"] >= 0
    assert tu["cost_usd"] is not None  # known model -> priced

    al = conn.execute("SELECT * FROM audit_log WHERE event_type='LLM_CALL'").fetchone()
    assert al is not None
    assert al["correlation_id"] == "cid-success"


@pytest.mark.asyncio
async def test_exception_path_persists_with_error_class(conn: sqlite3.Connection, prices: Any):
    with pytest.raises(RuntimeError):
        async with TokenMeter(
            conn=conn,
            prices=prices,
            decision_class="news_screen",
            correlation_id="cid-err",
            model="claude-opus-4-7",
        ):
            raise RuntimeError("boom")

    tu = conn.execute("SELECT * FROM token_usage").fetchone()
    assert tu["error_class"] == "RuntimeError"
    assert tu["input_tokens"] == 0
    assert tu["correlation_id"] == "cid-err"


@pytest.mark.asyncio
async def test_decision_class_none_preserved_as_null(conn: sqlite3.Connection, prices: Any):
    async with TokenMeter(
        conn=conn,
        prices=prices,
        decision_class=None,
        correlation_id="cid-null",
        model="claude-opus-4-7",
    ) as call:
        call.record_response(
            _FakeResponse(
                model="claude-opus-4-7",
                usage=_FakeUsage(input_tokens=1, output_tokens=1),
            )
        )

    tu = conn.execute("SELECT * FROM token_usage").fetchone()
    assert tu["decision_class"] is None


@pytest.mark.asyncio
async def test_unknown_model_yields_null_cost(conn: sqlite3.Connection, prices: Any):
    async with TokenMeter(
        conn=conn,
        prices=prices,
        decision_class="x",
        correlation_id="cid-unk",
    ) as call:
        call.record_response(
            _FakeResponse(
                model="claude-fictional-1",
                usage=_FakeUsage(input_tokens=10, output_tokens=10),
            )
        )

    tu = conn.execute("SELECT * FROM token_usage").fetchone()
    assert tu["cost_usd"] is None
    assert tu["model"] == "claude-fictional-1"


@pytest.mark.asyncio
async def test_latency_clamped_non_negative(conn: sqlite3.Connection, prices: Any):
    async with TokenMeter(
        conn=conn,
        prices=prices,
        decision_class=None,
        correlation_id="cid-lat",
        model="claude-opus-4-7",
    ) as call:
        call.record_response(_FakeResponse(model="claude-opus-4-7", usage=_FakeUsage()))

    tu = conn.execute("SELECT * FROM token_usage").fetchone()
    assert tu["latency_ms"] >= 0
