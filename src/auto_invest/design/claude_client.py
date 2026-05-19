"""Spec 010 T013 — Claude API thin wrapper for rule design.

`anthropic.AsyncAnthropic.messages.create`를 TokenMeter context로 감싸 호출.
응답 텍스트·모델 ID·토큰 사용량·비용을 한 dataclass로 묶어 리턴.

테스트에서는 `AsyncAnthropic` 자체를 monkeypatch — `_AnthropicProtocol`로
duck-typing해서 mock 객체 주입 가능.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from auto_invest.telemetry.meter import TokenMeter
from auto_invest.telemetry.prices import PriceTable

_RULE_DESIGN_DECISION_CLASS = "rule_design"
_MAX_COST_USD = Decimal("0.20")


class _AnthropicProtocol(Protocol):
    """Duck-type for `anthropic.AsyncAnthropic`-like client (테스트 mock용)."""

    messages: Any  # has `create(model, max_tokens, system, messages, ...)`


@dataclass(frozen=True)
class ClaudeDesignResponse:
    """`call_rule_design`의 리턴값.

    `text`는 Claude 응답 본문 (INTERPRETATION 주석 + TOML 한 덩어리).
    `cost_exceeded`가 True면 호출이 cost-band 한도를 넘어서 거부됨 — 호출자가
    RULE_DESIGN_REJECTED(reason="claude_api_error" 또는 별도)로 처리.
    """

    text: str
    model_id: str
    tokens_input: int
    tokens_output: int
    cost_usd: Decimal
    cost_exceeded: bool


async def call_rule_design(
    client: _AnthropicProtocol,
    *,
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-opus-4-7",
    max_tokens: int = 2500,
    conn: Any,  # sqlite3.Connection
    prices: PriceTable,
) -> ClaudeDesignResponse:
    """Spec 010의 새 judgment point `rule_design`에서 Claude 1회 호출.

    호출 결과의 token usage는 spec 002 meter에 기록되어 LLM_CALL 페이로드로
    audit_log에 남음. 비용이 cost-band 한도($0.20)를 넘으면 cost_exceeded=True
    리턴 — 호출자가 재시도 차감 또는 거부 처리.
    """
    async with TokenMeter(
        conn=conn,
        prices=prices,
        decision_class=_RULE_DESIGN_DECISION_CLASS,
        model=model,
    ) as metered:
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # response 객체에서 token 정보 + 본문 추출.
        text = _extract_text(response)
        # TokenMeter가 ANT SDK 응답에서 usage를 자동 읽도록 record.
        metered.record_response(response)

    counts = metered._counts  # type: ignore[attr-defined]
    cost = prices.compute_cost(
        counts.model or model,
        input_tokens=counts.input_tokens,
        output_tokens=counts.output_tokens,
        cache_read_tokens=counts.cache_read_tokens,
        cache_write_tokens=counts.cache_write_tokens,
    ) or Decimal("0")
    return ClaudeDesignResponse(
        text=text,
        model_id=counts.model or model,
        tokens_input=counts.input_tokens,
        tokens_output=counts.output_tokens,
        cost_usd=cost,
        cost_exceeded=cost > _MAX_COST_USD,
    )


def _extract_text(response: Any) -> str:
    """anthropic.types.Message.content는 ContentBlock 리스트.

    텍스트 블록만 추출해 이어붙임. 테스트 mock은 `content=[Mock(text="...")]`
    또는 단순 `text="..."` 속성으로 응답할 수도 있음 — 둘 다 지원.
    """
    content = getattr(response, "content", None)
    if content is None:
        return str(getattr(response, "text", ""))
    parts: list[str] = []
    for block in content:
        text_attr = getattr(block, "text", None)
        if text_attr is not None:
            parts.append(text_attr)
    return "".join(parts)
