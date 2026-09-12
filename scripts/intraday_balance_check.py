#!/usr/bin/env python3
"""Run a private-account GET comparison, publishing only counts and conclusions."""

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx

from auto_invest.broker.account_asset_evidence import observe_account_assets
from auto_invest.broker.account_source_profile import profile_margin_responses
from auto_invest.broker.auth import get_valid_token
from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.intraday_account import (
    AccountReadError,
    observe_account,
    public_contract_result,
)
from auto_invest.broker.intraday_balance_evidence import (
    observe_balance_evidence,
    public_balance_evidence,
)
from auto_invest.execution.intraday_account_history import AccountHistory, AccountHistoryError


async def _query(*, history=None):
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
        if history is not None:
            client = history.client(client)
        snapshot = await observe_balance_evidence(
            client,
            account=os.environ["KIS_ACCOUNT_NO"],
            access_token=token.access_token,
            app_key=os.environ["KIS_APP_KEY"],
            app_secret=os.environ["KIS_APP_SECRET"],
        )
        account_assets = await observe_account_assets(
            client, account=os.environ["KIS_ACCOUNT_NO"], access_token=token.access_token,
            app_key=os.environ["KIS_APP_KEY"], app_secret=os.environ["KIS_APP_SECRET"],
        )
        current_account = None
        if history is not None:
            current_account = public_contract_result(await observe_account(
                client, account=os.environ["KIS_ACCOUNT_NO"], access_token=token.access_token,
                app_key=os.environ["KIS_APP_KEY"], app_secret=os.environ["KIS_APP_SECRET"],
            ))
    result = dict(public_balance_evidence(snapshot), account_assets=account_assets)
    if current_account is not None:
        result["current_account"] = current_account
    return result, 0


async def run(*, history_db=None, execution_db=None):
    history = None
    if execution_db is not None and history_db is None:
        raise AccountHistoryError("HISTORY_DATABASE_REQUIRED")
    if history_db is not None and all(os.environ.get(key) for key in (
        "KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO",
    )):
        history = AccountHistory(history_db, os.environ["KIS_ACCOUNT_NO"],
                                 execution_db=execution_db)
    try:
        result, code = await _query(history=history)
    except BaseException:
        if history is not None:
            history.finish("FAILED")
        raise
    if history is not None:
        result["history"] = history.finish("COMPLETE" if code == 0 else "FAILED")
        result["source_structure"] = profile_margin_responses(history.responses)
    return result, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-db", type=Path, help="Private account source journal")
    parser.add_argument("--execution-db", type=Path, help="Existing execution ledger; read only")
    args = parser.parse_args()
    try:
        result, code = asyncio.run(run(history_db=args.history_db, execution_db=args.execution_db))
    except Exception as exc:
        result = dict(
            status="FAILED",
            reason=str(exc) if isinstance(exc, (AccountReadError, AccountHistoryError))
            else type(exc).__name__,
            orders_submitted=0,
            live_eligible=False,
        )
        code = 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
