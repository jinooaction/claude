"""Resilient HTTP client (constitution VII, research R-12).

Wraps `httpx.AsyncClient` with three layers of resilience:

  1. `AsyncTokenBucket`  — rate limiting that respects the broker's
     documented per-second cap.
  2. `tenacity` retry    — exponential backoff with jitter on transient
     failures (network errors, 5xx responses); 4xx propagates
     immediately because retrying a "Bad Request" achieves nothing.
  3. `CircuitBreaker`    — opens after `failure_threshold` consecutive
     transient failures, blocks new requests for `cooldown_seconds`,
     then transitions to half-open for a probe attempt.

Both `AsyncTokenBucket` and `CircuitBreaker` accept an injectable
clock so tests can advance time deterministically.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter


class CircuitBreakerOpen(Exception):
    """Raised when a request is rejected because the breaker is open."""


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class AsyncTokenBucket:
    """Async token bucket: `rate_per_sec` tokens accrue per second up to `capacity`.

    `acquire()` waits until a token is available, then consumes one.
    """

    rate_per_sec: float
    capacity: float
    clock: Callable[[], float] = field(default=time.monotonic)
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self._tokens = float(self.capacity)
        self._last_refill = self.clock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self.clock()
            elapsed = max(0.0, now - self._last_refill)
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate_per_sec)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            wait_time = (1.0 - self._tokens) / self.rate_per_sec
            await asyncio.sleep(wait_time)
            self._tokens = 0.0
            self._last_refill = self.clock()


@dataclass
class CircuitBreaker:
    """Closed -> open after N consecutive failures; half-open after cooldown."""

    failure_threshold: int = 5
    cooldown_seconds: float = 30.0
    clock: Callable[[], float] = field(default=time.monotonic)
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    consecutive_failures: int = field(default=0, init=False)
    opened_at: float = field(default=0.0, init=False)

    def before_request(self) -> None:
        """Raise CircuitBreakerOpen if the breaker is open and cooldown not elapsed."""
        if self.state is CircuitState.OPEN:
            if self.clock() - self.opened_at < self.cooldown_seconds:
                raise CircuitBreakerOpen("circuit breaker is open")
            self.state = CircuitState.HALF_OPEN

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = self.clock()


def _is_transient(exc: BaseException) -> bool:
    """Should this exception trigger a retry?"""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    return False


class ResilientClient:
    """httpx wrapper that applies rate-limit + retry + breaker per request."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        rate_limiter: AsyncTokenBucket,
        breaker: CircuitBreaker,
        max_retries: int = 4,
    ) -> None:
        self._client = client
        self._rate_limiter = rate_limiter
        self._breaker = breaker
        self._max_retries = max_retries

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = await self._do_with_retries(method, url, **kwargs)
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            if _is_transient(exc):
                self._breaker.record_failure()
            raise
        self._breaker.record_success()
        return response

    async def _do_with_retries(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=0.1, max=2.0, jitter=0.1),
            retry=retry_if_exception(_is_transient),
            reraise=True,
        ):
            with attempt:
                self._breaker.before_request()
                await self._rate_limiter.acquire()
                response = await self._client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
        raise RuntimeError("unreachable")  # tenacity reraises on exhaustion
