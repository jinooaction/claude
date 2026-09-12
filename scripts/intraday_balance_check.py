#!/usr/bin/env python3
"""Run a private-account GET comparison, publishing only counts and conclusions."""

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx

from auto_invest.broker.account_asset_evidence import observe_account_assets
from auto_invest.broker.account_cash_comparison import compare_cash_sources
from auto_invest.broker.account_component_profile import profile_account_components
from auto_invest.broker.account_source_profile import profile_margin_responses
from auto_invest.broker.auth import get_valid_token
from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.domestic_account import observe_domestic_account, public_domestic_account
from auto_invest.broker.domestic_cash_comparison import compare_domestic_cash_sources
from auto_invest.broker.intraday_account import (
    AccountReadError,
    observe_account,
    public_contract_result,
)
from auto_invest.broker.intraday_balance_evidence import (
    observe_balance_evidence,
    public_balance_evidence,
)
from auto_invest.broker.intraday_transactions import (
    observe_transactions,
    public_transactions,
    validate_window,
)
from auto_invest.broker.overseas import get_order_executions_resolving_market
from auto_invest.execution.intraday_account_history import AccountHistory, AccountHistoryError
from auto_invest.execution.intraday_cost_reconciliation import (
    CostReconciliationError,
    reconcile_cost_inputs,
)


async def _query(*, transactions_from=None, transactions_through=None, execution_db=None,
                 history=None):
    include_transactions = transactions_from is not None or transactions_through is not None
    if execution_db is not None:
        if include_transactions or history is None:
            validate_window(transactions_from, transactions_through)
        if not Path(execution_db).is_file():
            raise CostReconciliationError("COST_LEDGER_UNAVAILABLE")
    if include_transactions:
        validate_window(transactions_from, transactions_through)
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
        domestic_account = None
        if history is not None:
            current_account = public_contract_result(await observe_account(
                client, account=os.environ["KIS_ACCOUNT_NO"], access_token=token.access_token,
                app_key=os.environ["KIS_APP_KEY"], app_secret=os.environ["KIS_APP_SECRET"],
            ))
            domestic_account = public_domestic_account(await observe_domestic_account(
                client, account=os.environ["KIS_ACCOUNT_NO"], access_token=token.access_token,
                app_key=os.environ["KIS_APP_KEY"], app_secret=os.environ["KIS_APP_SECRET"],
            ))
        transactions = None
        if include_transactions:
            transaction_snapshot = await observe_transactions(
                client, account=os.environ["KIS_ACCOUNT_NO"], access_token=token.access_token,
                app_key=os.environ["KIS_APP_KEY"], app_secret=os.environ["KIS_APP_SECRET"],
                start_date=transactions_from, end_date=transactions_through,
            )
            transactions = public_transactions(transaction_snapshot)
            if execution_db is not None:
                executions = await get_order_executions_resolving_market(
                    client, account=os.environ["KIS_ACCOUNT_NO"], access_token=token.access_token,
                    app_key=os.environ["KIS_APP_KEY"], app_secret=os.environ["KIS_APP_SECRET"],
                    order_date_yyyymmdd=transactions_from, end_date_yyyymmdd=transactions_through,
                    strict_contract=True,
                )
                transactions["ledger_comparison"] = reconcile_cost_inputs(
                    Path(execution_db), executions, transaction_snapshot["rows"],
                )
    result = dict(public_balance_evidence(snapshot), account_assets=account_assets)
    if current_account is not None:
        result["current_account"] = current_account
        result["domestic_account"] = domestic_account
    if transactions is not None:
        result["transactions"] = transactions
    return result, 0


async def run(*, transactions_from=None, transactions_through=None, execution_db=None,
              history_db=None):
    if transactions_from is not None or transactions_through is not None:
        validate_window(transactions_from, transactions_through)
    history = None
    if history_db is not None and all(os.environ.get(key) for key in (
        "KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO",
    )):
        history = AccountHistory(history_db, os.environ["KIS_ACCOUNT_NO"],
                                 execution_db=execution_db)
    try:
        result, code = await _query(
            transactions_from=transactions_from, transactions_through=transactions_through,
            execution_db=execution_db, history=history,
        )
    except BaseException:
        if history is not None:
            history.finish("FAILED")
        raise
    if history is not None:
        result["history"] = history.finish("COMPLETE" if code == 0 else "FAILED")
        result["source_structure"] = profile_margin_responses(history.responses)
        result["cash_source_comparison"] = compare_cash_sources(history.responses)
        result["domestic_cash_comparison"] = compare_domestic_cash_sources(history.responses)
        result["account_components"] = profile_account_components(history.responses)
    return result, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transactions-from", help="Registration start date, YYYYMMDD")
    parser.add_argument("--transactions-through", help="Registration end date, YYYYMMDD")
    parser.add_argument(
        "--execution-db", type=Path, help="Existing execution DB; read-only comparison",
    )
    parser.add_argument(
        "--history-db", type=Path,
        help="Private account observation journal; records from now, no historical window required",
    )
    args = parser.parse_args()
    try:
        result, code = asyncio.run(run(
            transactions_from=args.transactions_from,
            transactions_through=args.transactions_through,
            execution_db=args.execution_db,
            history_db=args.history_db,
        ))
    except Exception as exc:
        result = dict(
            status="FAILED",
            reason=str(exc) if isinstance(exc, (
                AccountReadError, CostReconciliationError, AccountHistoryError,
            ))
            else type(exc).__name__,
            orders_submitted=0,
            live_eligible=False,
        )
        code = 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
