"""Bridge trusted in-process account readers and source-timed quotes to execution.

Verification flags belong to the account reader contract, not an operator file.
The current KIS diagnostic reader fails this contract; buying power is never cash.
"""

import asyncio
import re
from datetime import UTC, datetime
from decimal import Decimal, localcontext

from auto_invest.broker.auth import get_valid_token
from auto_invest.broker.domestic_account import observe_domestic_account
from auto_invest.broker.intraday_account import observe_account
from auto_invest.broker.intraday_cash_baseline import observe_cash_baseline
from auto_invest.broker.intraday_inputs import EXCHANGES, PREFIXES, REST_URL, SourceQuote
from auto_invest.execution.intraday import (
    Observation,
    ReportedAssetValue,
    validate_observation,
    validate_reported_assets,
)
from auto_invest.execution.intraday_cash_ledger import CashLedgerError, compute_net_cash
from auto_invest.logging_config import register_secret

READ_TIMEOUT_SECONDS = 30


class ObservationError(ValueError):
    """Closed local reasons only; never expose a broker response."""


def _reported_asset_inputs(snapshot):
    """Extract provided values only; leave scope and unverified assets untouched."""
    values = {}
    for symbol, asset in snapshot["unverified_assets"].items():
        if (symbol in EXCHANGES or asset.get("reported_market_code") != "OTCB"
                or asset.get("reported_valuation_usd") is None):
            continue
        quantity = _amount(asset.get("reported_quantity"))
        if not quantity or quantity != quantity.to_integral_value():
            continue
        amount = _amount(asset["reported_valuation_usd"])
        values[symbol] = dict(quantity=int(quantity), amount_usd=str(amount),
            observation_started_at=snapshot["observation_started_at"],
            observation_completed_at=snapshot["observation_completed_at"])
    return values


def _stamp(value):
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except Exception:
        raise ObservationError("ACCOUNT_TIME_INVALID") from None


def _amount(value, *, signed=False):
    pattern = r"-?[0-9]{1,18}(\.[0-9]{1,12})?" if signed else r"[0-9]{1,18}(\.[0-9]{1,12})?"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ObservationError("ACCOUNT_AMOUNT_INVALID")
    return Decimal(value)


def build_observation(account, quotes, *, now):
    """Consume verified cash/scope; optionally value every reported equity here.

    net_cash includes all non-equity balances and liabilities, while
    execution_cash is cash available to the executor. Selecting the calculation
    basis does not establish either value's provenance or scope verification.
    Non-strategy holdings may use explicit broker-reported valuations. Their
    query intervals never stand in for source timestamps on executable quotes.
    """
    if not isinstance(account, dict) or account.get("currency") != "USD":
        raise ObservationError("ACCOUNT_CURRENCY_OR_SHAPE")
    for field, reason in (
        ("pagination_complete", "ACCOUNT_PAGINATION_UNVERIFIED"),
        ("full_account_scope_verified", "ACCOUNT_SCOPE_UNVERIFIED"),
        ("cash_aggregation_verified", "ACCOUNT_CASH_UNVERIFIED"),
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
    cash = _amount(account.get("execution_cash"))
    basis = account.get("valuation_basis", "verified_report")
    if basis == "verified_report":
        if account.get("nav_verified") is not True:
            raise ObservationError("ACCOUNT_NAV_UNVERIFIED")
        nav = _amount(account.get("nav"))
    elif basis in {"net_cash_and_listed_equities", "net_cash_and_reported_equities"}:
        net_cash = _amount(account.get("net_cash"), signed=True)
    elif basis == "cash_ledger_and_listed_equities":
        try:
            net_cash = compute_net_cash(
                account.get("cash_ledger"), observation_started_at=started,
                observation_completed_at=completed,
            )
        except CashLedgerError as exc:
            raise ObservationError(str(exc)) from None
    else:
        raise ObservationError("ACCOUNT_VALUATION_BASIS_INVALID")
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
    reported = {}
    raw_reported = account.get("reported_asset_values", {})
    if (not isinstance(raw_reported, dict) or len(raw_reported) > 10000
            or (raw_reported and basis != "net_cash_and_reported_equities")):
        raise ObservationError("ACCOUNT_REPORTED_ASSETS_BASIS")
    for symbol, row in raw_reported.items():
        if not isinstance(row, dict):
            raise ObservationError("ACCOUNT_REPORTED_ASSETS_SHAPE")
        reported[symbol] = ReportedAssetValue(
            row.get("quantity"), _amount(row.get("amount_usd")),
            _stamp(row.get("observation_started_at")),
            _stamp(row.get("observation_completed_at")),
        )
    try:
        validate_reported_assets(reported, positions, marks, observed_at=started,
                                 now=completed, required=set())
    except ValueError:
        raise ObservationError("ACCOUNT_REPORTED_ASSETS_INVALID") from None
    if basis in {"net_cash_and_listed_equities", "cash_ledger_and_listed_equities",
                 "net_cash_and_reported_equities"}:
        held = {symbol for symbol, qty in positions.items() if qty}
        if len(held) > 10000 or any(positions[symbol] > 10**18 for symbol in held):
            raise ObservationError("ACCOUNT_POSITIONS_INVALID")
        if held - (marks.keys() | reported.keys()):
            raise ObservationError("ACCOUNT_NAV_MARK_MISSING")
        if any(not isinstance(marks[symbol], Decimal) or not marks[symbol].is_finite()
               or not 0 < marks[symbol] < Decimal("1e18")
               or marks[symbol].as_tuple().exponent < -12 for symbol in held - reported.keys()):
            raise ObservationError("ACCOUNT_NAV_MARK_INVALID")
        with localcontext() as context:
            context.prec = 80
            nav = net_cash + sum((reported[symbol].amount_usd if symbol in reported
                                 else positions[symbol] * marks[symbol]
                                 for symbol in held), Decimal(0))
    view = Observation(started, cash, nav, positions, marks, order_ids, sellable, times, reported)
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


class KISExecutionObserver(ExecutionObserver):
    """Read using the executor's own account, client and refreshed credentials.

    Authentication may POST to tokenP; all account requests are GET. Successful
    authentication never changes the account reader's verification conclusions.
    """

    def __init__(self, authority, quote_snapshot, *, token_cache, now=lambda: datetime.now(UTC)):
        self.authority = authority
        self.account = authority.account_no
        self.broker = authority.broker
        self.http = self.broker._client
        self.token_cache = token_cache
        self._credential_identity = (authority.app_key, authority.app_secret)
        self._read_lock = asyncio.Lock()
        self._check_connection()
        for value in (self.account, *self._credential_identity):
            register_secret(value)
        super().__init__(self._read, quote_snapshot, now=now)

    def _check_connection(self):
        if (self.authority.account_no != self.account
                or self.authority.broker is not self.broker
                or self.broker._client is not self.http
                or (self.authority.app_key, self.authority.app_secret)
                != self._credential_identity
                or str(self.http.base_url).rstrip("/") != REST_URL.rstrip("/")
                or self.http.follow_redirects
                or not re.fullmatch(r"[0-9]{10}", self.account)
                or any(not isinstance(v, str) or not v for v in self._credential_identity)):
            raise ObservationError("ACCOUNT_CONNECTION_INVALID")

    async def _read(self):
        async with self._read_lock:
            await self.refresh_credentials()
            result = await observe_account(
                self.broker, access_token=self.authority.access_token,
                app_key=self.authority.app_key, app_secret=self.authority.app_secret,
                account=self.account, now=self.now,
            )
            self._check_connection()
            result["reported_asset_values"] = _reported_asset_inputs(result)
            result["reported_cash_baseline"] = await observe_cash_baseline(
                self.broker, access_token=self.authority.access_token,
                app_key=self.authority.app_key, app_secret=self.authority.app_secret,
                account=self.account, now=self.now,
            )
            self._check_connection()
            result["reported_domestic_account"] = await observe_domestic_account(
                self.broker, access_token=self.authority.access_token,
                app_key=self.authority.app_key, app_secret=self.authority.app_secret,
                account=self.account, now=self.now,
            )
            self._check_connection()
            return result

    async def refresh_credentials(self):
        self._check_connection()
        try:
            token = await asyncio.wait_for(get_valid_token(
                self.http, base_url=REST_URL,
                app_key=self.authority.app_key, app_secret=self.authority.app_secret,
                cache_path=self.token_cache, now=self.now(),
            ), READ_TIMEOUT_SECONDS)
        except Exception:
            raise ObservationError("ACCOUNT_AUTHENTICATION_UNAVAILABLE") from None
        self._check_connection()
        self.authority.access_token = token.access_token
