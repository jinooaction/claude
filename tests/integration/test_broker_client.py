"""Integration tests for ResilientClient (T029).

Uses respx to deterministically reproduce transient failures (5xx),
permanent failures (4xx), and recovery patterns. The breaker and rate
limiter accept an injectable `clock` so tests advance time without
sleeping.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import httpx
import pytest
import respx

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    ResilientClient,
)

BASE = "https://api.example"


def _fake_clock() -> tuple[list[float], Callable[[], float]]:
    state = [0.0]

    def now() -> float:
        return state[0]

    return state, now


@asynccontextmanager
async def _make_client(
    *,
    rate_per_sec: float = 100.0,
    capacity: float = 100.0,
    failure_threshold: int = 5,
    cooldown_seconds: float = 30.0,
    max_retries: int = 4,
    clock: Callable[[], float] | None = None,
) -> AsyncIterator[ResilientClient]:
    bucket_kwargs: dict = {"rate_per_sec": rate_per_sec, "capacity": capacity}
    breaker_kwargs: dict = {
        "failure_threshold": failure_threshold,
        "cooldown_seconds": cooldown_seconds,
    }
    if clock is not None:
        bucket_kwargs["clock"] = clock
        breaker_kwargs["clock"] = clock
    async with httpx.AsyncClient(base_url=BASE) as inner:
        yield ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(**bucket_kwargs),
            breaker=CircuitBreaker(**breaker_kwargs),
            max_retries=max_retries,
        )


# ---------------------------------------------------------------- retry policy


@pytest.mark.asyncio
async def test_retries_5xx_then_succeeds():
    async with _make_client(max_retries=4) as client:
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/probe").mock(
                side_effect=[
                    httpx.Response(500, json={"err": "x"}),
                    httpx.Response(500, json={"err": "x"}),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            response = await client.request("GET", "/probe")
            assert response.status_code == 200
            assert route.call_count == 3


@pytest.mark.asyncio
async def test_no_retry_on_4xx():
    async with _make_client(max_retries=4) as client:
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/forbidden").mock(
                return_value=httpx.Response(400, json={"err": "bad"}),
            )
            with pytest.raises(httpx.HTTPStatusError) as excinfo:
                await client.request("GET", "/forbidden")
            assert excinfo.value.response.status_code == 400
            assert route.call_count == 1


@pytest.mark.asyncio
async def test_retries_on_transport_error_then_succeeds():
    async with _make_client(max_retries=4) as client:
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/flaky-net").mock(
                side_effect=[
                    httpx.ConnectError("boom"),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            response = await client.request("GET", "/flaky-net")
            assert response.status_code == 200
            assert route.call_count == 2


@pytest.mark.asyncio
async def test_retry_exhaustion_propagates_last_error():
    async with _make_client(max_retries=3) as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/dead").mock(return_value=httpx.Response(503))
            with pytest.raises(httpx.HTTPStatusError) as excinfo:
                await client.request("GET", "/dead")
            assert excinfo.value.response.status_code == 503


# ---------------------------------------------------------------- breaker


@pytest.mark.asyncio
async def test_breaker_opens_after_threshold():
    async with _make_client(failure_threshold=3, max_retries=1) as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/dead").mock(return_value=httpx.Response(500))
            for _ in range(3):
                with pytest.raises(httpx.HTTPStatusError):
                    await client.request("GET", "/dead")
            with pytest.raises(CircuitBreakerOpen):
                await client.request("GET", "/dead")


@pytest.mark.asyncio
async def test_breaker_resets_on_success():
    async with _make_client(failure_threshold=3, max_retries=1) as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/recovery").mock(
                side_effect=[
                    httpx.Response(500),
                    httpx.Response(500),
                    httpx.Response(200, json={"ok": True}),
                    httpx.Response(500),
                    httpx.Response(500),
                ]
            )
            with pytest.raises(httpx.HTTPStatusError):
                await client.request("GET", "/recovery")
            with pytest.raises(httpx.HTTPStatusError):
                await client.request("GET", "/recovery")
            response = await client.request("GET", "/recovery")
            assert response.status_code == 200
            # After success, the failure counter is back to zero.
            with pytest.raises(httpx.HTTPStatusError):
                await client.request("GET", "/recovery")
            with pytest.raises(httpx.HTTPStatusError):
                await client.request("GET", "/recovery")
            # Still only 2 fresh failures < threshold; next call must
            # NOT see CircuitBreakerOpen.
            assert client._breaker.state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_breaker_half_open_after_cooldown_then_recovers():
    state, clock = _fake_clock()
    async with _make_client(
        failure_threshold=2,
        cooldown_seconds=10.0,
        max_retries=1,
        clock=clock,
    ) as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/blip").mock(
                side_effect=[
                    httpx.Response(500),
                    httpx.Response(500),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            with pytest.raises(httpx.HTTPStatusError):
                await client.request("GET", "/blip")
            with pytest.raises(httpx.HTTPStatusError):
                await client.request("GET", "/blip")
            # Breaker is now OPEN.
            with pytest.raises(CircuitBreakerOpen):
                await client.request("GET", "/blip")

            state[0] += 11.0  # cooldown elapsed.
            response = await client.request("GET", "/blip")
            assert response.status_code == 200
            assert client._breaker.state is CircuitState.CLOSED


# ---------------------------------------------------------------- rate limiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_burst_up_to_capacity():
    state, clock = _fake_clock()
    bucket = AsyncTokenBucket(rate_per_sec=10.0, capacity=3.0, clock=clock)
    # Burst of 3 should pass without waiting.
    for _ in range(3):
        await asyncio.wait_for(bucket.acquire(), timeout=0.1)


@pytest.mark.asyncio
async def test_rate_limiter_delays_when_empty():
    bucket = AsyncTokenBucket(rate_per_sec=20.0, capacity=2.0)
    await bucket.acquire()
    await bucket.acquire()
    # Bucket is empty; the next acquire must wait approximately 1/20 = 50 ms.
    loop = asyncio.get_running_loop()
    start = loop.time()
    await bucket.acquire()
    elapsed = loop.time() - start
    assert elapsed >= 0.04  # tolerate scheduling jitter
    assert elapsed < 0.5  # but should not be absurdly slow
