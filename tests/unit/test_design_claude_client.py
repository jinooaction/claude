"""Spec 010 T009 — Claude API thin wrapper.

anthropic SDK 자체를 mock 객체로 주입해 호출 → 응답 텍스트·토큰·비용이
정확히 분해되는지 검증.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from auto_invest.design.claude_client import call_rule_design
from auto_invest.persistence import db
from auto_invest.telemetry.prices import PriceEntry, PriceTable

_PRICE_TABLE = PriceTable(
    entries={
        "claude-opus-4-7": PriceEntry(
            usd_per_million_input_tokens=Decimal("15"),
            usd_per_million_output_tokens=Decimal("75"),
            usd_per_million_cache_read_tokens=Decimal("1.5"),
            usd_per_million_cache_write_tokens=Decimal("18.75"),
        ),
    },
    source_path="/test/prices.toml",
    sha256="0" * 64,
)


class _MockAnthropicClient:
    """anthropic.AsyncAnthropic의 duck-type mock."""

    def __init__(
        self,
        response_text: str,
        *,
        input_tokens=1000,
        output_tokens=500,
        model="claude-opus-4-7",
    ):
        self._response_text = response_text
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._model = model
        self.messages = self  # 자기 자신을 messages 객체로

    async def create(self, *, model, max_tokens, system, messages):
        # anthropic.types.Message 구조 mock
        return SimpleNamespace(
            content=[SimpleNamespace(text=self._response_text)],
            usage={
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
            },
            model=self._model,
        )


@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


@pytest.mark.asyncio
async def test_call_returns_text_and_tokens(conn):
    client = _MockAnthropicClient(
        response_text="# INTERPRETATION: {}\n[caps]\nper_trade_pct = 5\n",
        input_tokens=1234,
        output_tokens=567,
    )
    response = await call_rule_design(
        client,
        system_prompt="sys",
        user_prompt="user",
        conn=conn,
        prices=_PRICE_TABLE,
    )
    assert "INTERPRETATION" in response.text
    assert response.tokens_input == 1234
    assert response.tokens_output == 567
    assert response.model_id == "claude-opus-4-7"
    assert response.cost_usd > Decimal("0")
    assert response.cost_exceeded is False


@pytest.mark.asyncio
async def test_call_marks_cost_exceeded_above_band(conn):
    """입력 5M·출력 1M 토큰 → 가격표 기준 입력 $75 + 출력 $75 = $150 → cost-band 초과."""
    client = _MockAnthropicClient(
        response_text="text",
        input_tokens=5_000_000,
        output_tokens=1_000_000,
    )
    response = await call_rule_design(
        client,
        system_prompt="sys",
        user_prompt="user",
        conn=conn,
        prices=_PRICE_TABLE,
    )
    assert response.cost_exceeded is True


@pytest.mark.asyncio
async def test_token_usage_recorded_to_meter(conn):
    """spec 002 token_usage 테이블에 row 1개 + LLM_CALL audit row 1개."""
    client = _MockAnthropicClient(
        response_text="text", input_tokens=100, output_tokens=50,
    )
    await call_rule_design(
        client,
        system_prompt="sys",
        user_prompt="user",
        conn=conn,
        prices=_PRICE_TABLE,
    )

    token_rows = list(conn.execute("SELECT * FROM token_usage"))
    assert len(token_rows) == 1
    assert token_rows[0]["input_tokens"] == 100
    assert token_rows[0]["decision_class"] == "rule_design"

    audit_rows = list(conn.execute(
        "SELECT payload_json FROM audit_log WHERE event_type = 'LLM_CALL'"
    ))
    assert len(audit_rows) == 1
    import json
    payload = json.loads(audit_rows[0]["payload_json"])
    assert payload["decision_class"] == "rule_design"
