"""Offline arithmetic for capital review; never an execution configuration."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

# Kept independent of broker/runtime imports. Contract tests verify sizing parity.
SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "GLD")
CENT = Decimal(".01")


def money(value: object, *, positive: bool = True) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,8}(\.[0-9]{1,4})?", value):
        raise ValueError("INVALID_USD_AMOUNT")
    amount = Decimal(value)
    if amount < 0 or (positive and amount == 0):
        raise ValueError("INVALID_USD_AMOUNT")
    return amount


def _text(amount: Decimal) -> str:
    return format(amount, "f")


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_INPUT_FIELD")
        result[key] = value
    return result


def load_prices(path: Path) -> dict:
    if path.stat().st_size > 16_384:
        raise ValueError("INPUT_TOO_LARGE")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)


def review(prices: dict, capital_usd: str, *, now: datetime | None = None) -> dict:
    expected = {"schema_version", "currency", "quote_as_of", "quote_source", "prices"}
    if not isinstance(prices, dict) or set(prices) != expected:
        raise ValueError("INVALID_REVIEW_SCHEMA")
    if type(prices["schema_version"]) is not int or prices["schema_version"] != 1:
        raise ValueError("INVALID_REVIEW_VERSION")
    if prices["currency"] != "USD":
        raise ValueError("USD_ONLY")
    source = prices["quote_source"]
    if not isinstance(source, str) or not 1 <= len(source.strip()) <= 500:
        raise ValueError("INVALID_QUOTE_SOURCE")
    try:
        stamp = datetime.fromisoformat(prices["quote_as_of"])
    except (ValueError, TypeError):
        raise ValueError("INVALID_QUOTE_TIME") from None
    clock = now or datetime.now(UTC)
    if stamp.tzinfo is None or stamp.utcoffset() is None or stamp > clock:
        raise ValueError("INVALID_QUOTE_TIME")
    values = prices["prices"]
    if not isinstance(values, dict) or set(values) != set(SYMBOLS):
        raise ValueError("INVALID_SYMBOLS")
    marks = {symbol: money(values[symbol]) for symbol in SYMBOLS}
    capital = money(capital_usd, positive=False)
    if capital != capital.quantize(CENT):
        raise ValueError("CAPITAL_REQUIRES_CENTS")
    capital = capital.quantize(CENT)
    cash = capital
    rows = []
    for symbol in SYMBOLS:
        limit = (marks[symbol] * Decimal("1.0006")).quantize(CENT, rounding=ROUND_FLOOR)
        if limit <= 0:
            raise ValueError("REFERENCE_PRICE_BELOW_ONE_CENT")
        notional = min(capital * Decimal(".16"), cash / Decimal("1.003"))
        quantity = int(notional / limit)
        reserved_cash = quantity * limit * Decimal("1.003")
        cash -= reserved_cash
        rows.append(
            dict(
                symbol=symbol,
                reference_price_usd=_text(marks[symbol]),
                illustrative_buy_limit_usd=_text(limit),
                hypothetical_shares=quantity,
                hypothetical_reserved_cash_usd=_text(reserved_cash),
                minimum_capital_for_one_reference_share_usd=_text(
                    (limit / Decimal(".16")).quantize(CENT, rounding=ROUND_CEILING)
                ),
            )
        )
    execution = Path(__file__).parents[1] / "execution"
    files = (Path(__file__), execution / "intraday.py", execution / "intraday_signals.py")
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    return dict(
        schema_version=1,
        mode="capital_review_only",
        status="REVIEW_COMPLETE",
        live_eligible=False,
        capital_change_usd="0.00",
        orders_submitted=0,
        approval_recorded=False,
        account_nav_verified=False,
        input_sha256=hashlib.sha256(
            json.dumps(prices, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        source_sha256=sources,
        quote_as_of=stamp.isoformat(),
        quote_source=source,
        quote_age_seconds=int((clock - stamp).total_seconds()),
        execution_quote_verified=False,
        proposed_capital_limit_usd=_text(capital),
        sizing_target_per_symbol_usd=_text(capital * Decimal(".16")),
        existing_engine_order_cap_usd=_text(capital * Decimal(".20")),
        existing_engine_symbol_cap_usd=_text(capital * Decimal(".20")),
        existing_engine_total_exposure_cap_usd=_text(capital * Decimal(".80")),
        existing_engine_daily_stop_trigger_usd=_text(capital * Decimal(".02")),
        stop_is_loss_guarantee=False,
        assumptions=[
            "REFERENCE_PRICES_ONLY",
            "HYPOTHETICAL_DEDICATED_CASH_EQUALS_CAPITAL",
            "NO_HOLDINGS_ALL_SYMBOLS_HAVE_ENTRY_SIGNAL",
            "ACCOUNT_NAV_AT_LEAST_PROPOSED_CAPITAL_NOT_VERIFIED",
            "ACTUAL_ENGINE_MAY_APPLY_LOWER_ACCOUNT_AND_ROUTER_LIMITS",
        ],
        readiness_not_established=[
            "VERIFIED_ACCOUNT_NAV_AND_UNENCUMBERED_USD_CASH",
            "QUALIFIED_HISTORY_STRATEGY_FORWARD_AND_EXECUTION_PARITY",
            "SEPARATE_INTRADAY_CAPITAL_AND_STRATEGY_APPROVAL",
            "PRODUCTION_INTRADAY_AUTHORITY_AND_ACCOUNT_GATEWAY",
            "PRODUCTION_ORDER_FILL_EXIT_RECONCILIATION_EVIDENCE",
        ],
        any_reference_share_fundable=any(r["hypothetical_shares"] for r in rows),
        all_symbols_reference_fundable=all(r["hypothetical_shares"] for r in rows),
        hypothetical_remaining_cash_usd=_text(cash),
        symbols=rows,
    )
