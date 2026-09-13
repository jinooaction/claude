"""Explicit reported-holdings contract for fixed-allocation execution.

This verifies the supported reported asset categories and current equity rows;
it does not certify account net cash, NAV, or absence of future broker charges.
"""

import asyncio

from auto_invest.broker.intraday_inputs import EXCHANGES, PREFIXES, SourceQuote
from auto_invest.execution.intraday import (
    BudgetObservation,
    ReportedAssetValue,
    validate_observation,
)
from auto_invest.execution.intraday_observation import (
    READ_TIMEOUT_SECONDS,
    KISExecutionObserver,
    ObservationError,
    _amount,
    _reported_asset_inputs,
    _stamp,
)


def build_budget_observation(account, quotes, *, now):
    if not isinstance(account, dict) or account.get("currency") != "USD":
        raise ObservationError("ACCOUNT_CURRENCY_OR_SHAPE")
    if account.get("pagination_complete") is not True:
        raise ObservationError("ACCOUNT_PAGINATION_UNVERIFIED")
    scope = account.get("reported_asset_scope", {})
    coverage = account.get("reported_holdings_coverage", {})
    if (not isinstance(scope, dict) or scope.get("status") != "MATCH"
            or scope.get("reported_asset_categories_matched") is not True
            or scope.get("scope") != "SETTLEMENT_CATEGORIES_WITH_CURRENT_INPUTS"
            or scope.get("category_count") != 19
            or not isinstance(coverage, dict) or coverage.get("status") != "MATCH"
            or coverage.get("scope") != "CURRENT_OVERSEAS_EQUITIES_ONLY"
            or coverage.get("equity_holdings_matched") is not True):
        raise ObservationError("BUDGET_REPORTED_SCOPE_UNAVAILABLE")
    started = _stamp(account.get("observation_started_at"))
    completed, clock = _stamp(account.get("observation_completed_at")), _stamp(now)
    if not started <= completed <= clock or not 0 <= (clock - started).total_seconds() <= 30:
        raise ObservationError("ACCOUNT_BATCH_STALE")
    positions, sellable, reported = {}, {}, {}
    raw, unsupported = account.get("positions"), account.get("unverified_assets")
    if not isinstance(raw, dict) or not isinstance(unsupported, dict):
        raise ObservationError("ACCOUNT_POSITIONS_INVALID")
    for symbol, row in raw.items():
        if not isinstance(row, dict):
            raise ObservationError("ACCOUNT_POSITIONS_INVALID")
        positions[symbol], sellable[symbol] = row.get("quantity"), row.get("sellable_quantity")
    converted = _reported_asset_inputs(account)
    if set(converted) != set(unsupported) or set(unsupported) & set(positions):
        raise ObservationError("ACCOUNT_UNVERIFIED_ASSETS")
    for symbol, row in converted.items():
        available = _amount(unsupported[symbol].get("reported_sellable_quantity"))
        if available != available.to_integral_value():
            raise ObservationError("ACCOUNT_POSITIONS_INVALID")
        positions[symbol], sellable[symbol] = row["quantity"], int(available)
        reported[symbol] = ReportedAssetValue(
            row["quantity"], _amount(row["amount_usd"]),
            _stamp(row["observation_started_at"]), _stamp(row["observation_completed_at"]),
        )
    count = coverage.get("positive_holding_count")
    if (type(count) is not int or count != sum(type(q) is int and q > 0 for q in positions.values())
            or scope.get("current_positive_holding_count") != count):
        raise ObservationError("BUDGET_REPORTED_SCOPE_UNAVAILABLE")
    orders = account.get("open_orders")
    if not isinstance(orders, list) or any(not isinstance(row, dict) for row in orders):
        raise ObservationError("ACCOUNT_ORDERS_INVALID")
    if not isinstance(quotes, dict):
        raise ObservationError("ACCOUNT_QUOTES_INVALID")
    marks, times = {}, {}
    for symbol, quote in quotes.items():
        if (not isinstance(quote, SourceQuote) or symbol != quote.symbol
                or quote.exchange not in PREFIXES or quote.market_type != "1"
                or quote.rsym != PREFIXES[quote.exchange] + symbol
                or symbol in EXCHANGES and quote.exchange != EXCHANGES[symbol]):
            raise ObservationError("ACCOUNT_QUOTES_INVALID")
        source, received = _stamp(quote.source_at), _stamp(quote.received_at)
        if not source <= received <= clock:
            raise ObservationError("ACCOUNT_QUOTE_TIME_INVALID")
        marks[symbol], times[symbol] = quote.last, source
    view = BudgetObservation(
        started, positions, marks, tuple(row.get("order_id") for row in orders),
        sellable, times, reported,
    )
    try:
        validate_observation(view, clock, set(), require_fresh_marks=False)
    except (ValueError, TypeError):
        raise ObservationError("BUDGET_OBSERVATION_INVALID") from None
    return view


class KISBudgetObserver(KISExecutionObserver):
    async def __call__(self):
        started = _stamp(self.now())
        try:
            account = await asyncio.wait_for(self._read(), READ_TIMEOUT_SECONDS)
            quotes, clock = self.quote_snapshot(), _stamp(self.now())
            if not 0 <= (clock - started).total_seconds() <= 30:
                raise ObservationError("ACCOUNT_COLLECTION_STALE")
            return build_budget_observation(account, quotes, now=clock)
        except ObservationError:
            raise
        except Exception:
            raise ObservationError("ACCOUNT_INPUT_UNAVAILABLE") from None
