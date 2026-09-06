"""Confirmed preparation parameters are not funding or broker-write authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from auto_invest.analytics.intraday_capital_review import load_prices
from auto_invest.execution.intraday_rehearsal import rehearse

DEFAULT_BUDGET = Path("specs/182-intraday-kis-execution/contracts/confirmed-budget.json")
CONFIRMED = {
    "schema_version": 1,
    "currency": "USD",
    "approval_scope": "preparation_parameters",
    "capital_limit_usd": "600.00",
    "order_limit_usd": "120.00",
    "symbol_limit_usd": "120.00",
    "total_exposure_limit_usd": "480.00",
    "daily_stop_trigger_usd": "12.00",
    "orders_enabled": False,
    "confirmed_on": "2026-09-07",
    "confirmation_reference": "운영자: 응 확정하고 완성해줘",
}


def confirmed_budget(path: Path = DEFAULT_BUDGET) -> dict:
    value = load_prices(path)  # Bounded JSON with duplicate-key rejection.
    if not isinstance(value, dict) or set(value) != set(CONFIRMED):
        raise ValueError("BUDGET_SCHEMA")
    if any(type(value[k]) is not type(v) or value[k] != v for k, v in CONFIRMED.items()):
        raise ValueError("CONFIRMED_BUDGET_MISMATCH")
    return value


async def preflight() -> dict:
    from decimal import Decimal

    budget = confirmed_budget()
    rehearsal = await rehearse(
        capital_limit=Decimal(budget["capital_limit_usd"]), mark=Decimal("20")
    )
    return dict(
        schema_version=182,
        mode="confirmed_budget_preflight",
        status="PREPARATION_CHECKED",
        budget=budget,
        budget_sha256=hashlib.sha256(
            json.dumps(budget, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        budget_parameters_confirmed=True,
        capital_change_usd="0.00",
        orders_submitted=0,
        live_eligible=False,
        simulation_price_is_market_quote=False,
        rehearsal=rehearsal,
        blockers=[
            "VERIFIED_ACCOUNT_NAV_REQUIRED",
            "HISTORY_AND_STRATEGY_ACCEPTANCE_REQUIRED",
            "QUALIFIED_FORWARD_60_SESSIONS_REQUIRED",
            "PROVIDER_EXECUTION_PARITY_REQUIRED",
            "PRODUCTION_INTRADAY_AUTHORITY_REQUIRED",
            "PRODUCTION_FILLS_NOT_VERIFIED",
        ],
    )
