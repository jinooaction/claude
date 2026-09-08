#!/usr/bin/env python3
"""Run a private-account GET comparison, publishing only counts and conclusions."""

import asyncio
import json
import os
from pathlib import Path

import httpx

from auto_invest.broker.auth import get_valid_token
from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.intraday_balance_evidence import (
    observe_balance_evidence,
    public_balance_evidence,
)


async def run():
    required = ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO")
    if any(not os.environ.get(key) for key in required):
        return dict(status="DATA_ACCESS_REQUIRED", orders_submitted=0, live_eligible=False), 2
    base_url = "https://openapi.koreainvestment.com:9443"
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0, follow_redirects=False) as http:
        token = await get_valid_token(
            http,
            base_url=base_url,
            app_key=os.environ["KIS_APP_KEY"],
            app_secret=os.environ["KIS_APP_SECRET"],
            cache_path=Path(os.environ.get("KIS_TOKEN_CACHE_PATH", "data/kis_token.json")),
        )
        client = ResilientClient(
            http,
            rate_limiter=AsyncTokenBucket(rate_per_sec=1.0, capacity=1.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0),
            max_retries=2,
        )
        snapshot = await observe_balance_evidence(
            client,
            account=os.environ["KIS_ACCOUNT_NO"],
            access_token=token.access_token,
            app_key=os.environ["KIS_APP_KEY"],
            app_secret=os.environ["KIS_APP_SECRET"],
        )
    return public_balance_evidence(snapshot), 0


def main():
    try:
        result, code = asyncio.run(run())
    except Exception as exc:
        result = dict(
            status="FAILED",
            reason=str(exc) if isinstance(exc, AccountReadError) else type(exc).__name__,
            orders_submitted=0,
            live_eligible=False,
        )
        code = 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
