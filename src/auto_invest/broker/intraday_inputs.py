"""KIS source-timed quotes and order-specific foreign buying power (spec 184).

These inputs do not establish whole-account cash/NAV or authorize broker writes.
The old receipt-timed realtime feed remains separate from this strict consumer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from auto_invest.broker.overseas import _kis_headers, _split_account
from auto_invest.broker.realtime import build_subscribe_frame
from auto_invest.logging_config import register_secret

TR_ID = "HDFSCNT0"
REST_URL = "https://openapi.koreainvestment.com:9443"
WS_URL = "ws://ops.koreainvestment.com:21000/tryitout"
EXCHANGES = {"SPY": "AMEX", "QQQ": "NASD", "IWM": "AMEX", "TLT": "NASD", "GLD": "AMEX"}
PREFIXES = {"AMEX": "DAMS", "NASD": "DNAS", "NYSE": "DNYS"}
KOREA = ZoneInfo("Asia/Seoul")
NEW_YORK = ZoneInfo("America/New_York")
NUMBER = re.compile(r"[0-9]{1,18}(?:\.[0-9]{1,12})?")


class InputError(ValueError):
    """Fixed local codes; never include external response bodies or credentials."""


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InputError("INVALID_CLOCK")
    return value.astimezone(UTC)


def _amount(value: str, *, positive=False, whole=False) -> Decimal:
    if not isinstance(value, str) or not NUMBER.fullmatch(value.strip()):
        raise InputError("INVALID_AMOUNT")
    result = Decimal(value)
    if positive and result <= 0 or whole and result != result.to_integral_value():
        raise InputError("INVALID_AMOUNT")
    return result


def subscription_key(symbol: str) -> str:
    if symbol not in EXCHANGES:
        raise InputError("SYMBOL_NOT_ALLOWED")
    return PREFIXES[EXCHANGES[symbol]] + symbol


def _source_time(day: str, clock: str, zone: ZoneInfo, received: datetime) -> datetime:
    if not re.fullmatch(r"(?:[0-9]{6}|[0-9]{8})", day) or not re.fullmatch(r"[0-9]{6}", clock):
        raise InputError("INVALID_SOURCE_TIME")
    if len(day) == 6:
        # The portal permits YYMMDD. Resolve only near the receipt day, never a
        # free-standing century guess; freshness and both time zones are checked.
        day = str(received.astimezone(zone).year)[:2] + day
    try:
        naive = datetime.strptime(day + clock, "%Y%m%d%H%M%S")
        result = naive.replace(tzinfo=zone).astimezone(UTC)
    except ValueError:
        raise InputError("INVALID_SOURCE_TIME") from None
    if abs((result - received).total_seconds()) > 86400:
        raise InputError("SOURCE_DATE_OUT_OF_RANGE")
    if result.astimezone(zone).replace(tzinfo=None) != naive:
        raise InputError("INVALID_SOURCE_TIME")
    return result


@dataclass(frozen=True)
class SourceQuote:
    symbol: str
    exchange: str
    rsym: str
    last: Decimal
    bid: Decimal | None
    ask: Decimal | None
    source_at: datetime
    received_at: datetime
    source_date_text: str
    source_time_text: str
    local_date_text: str
    local_time_text: str
    market_type: str

    def is_fresh(self, now: datetime) -> bool:
        return 0 <= (_aware(now) - self.source_at).total_seconds() <= 30

    def public(self) -> dict:
        return dict(
            symbol=self.symbol, exchange=self.exchange, last=str(self.last),
            bid=str(self.bid) if self.bid is not None else None,
            ask=str(self.ask) if self.ask is not None else None,
            source_at=self.source_at.isoformat(), received_at=self.received_at.isoformat(),
            source_contract="KIS_HDFSCNT0_26", consolidated_market=False,
        )


def parse_trades(raw: str | bytes, *, subscribed: Mapping[str, str], received_at: datetime,
                 exchanges=None):
    """Validate an entire frame atomically; no 25-field or receipt-time fallback."""
    received = _aware(received_at)
    markets = EXCHANGES if exchanges is None else exchanges
    if not isinstance(raw, str | bytes) or len(raw) > 65536:
        raise InputError("INVALID_FRAME")
    try:
        raw = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    except UnicodeError:
        raise InputError("INVALID_FRAME") from None
    parts = raw.split("|")
    if len(parts) != 4 or parts[0] != "0" or parts[1] != TR_ID:
        raise InputError("INVALID_FRAME_HEADER")
    if not re.fullmatch(r"[0-9]{1,3}", parts[2]) or not 1 <= int(parts[2]) <= 100:
        raise InputError("INVALID_FRAME_COUNT")
    fields = parts[3].split("^")
    if len(fields) != 26 * int(parts[2]):
        raise InputError("INVALID_FRAME_WIDTH")
    result = []
    for offset in range(0, len(fields), 26):
        row = fields[offset:offset + 26]
        rsym, symbol = row[:2]
        market = markets.get(symbol)
        if (subscribed.get(rsym) != symbol or market not in PREFIXES
                or rsym != PREFIXES[market] + symbol):
            raise InputError("UNSUBSCRIBED_QUOTE")
        if row[25] != "1":
            raise InputError("NON_REGULAR_QUOTE")
        source = _source_time(row[6], row[7], KOREA, received)
        local = _source_time(row[4], row[5], NEW_YORK, received)
        if source != local:
            raise InputError("SOURCE_TIMEZONE_MISMATCH")
        if not 0 <= (received - source).total_seconds() <= 30:
            raise InputError("STALE_OR_FUTURE_QUOTE")
        last = _amount(row[11], positive=True)
        bid = _amount(row[15]) if row[15] else Decimal(0)
        ask = _amount(row[16]) if row[16] else Decimal(0)
        if bid and ask and bid > ask:
            raise InputError("CROSSED_QUOTE")
        result.append(SourceQuote(
            symbol, market, rsym, last, bid or None, ask or None,
            source, received, row[6], row[7], row[4], row[5], row[25],
        ))
    return tuple(result)


class StrictQuoteFeed:
    """Read-only feed with bounded reconnects and immediate cache invalidation.

    ``serve`` owns the connection in the caller's task. Cancellation closes it.
    Production defaults are fixed; tests may inject a local transport factory.
    """

    def __init__(self, symbols=tuple(EXCHANGES), *, now=lambda: datetime.now(UTC),
                 valuation_exchanges=None):
        if not symbols or len(set(symbols)) != len(symbols):
            raise InputError("INVALID_SUBSCRIPTIONS")
        if valuation_exchanges is None:
            self.exchanges = dict(EXCHANGES)
            self.subscribed = {subscription_key(s): s for s in symbols}
        else:
            additional = dict(valuation_exchanges)
            if (not set(additional) <= set(symbols) or len(symbols) > 40
                    or any(not isinstance(s, str) or not re.fullmatch(r"[A-Z][A-Z0-9.]{0,19}", s)
                           or m not in PREFIXES for s, m in additional.items())
                    or set(additional) & set(EXCHANGES)
                    or set(symbols) - (set(additional) | set(EXCHANGES))):
                raise InputError("INVALID_VALUATION_SUBSCRIPTIONS")
            self.exchanges = {s: EXCHANGES[s] for s in symbols if s in EXCHANGES} | additional
            self.subscribed = {PREFIXES[self.exchanges[s]] + s: s for s in symbols}
        self.now: Callable[[], datetime] = now
        self.quotes: dict[str, SourceQuote] = {}
        self.connected = False
        self.reason = "NOT_CONNECTED"
        self.acknowledged: set[str] = set()

    def snapshot(self) -> dict[str, SourceQuote]:
        if not self.connected:
            return {}
        return {s: q for s, q in self.quotes.items() if q.is_fresh(self.now())}

    async def _handle(self, raw, transport):
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeError:
                raise InputError("INVALID_FRAME") from None
        if not isinstance(raw, str) or len(raw) > 65536:
            raise InputError("INVALID_FRAME")
        if raw.startswith("{"):
            try:
                obj = json.loads(raw)
                header = obj["header"]
                tr_id = header["tr_id"]
                if tr_id == "PINGPONG":
                    await transport.pong(raw)
                    return
                if tr_id != TR_ID or header.get("tr_key") not in self.subscribed:
                    raise InputError("UNEXPECTED_CONTROL")
                if obj["body"].get("rt_cd") != "0":
                    raise InputError("SUBSCRIPTION_REJECTED")
                self.acknowledged.add(header["tr_key"])
                return
            except InputError:
                raise
            except (ValueError, TypeError, KeyError, AttributeError):
                raise InputError("INVALID_OR_REJECTED_CONTROL") from None
        trades = parse_trades(raw, subscribed=self.subscribed, received_at=self.now(),
                              exchanges=self.exchanges)
        pending = dict(self.quotes)
        for trade in trades:
            if trade.rsym not in self.acknowledged:
                raise InputError("SUBSCRIPTION_NOT_ACKNOWLEDGED")
            previous = pending.get(trade.symbol)
            if previous and trade.source_at < previous.source_at:
                raise InputError("QUOTE_TIME_REGRESSION")
            pending[trade.symbol] = trade
        self.quotes = pending

    async def serve(self, *, approval, transport_factory=None, attempts=3):
        if type(attempts) is not int or not 1 <= attempts <= 5:
            raise InputError("INVALID_RECONNECT_LIMIT")
        if transport_factory is None:
            transport_factory = connect_kis
        for attempt in range(attempts):
            self.quotes.clear()
            self.acknowledged.clear()
            transport = None
            try:
                key = await approval()
                if not isinstance(key, str) or not key:
                    raise InputError("INVALID_APPROVAL_KEY")
                transport = await transport_factory()
                for rsym in self.subscribed:
                    await transport.send(build_subscribe_frame(key, tr_id=TR_ID, tr_key=rsym))
                    await asyncio.sleep(0.1)
                self.connected, self.reason = True, "WAIT_QUOTES"
                while True:
                    raw = await asyncio.wait_for(transport.recv(), timeout=40)
                    await self._handle(raw, transport)
                    self.reason = "RECEIVING" if self.snapshot() else "WAIT_QUOTES"
            except asyncio.CancelledError:
                self.reason = "STOPPED"
                raise
            except Exception as exc:
                self.reason = str(exc) if isinstance(exc, InputError) else "QUOTE_TRANSPORT_FAILED"
            finally:
                self.connected = False
                self.quotes.clear()
                self.acknowledged.clear()
                if transport is not None:
                    with suppress(Exception):
                        await asyncio.wait_for(transport.close(), timeout=5)
            if attempt + 1 < attempts:
                await asyncio.sleep(2 ** attempt)


async def connect_kis():
    from websockets.asyncio.client import connect

    # No global logger changes. Never emit approval frames, even under root DEBUG.
    private_logger = logging.Logger("auto_invest.private_quote_transport")
    private_logger.disabled = True
    return await connect(
        WS_URL, proxy=None, open_timeout=10, close_timeout=3, max_size=65536,
        max_queue=16, ping_interval=20, ping_timeout=20, logger=private_logger,
    )


async def approval_key(client, *, app_key, app_secret):
    """Caller provides the shared rate-limited/retrying HTTP client."""
    try:
        response = await client.request(
            "POST", REST_URL + "/oauth2/Approval",
            json=dict(grant_type="client_credentials", appkey=app_key, secretkey=app_secret),
            headers={"content-type": "application/json"},
        )
        response.raise_for_status()
        key = response.json()["approval_key"]
        if not isinstance(key, str) or not 1 <= len(key) <= 8192 or any(c.isspace() for c in key):
            raise ValueError
    except Exception:
        raise InputError("QUOTE_AUTHENTICATION_FAILED") from None
    register_secret(key)
    return key


@dataclass(frozen=True)
class BuyingPower:
    symbol: str
    exchange: str
    limit_price: Decimal
    foreign_orderable_amount: Decimal
    foreign_orderable_qty: int
    started_at: datetime
    completed_at: datetime


async def buying_power(
    client, *, symbol, limit_price, account, access_token, app_key, app_secret,
    now=lambda: datetime.now(UTC),
):
    subscription_key(symbol)
    price = _amount(str(limit_price), positive=True)
    if price != price.quantize(Decimal(".01")):
        raise InputError("INVALID_LIMIT_PRECISION")
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise InputError("INVALID_ACCOUNT")
    started = _aware(now())
    cano, product = _split_account(account)
    try:
        response = await client.request(
            "GET", "/uapi/overseas-stock/v1/trading/inquire-psamount",
            headers=_kis_headers(
                access_token=access_token, app_key=app_key, app_secret=app_secret,
                tr_id="TTTS3007R",
            ),
            params=dict(
                CANO=cano, ACNT_PRDT_CD=product, OVRS_EXCG_CD=EXCHANGES[symbol],
                OVRS_ORD_UNPR=format(price, ".2f"), ITEM_CD=symbol,
            ),
        )
        response.raise_for_status()
        body = response.json()
    except Exception:
        raise InputError("BUYING_POWER_TRANSPORT_FAILED") from None
    completed = _aware(now())
    if not timedelta(0) <= completed - started <= timedelta(seconds=30):
        raise InputError("STALE_BUYING_POWER")
    if not isinstance(body, dict) or body.get("rt_cd") != "0":
        raise InputError("BUYING_POWER_REJECTED")
    if response.headers.get("tr_cont", "").strip() not in {"", "D", "E"}:
        raise InputError("UNEXPECTED_BUYING_POWER_PAGE")
    row = body.get("output")
    if isinstance(row, list) and len(row) == 1:
        row = row[0]
    if not isinstance(row, dict) or row.get("tr_crcy_cd") != "USD":
        raise InputError("INVALID_BUYING_POWER_CURRENCY")
    amount = _amount(row.get("ovrs_ord_psbl_amt"))
    quantity = int(_amount(row.get("max_ord_psbl_qty"), whole=True))
    return BuyingPower(symbol, EXCHANGES[symbol], price, amount, quantity, started, completed)
