"""Bridge trusted in-process account readers and source-timed quotes to execution.

Verification flags belong to the account reader contract, not an operator file.
The current KIS diagnostic reader fails this contract; buying power is never cash.
"""

import asyncio
import re
from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.broker.intraday_inputs import EXCHANGES, PREFIXES, SourceQuote
from auto_invest.execution.intraday import Observation, validate_observation

READ_TIMEOUT_SECONDS = 30


class ObservationError(ValueError):
    """Closed local reasons only; never expose a broker response."""


def _stamp(value):
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except Exception:
        raise ObservationError("ACCOUNT_TIME_INVALID") from None


def _amount(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,18}(\.[0-9]{1,12})?", value):
        raise ObservationError("ACCOUNT_AMOUNT_INVALID")
    return Decimal(value)


def build_observation(account, quotes, *, now):
    """Consume a validated reader result; do not derive or approve account totals."""
    if not isinstance(account, dict) or account.get("currency") != "USD":
        raise ObservationError("ACCOUNT_CURRENCY_OR_SHAPE")
    for field, reason in (
        ("pagination_complete", "ACCOUNT_PAGINATION_UNVERIFIED"),
        ("full_account_scope_verified", "ACCOUNT_SCOPE_UNVERIFIED"),
        ("cash_aggregation_verified", "ACCOUNT_CASH_UNVERIFIED"),
        ("nav_verified", "ACCOUNT_NAV_UNVERIFIED"),
    ):
        if account.get(field) is not True:
            raise ObservationError(reason)
    if account.get("unverified_assets") != {}:
        raise ObservationError("ACCOUNT_UNVERIFIED_ASSETS")
    started = _stamp(account.get("observation_started_at"))
    completed = _stamp(account.get("observation_completed_at"))
    clock = _stamp(now)
    if not started <= completed <= clock or not 0 <= (clock - started).total_seconds() <= 30:
        raise ObservationError("ACCOUNT_BATCH_STALE")
    cash, nav = _amount(account.get("execution_cash")), _amount(account.get("nav"))
    positions, sellable = {}, {}
    raw_positions = account.get("positions")
    if not isinstance(raw_positions, dict):
        raise ObservationError("ACCOUNT_POSITIONS_INVALID")
    for symbol, row in raw_positions.items():
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,31}", symbol):
            raise ObservationError("ACCOUNT_SYMBOL_INVALID")
        if not isinstance(row, dict):
            raise ObservationError("ACCOUNT_POSITIONS_INVALID")
        qty, available = row.get("quantity"), row.get("sellable_quantity")
        if type(qty) is not int or type(available) is not int or not 0 <= available <= qty:
            raise ObservationError("ACCOUNT_POSITIONS_INVALID")
        positions[symbol], sellable[symbol] = qty, available
    orders = account.get("open_orders")
    if not isinstance(orders, list) or any(not isinstance(row, dict) for row in orders):
        raise ObservationError("ACCOUNT_ORDERS_INVALID")
    order_ids = tuple(row.get("order_id") for row in orders)
    if any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", value)
           for value in order_ids):
        raise ObservationError("ACCOUNT_ORDERS_INVALID")
    if not isinstance(quotes, dict):
        raise ObservationError("ACCOUNT_QUOTES_INVALID")
    marks, times = {}, {}
    for symbol, quote in quotes.items():
        if not isinstance(quote, SourceQuote) or symbol != quote.symbol:
            raise ObservationError("ACCOUNT_QUOTES_INVALID")
        if (quote.exchange not in PREFIXES or quote.market_type != "1"
                or quote.rsym != PREFIXES[quote.exchange] + symbol
                or (symbol in EXCHANGES and quote.exchange != EXCHANGES[symbol])):
            raise ObservationError("ACCOUNT_QUOTES_INVALID")
        source, received = _stamp(quote.source_at), _stamp(quote.received_at)
        if not source <= received <= clock:
            raise ObservationError("ACCOUNT_QUOTE_TIME_INVALID")
        marks[symbol], times[symbol] = quote.last, source
    view = Observation(started, cash, nav, positions, marks, order_ids, sellable, times)
    try:
        # Cancellation may use fresh account data with an older source quote.
        # The engine checks these original timestamps before pricing any order.
        validate_observation(view, clock, set(), require_fresh_marks=False)
    except Exception:
        raise ObservationError("ACCOUNT_EXECUTION_CONTRACT_INVALID") from None
    return view


class ExecutionObserver:
    """An asynchronous account reader plus the existing synchronous quote cache."""

    def __init__(self, read_account, quote_snapshot, *, now=lambda: datetime.now(UTC)):
        self.read_account, self.quote_snapshot, self.now = read_account, quote_snapshot, now

    async def __call__(self):
        started = _stamp(self.now())
        try:
            account = await asyncio.wait_for(self.read_account(), READ_TIMEOUT_SECONDS)
            quotes = self.quote_snapshot()
            clock = _stamp(self.now())
            if not 0 <= (clock - started).total_seconds() <= 30:
                raise ObservationError("ACCOUNT_COLLECTION_STALE")
            return build_observation(account, quotes, now=clock)
        except ObservationError:
            raise
        except Exception:
            raise ObservationError("ACCOUNT_INPUT_UNAVAILABLE") from None
