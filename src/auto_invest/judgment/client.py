"""Resilient Anthropic client for judgment points (헌법 VII — FR-004).

`broker/client.py` 의 `AsyncTokenBucket`(레이트리밋)·`CircuitBreaker`(서킷)를
재사용하고, `design/claude_client.py` 의 `TokenMeter` 감싸기 패턴을 미러한다.
새 견고성 메커니즘을 발명하지 않는다.

호출 결과는 `JudgmentCallResult` 로 반환한다:
  - 성공: `ok=True`, `text`(자유 텍스트), `cost_usd`.
  - 실패/타임아웃/서킷오픈: `ok=False`, `fallback_reason` — 호출자는 거래를
    막지 않고 결정론적 폴백으로 진행한다(SC-001).

`TokenMeter` 는 예외를 삼키지 않고 실패 호출도 token_usage + LLM_CALL 로
기록(error_class 포함)한 뒤 다시 던지므로, 실패한 호출도 감사에 남는다.
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    CircuitBreakerOpen,
)
from auto_invest.telemetry.meter import TokenMeter
from auto_invest.telemetry.prices import PriceTable

FallbackReason = Literal["failure", "timeout", "circuit_open"]


class _AnthropicProtocol(Protocol):
    """`anthropic.AsyncAnthropic` 덕타이핑 (테스트 mock 용)."""

    messages: Any  # has async create(model, max_tokens, system, messages, ...)


@dataclass(frozen=True)
class JudgmentCallResult:
    """판단 호출 결과. ok=False 면 호출자는 결정론적 폴백으로 전환한다."""

    ok: bool
    correlation_id: str
    text: str | None = None
    cost_usd: Decimal = Decimal("0")
    fallback_reason: FallbackReason | None = None


class JudgmentClient:
    """판단 지점용 견고한 Anthropic 단발 호출 래퍼."""

    def __init__(
        self,
        client: _AnthropicProtocol,
        *,
        conn: sqlite3.Connection,
        prices: PriceTable,
        breaker: CircuitBreaker | None = None,
        rate_limiter: AsyncTokenBucket | None = None,
    ) -> None:
        self._client = client
        self._conn = conn
        self._prices = prices
        self._breaker = breaker or CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)
        # 판단 지점은 드물게(트리거+쿨다운) 호출되므로 보수적 레이트.
        self._rate_limiter = rate_limiter or AsyncTokenBucket(rate_per_sec=2.0, capacity=4.0)

    async def call(
        self,
        *,
        decision_class: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        latency_budget_ms: int,
        correlation_id: str | None = None,
    ) -> JudgmentCallResult:
        cid = correlation_id or uuid.uuid4().hex

        # 서킷이 열려 있으면 호출 자체를 안 함 (비용 0, LLM_CALL 미기록).
        try:
            self._breaker.before_request()
        except CircuitBreakerOpen:
            return JudgmentCallResult(
                ok=False, correlation_id=cid, fallback_reason="circuit_open"
            )

        await self._rate_limiter.acquire()

        timeout_s = max(0.001, latency_budget_ms / 1000.0)
        try:
            async with TokenMeter(
                conn=self._conn,
                prices=self._prices,
                decision_class=decision_class,
                correlation_id=cid,
                model=model,
            ) as metered:
                response = await asyncio.wait_for(
                    self._client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                    ),
                    timeout=timeout_s,
                )
                metered.record_response(response)
                text = _extract_text(response)
        except TimeoutError:
            self._breaker.record_failure()
            return JudgmentCallResult(
                ok=False, correlation_id=cid, fallback_reason="timeout"
            )
        except Exception:
            # 어떤 실패든 거래를 막지 않는다 — 폴백 신호로 변환 (SC-001).
            self._breaker.record_failure()
            return JudgmentCallResult(
                ok=False, correlation_id=cid, fallback_reason="failure"
            )

        self._breaker.record_success()
        counts = metered._counts
        cost = self._prices.compute_cost(
            counts.model or model,
            input_tokens=counts.input_tokens,
            output_tokens=counts.output_tokens,
            cache_read_tokens=counts.cache_read_tokens,
            cache_write_tokens=counts.cache_write_tokens,
        ) or Decimal("0")
        return JudgmentCallResult(
            ok=True, correlation_id=cid, text=text, cost_usd=cost
        )


def _extract_text(response: Any) -> str:
    """anthropic Message.content(ContentBlock 리스트)에서 텍스트만 이어붙임.

    테스트 mock 은 `content=[obj(text=...)]` 또는 `text="..."` 둘 다 지원.
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
