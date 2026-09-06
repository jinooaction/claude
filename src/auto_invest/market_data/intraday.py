"""Spec 181: fixed-endpoint, read-only five-minute data acquisition.

No orders or trading database access. Provider identities are deliberately distinct.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import hashlib
import json
import math
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import httpx

from auto_invest.broker.auth import get_valid_token
from auto_invest.broker.client import CircuitBreaker, CircuitBreakerOpen

SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "GLD")
ALPACA = "https://data.alpaca.markets/v2/stocks/bars"
KIS_BASE = "https://openapi.koreainvestment.com:9443"
KIS_BARS = KIS_BASE + "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
CALENDAR = xcals.get_calendar("XNYS")
NY = ZoneInfo("America/New_York")


class DataError(ValueError):
    """Public, sanitized failure code (never contains response bodies or credentials)."""


def encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def utc(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.utcoffset() != timedelta(0):
            raise ValueError
        return moment.astimezone(UTC)
    except (ValueError, TypeError, AttributeError) as exc:
        raise DataError("INVALID_UTC") from exc


class ReadTransport:
    """2 requests/s, four tries, 429/5xx/network backoff, persistent process breaker."""

    def __init__(self, client: httpx.AsyncClient, *, interval: float = 0.5, backoff: float = 1):
        self.client = client
        self.interval = interval
        self.backoff = backoff
        self.last_request = 0.0
        self.breaker = CircuitBreaker(failure_threshold=4, cooldown_seconds=60)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        # Compatibility with the existing redacting OAuth cache/refresh implementation.
        return await self.request("POST", url, **kwargs)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if (method, url) not in {
            ("GET", ALPACA),
            ("GET", KIS_BARS),
            ("POST", KIS_BASE + "/oauth2/tokenP"),
        }:
            raise DataError("ENDPOINT_DENIED")
        for attempt in range(4):
            try:
                self.breaker.before_request()
            except CircuitBreakerOpen as exc:
                raise DataError("DATA_CIRCUIT_OPEN") from exc
            await asyncio.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            retry_after = 0.0
            try:
                response = await self.client.request(method, url, **kwargs)
                if response.status_code < 300:
                    self.breaker.record_success()
                    return response
                code = f"DATA_HTTP_{response.status_code}"
                transient = response.status_code == 429 or response.status_code >= 500
                with contextlib.suppress(ValueError):
                    retry_after = min(60, max(0, float(response.headers.get("Retry-After", "0"))))
            except httpx.TransportError:
                code, transient = "DATA_TRANSPORT_FAILURE", True
            if not transient:
                raise DataError(code)
            self.breaker.record_failure()
            if attempt == 3:
                raise DataError(code)
            await asyncio.sleep(max(retry_after, self.backoff * 2**attempt))
        raise DataError("DATA_RETRY_EXHAUSTED")


def normalize(symbol: str, row: dict, observed: datetime) -> dict | None:
    """Convert one provider bar; exclude extended hours and not-yet-closed bars."""
    try:
        if symbol not in SYMBOLS:
            raise DataError("SYMBOL_DENIED")
        stamp = utc(row["t"])
        if stamp.minute % 5 or stamp.second or stamp.microsecond:
            raise DataError("BAR_ALIGNMENT")
        session = stamp.astimezone(NY).date()
        if not CALENDAR.is_session(session):
            return None
        opening = CALENDAR.session_open(session).to_pydatetime()
        closing = CALENDAR.session_close(session).to_pydatetime()
        if not opening <= stamp < closing or stamp + timedelta(minutes=5) > observed:
            return None
        prices = [float(row[key]) for key in ("o", "h", "l", "c")]
        volume = float(row["v"])
        if any(isinstance(row[k], bool) for k in ("o", "h", "l", "c", "v")):
            raise DataError("BAR_NUMERIC")
        if any(not math.isfinite(p) or p <= 0 for p in prices):
            raise DataError("BAR_PRICE")
        op, hi, lo, cl = prices
        if lo > min(op, cl) or hi < max(op, cl) or lo > hi:
            raise DataError("BAR_OHLC")
        if not math.isfinite(volume) or volume <= 0 or not volume.is_integer():
            raise DataError("BAR_VOLUME")
        return dict(
            timestamp_utc=iso(stamp),
            symbol=symbol,
            open=op,
            high=hi,
            low=lo,
            close=cl,
            volume=int(volume),
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, DataError):
            raise
        raise DataError("BAR_SCHEMA") from exc


def _keys(env: dict, names: tuple[str, ...]) -> list[str]:
    if any(not env.get(name) for name in names):
        raise DataError("DATA_ACCESS_REQUIRED: " + ",".join(names))
    return [env[name] for name in names]


def _json(response: httpx.Response) -> dict:
    try:
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError
        return body
    except ValueError as exc:
        raise DataError("DATA_RESPONSE_SCHEMA") from exc


def _batch(provider: str, start: datetime, end: datetime, now: datetime) -> dict:
    if any(x.tzinfo is None for x in (start, end, now)) or not start < end <= now:
        raise DataError("DATA_INTERVAL")
    return {
        "provider": provider,
        "start": iso(start),
        "end": iso(end),
        "retrieved_at_utc": iso(now),
        "pages": [],
        "bars": [],
        "synthetic": False,
    }


def _deduplicate(batch: dict) -> dict:
    by_key = {}
    for row in batch["bars"]:
        key = (row["timestamp_utc"], row["symbol"])
        if key in by_key and by_key[key] != row:
            raise DataError("CONFLICTING_BAR_REVISION")
        by_key[key] = row
    batch["bars"] = [by_key[k] for k in sorted(by_key)]
    if {r["symbol"] for r in batch["bars"]} != set(SYMBOLS):
        raise DataError("INCOMPLETE_SYMBOL_COVERAGE")
    return batch


async def collect_alpaca(transport, env, start, end, now, *, max_pages=1000) -> dict:
    key, secret = _keys(env, ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"))
    batch = _batch("alpaca-sip-split", start, end, now)
    if end > now - timedelta(minutes=16):
        raise DataError("SIP_HISTORY_REQUIRES_16_MINUTE_DELAY")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    params = dict(
        symbols=",".join(SYMBOLS),
        timeframe="5Min",
        feed="sip",
        adjustment="split",
        start=iso(start),
        end=iso(end),
        sort="asc",
        limit="10000",
    )
    tokens = set()
    for _ in range(max_pages):
        body = _json(await transport.request("GET", ALPACA, headers=headers, params=params))
        bars = body.get("bars")
        if not isinstance(bars, dict) or set(bars) - set(SYMBOLS):
            raise DataError("DATA_RESPONSE_SCHEMA")
        batch["pages"].append(body)
        for symbol, values in bars.items():
            if not isinstance(values, list):
                raise DataError("DATA_RESPONSE_SCHEMA")
            for raw in values:
                row = normalize(symbol, raw, now)
                if row and start <= utc(row["timestamp_utc"]) < end:
                    batch["bars"].append(row)
        token = body.get("next_page_token")
        if not token:
            return _deduplicate(batch)
        if not isinstance(token, str) or token in tokens:
            raise DataError("REPEATED_PAGE_TOKEN")
        tokens.add(token)
        params["page_token"] = token
    raise DataError("DATA_PAGE_LIMIT")


async def collect_kis(transport, env, start, end, now, cache_path, *, max_pages=40) -> dict:
    key, secret = _keys(env, ("KIS_APP_KEY", "KIS_APP_SECRET"))
    batch = _batch("kis-nasdaq-partial-unadjusted", start, end, now)
    if start < now - timedelta(days=30):
        raise DataError("KIS_HISTORY_LIMIT_30_DAYS")
    token = await get_valid_token(
        transport, base_url=KIS_BASE, app_key=key, app_secret=secret, cache_path=cache_path, now=now
    )
    headers = {
        "authorization": "Bearer " + token.access_token,
        "appkey": key,
        "appsecret": secret,
        "tr_id": "HHDFS76950200",
        "custtype": "P",
        "tr_cont": "",
    }
    for symbol in SYMBOLS:
        params = dict(
            AUTH="",
            EXCD="NAS" if symbol in {"QQQ", "TLT"} else "AMS",
            SYMB=symbol,
            NMIN="5",
            PINC="1",
            NEXT="",
            NREC="120",
            FILL="",
            KEYB="",
        )
        previous = None
        for _ in range(max_pages):
            body = _json(await transport.request("GET", KIS_BARS, headers=headers, params=params))
            if body.get("rt_cd") != "0" or not isinstance(body.get("output2"), list):
                raise DataError("KIS_BAR_RESPONSE_REJECTED")
            batch["pages"].append({"symbol": symbol, "response": body})
            values = body["output2"]
            if not values:
                break
            times = []
            for raw in values:
                try:
                    moment = (
                        datetime.strptime(raw["xymd"] + raw["xhms"], "%Y%m%d%H%M%S")
                        .replace(tzinfo=NY)
                        .astimezone(UTC)
                    )
                    times.append(moment)
                    row = normalize(
                        symbol,
                        dict(
                            t=iso(moment),
                            o=raw["open"],
                            h=raw["high"],
                            l=raw["low"],
                            c=raw["last"],
                            v=raw["evol"],
                        ),
                        now,
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise DataError("KIS_BAR_SCHEMA") from exc
                if row and start <= moment < end:
                    batch["bars"].append(row)
            oldest = min(times)
            if previous is not None and oldest >= previous:
                raise DataError("KIS_PAGINATION_NOT_ADVANCING")
            if oldest <= start:
                break
            previous = oldest
            params.update(
                NEXT="1",
                KEYB=(oldest - timedelta(minutes=5)).astimezone(NY).strftime("%Y%m%d%H%M%S"),
            )
        else:
            raise DataError("DATA_PAGE_LIMIT")
    return _deduplicate(batch)


def last_completed_session(now: datetime):
    """Only completed XNYS sessions; allow a minute for the closing bar to settle."""
    if now.tzinfo is None:
        raise DataError("INVALID_UTC")
    session = CALENDAR.date_to_session(now.astimezone(NY).date(), direction="previous")
    if CALENDAR.session_close(session).to_pydatetime() + timedelta(minutes=1) > now:
        session = CALENDAR.previous_session(session)
    return session.date()


async def probe_kis_session(transport, env, now, cache_path, output_dir) -> dict:
    """Read-only production contract probe, not strategy/promotion evidence."""
    session = last_completed_session(now)
    opening = CALENDAR.session_open(session).to_pydatetime()
    closing = CALENDAR.session_close(session).to_pydatetime()
    batch = await collect_kis(transport, env, opening, closing, now, cache_path)
    count = int((closing - opening).total_seconds() // 300)
    expected = {
        (iso(opening + timedelta(minutes=5 * i)), symbol)
        for i in range(count)
        for symbol in SYMBOLS
    }
    actual = [(row["timestamp_utc"], row["symbol"]) for row in batch["bars"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise DataError("INCOMPLETE_SESSION_GRID")
    write_batch(output_dir, batch)
    return dict(
        status="INTRADAY_DATA_CONTRACT_OK",
        session=str(session),
        provider=batch["provider"],
        bars_per_symbol=dict.fromkeys(SYMBOLS, count),
        dataset_sha256=digest(encode(batch)),
        orders_submitted=0,
        live_eligible=False,
        forward_promotion_eligible=False,
    )


def write_batch(path: Path, batch: dict) -> None:
    """New private directory only; manifest is written last as the completeness marker."""
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    raw = encode(batch)
    with (path / "source.json").open("xb") as handle:
        handle.write(raw)
    files = {}
    columns = ("timestamp_utc", "symbol", "open", "high", "low", "close", "volume")
    for symbol in SYMBOLS:
        rows = [r for r in batch["bars"] if r["symbol"] == symbol]
        csv_path = path / f"{symbol}.csv"
        with csv_path.open("x", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        files[symbol] = {
            "path": csv_path.name,
            "rows": len(rows),
            "sha256": digest(csv_path.read_bytes()),
        }
    manifest = dict(
        schema_version="1.0",
        dataset_id=digest(raw),
        provider=batch["provider"],
        retrieved_at_utc=batch["retrieved_at_utc"],
        base_timeframe_minutes=5,
        synthetic=batch["synthetic"],
        files=files,
        raw_sha256=digest(raw),
        adjustment_policy="split; dividends unadjusted"
        if batch["provider"] == "alpaca-sip-split"
        else "provider unadjusted; partial-market; revisions possible",
    )
    with (path / "manifest.json").open("xb") as handle:
        handle.write(encode(manifest))
