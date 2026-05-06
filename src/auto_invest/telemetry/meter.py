"""TokenMeter — async context manager around every Anthropic call.

Per R-T1 (research.md), the meter is intentionally explicit at the
call site:

    async with TokenMeter(
        decision_class="news_screen",
        correlation_id=cid,
        conn=conn,
        prices=prices,
    ) as call:
        response = await client.messages.create(...)
        call.record_response(response)

On `__aexit__`, the meter persists exactly one `token_usage` row and
exactly one `LLM_CALL` audit-log row sharing the same `correlation_id`.
The exception path also persists, with `error_class` populated.

Per FR-T11 / constitution V the meter never accepts prompt or response
text; only token counts and metadata.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any

from auto_invest.persistence import audit
from auto_invest.persistence.audit import LlmCallPayload
from auto_invest.telemetry.prices import PriceTable
from auto_invest.telemetry.store import (
    TokenUsage,
    _utcnow_iso_ms,
    append_token_usage,
)


@dataclass
class _Counts:
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class MeteredCall:
    """Returned by `async with TokenMeter(...)`.

    The call site invokes `record_response(response)` to feed the
    Anthropic SDK response object. Only the `usage` block and the
    `model` field are read. Other fields are ignored.
    """

    def __init__(self) -> None:
        self._counts = _Counts()

    def record_response(self, response: Any) -> None:
        usage = getattr(response, "usage", None) or {}
        if not isinstance(usage, dict):
            usage = {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
                "cache_creation_input_tokens": getattr(
                    usage, "cache_creation_input_tokens", 0
                ),
            }
        self._counts.input_tokens = int(usage.get("input_tokens") or 0)
        self._counts.output_tokens = int(usage.get("output_tokens") or 0)
        self._counts.cache_read_tokens = int(usage.get("cache_read_input_tokens") or 0)
        self._counts.cache_write_tokens = int(
            usage.get("cache_creation_input_tokens") or 0
        )
        self._counts.model = getattr(response, "model", None) or self._counts.model

    def record_model(self, model: str) -> None:
        """Override the model name (used when the SDK response lacks one)."""
        self._counts.model = model


class TokenMeter:
    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        prices: PriceTable,
        decision_class: str | None = None,
        correlation_id: str | None = None,
        model: str | None = None,
    ) -> None:
        self._conn = conn
        self._prices = prices
        self._decision_class = decision_class
        self._correlation_id = correlation_id or uuid.uuid4().hex
        self._model_hint = model
        self._call: MeteredCall | None = None
        self._start_ns: int | None = None

    @property
    def correlation_id(self) -> str:
        return self._correlation_id

    async def __aenter__(self) -> MeteredCall:
        self._start_ns = time.perf_counter_ns()
        self._call = MeteredCall()
        if self._model_hint is not None:
            self._call.record_model(self._model_hint)
        return self._call

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> bool:
        end_ns = time.perf_counter_ns()
        start_ns = self._start_ns or end_ns
        latency_ms = max(0, int((end_ns - start_ns) / 1_000_000))

        call = self._call or MeteredCall()
        counts = call._counts
        model = counts.model or self._model_hint or "unknown"
        error_class = exc_type.__name__ if exc_type is not None else None

        cost = self._prices.compute_cost(
            model,
            input_tokens=counts.input_tokens,
            output_tokens=counts.output_tokens,
            cache_read_tokens=counts.cache_read_tokens,
            cache_write_tokens=counts.cache_write_tokens,
        )
        cost_str = str(cost) if cost is not None else None

        ts = _utcnow_iso_ms()
        usage = TokenUsage(
            model=model,
            decision_class=self._decision_class,
            input_tokens=counts.input_tokens,
            output_tokens=counts.output_tokens,
            cache_read_tokens=counts.cache_read_tokens,
            cache_write_tokens=counts.cache_write_tokens,
            cost_usd=cost_str,
            latency_ms=latency_ms,
            error_class=error_class,
            correlation_id=self._correlation_id,
            ts_utc=ts,
        )
        append_token_usage(self._conn, usage)

        audit.append(
            self._conn,
            LlmCallPayload(
                model=model,
                decision_class=self._decision_class,
                tokens_total=usage.tokens_total,
                cost_usd=cost_str,
                latency_ms=latency_ms,
                error_class=error_class,
            ),
            correlation_id=self._correlation_id,
            ts_utc=ts,
        )

        # Never swallow exceptions raised by the wrapped call (constitution VII).
        return False
