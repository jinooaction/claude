"""Optional live KIS smoke test (T064).

Gated by KIS_LIVE_TEST=1. NEVER runs in CI. Verifies that the
overseas-equity adapter shapes match the real broker by issuing one
access token and one read-only quote call. Places NO orders.

Run via:
    uv run python scripts/live_smoke.py

The runner script handles credential prompting (hidden input) and
sets the required env vars in the subprocess.
"""

from __future__ import annotations

import os
from decimal import Decimal

import httpx
import pytest

from auto_invest.broker.auth import issue_token
from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.broker.overseas import get_quote

pytestmark = pytest.mark.skipif(
    os.environ.get("KIS_LIVE_TEST") != "1",
    reason="Live KIS smoke test gated by KIS_LIVE_TEST=1",
)


KIS_BASE_URL = os.environ.get("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")


@pytest.mark.asyncio
async def test_live_kis_token_and_quote() -> None:
    """Issues a token + fetches a single AAPL quote against the real
    broker. No trading endpoint is touched."""
    app_key = os.environ["KIS_APP_KEY"]
    app_secret = os.environ["KIS_APP_SECRET"]

    async with httpx.AsyncClient(base_url=KIS_BASE_URL, timeout=30.0) as inner:
        token = await issue_token(
            inner,
            base_url=KIS_BASE_URL,
            app_key=app_key,
            app_secret=app_secret,
        )
        assert token.access_token  # masked in logs by the redaction filter
        assert token.token_type.lower() in ("bearer", "bearer ")

        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=15.0, capacity=15.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0),
            max_retries=2,
        )

        quote = await get_quote(
            broker,
            access_token=token.access_token,
            app_key=app_key,
            app_secret=app_secret,
            symbol="AAPL",
            market="NAS",
        )

    assert quote.symbol == "AAPL"
    assert quote.last_price_usd > Decimal("0")
    # Last price is non-secret market data, so printing it is fine.
    print(f"\nLive AAPL quote: ${quote.last_price_usd}")
