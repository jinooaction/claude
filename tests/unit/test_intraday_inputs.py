from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from auto_invest.broker.intraday_inputs import (
    KOREA,
    NEW_YORK,
    InputError,
    StrictQuoteFeed,
    approval_key,
    buying_power,
    parse_trades,
    subscription_key,
)

NOW = datetime(2026, 9, 8, 14, 30, tzinfo=UTC)


def record(symbol="QQQ", *, at=NOW, short=False, **changes):
    row = ["0"] * 26
    row[0], row[1] = subscription_key(symbol), symbol
    row[3] = at.astimezone(NEW_YORK).strftime("%Y%m%d")
    fmt = "%y%m%d" if short else "%Y%m%d"
    row[4:8] = [
        at.astimezone(NEW_YORK).strftime(fmt), at.astimezone(NEW_YORK).strftime("%H%M%S"),
        at.astimezone(KOREA).strftime(fmt), at.astimezone(KOREA).strftime("%H%M%S"),
    ]
    row[11], row[15], row[16], row[25] = "100.00", "99.99", "100.01", "1"
    for index, value in changes.items():
        row[int(index)] = value
    return row


def frame(*records):
    return "0|HDFSCNT0|" + str(len(records)).zfill(3) + "|" + "^".join(sum(records, []))


def parse(raw, *, now=NOW):
    return parse_trades(
        raw, subscribed={subscription_key(s): s for s in ("SPY", "QQQ")}, received_at=now,
    )


@pytest.mark.parametrize("short", [False, True])
def test_multiple_records_preserve_source_time_and_field_alignment(short):
    earlier = NOW - timedelta(seconds=4)
    quotes = parse(frame(record(short=short, at=earlier), record("SPY", short=short)))
    assert [q.symbol for q in quotes] == ["QQQ", "SPY"]
    assert quotes[0].source_at == earlier
    assert quotes[0].received_at == NOW
    assert quotes[0].bid == Decimal("99.99")
    assert not quotes[0].is_fresh(NOW + timedelta(seconds=27))
    assert quotes[0].public()["consolidated_market"] is False


@pytest.mark.parametrize("raw", [
    b"\xff", "0|HDFSCNT0|0|", "1|HDFSCNT0|1|x", "0|OTHER|1|x",
    "0|HDFSCNT0|101|x", "0|HDFSCNT0|1.0|x", "0|HDFSCNT0|1|x|y",
    "0|HDFSCNT0|1|" + "^".join(record()[1:]), "a" * 65537,
])
def test_reject_unsupported_frames(raw):
    with pytest.raises(InputError):
        parse(raw)


@pytest.mark.parametrize(("field", "value"), [
    (0, "DNASSPY"), (1, "SPY"), (11, "NaN"), (11, "Infinity"), (11, "0"),
    (11, "-1"), (15, "-1"), (15, "101"), (25, "2"), (25, "3"),
    (6, "260231"), (6, "20250908"), (7, "999999"), (5, "103001"),
])
def test_reject_bad_record_atomically(field, value):
    with pytest.raises(InputError):
        parse(frame(record("SPY"), record(**{str(field): value})))


@pytest.mark.parametrize("seconds", [-31, 1])
def test_late_and_future_frames_do_not_become_fresh_at_receipt(seconds):
    with pytest.raises(InputError, match="STALE_OR_FUTURE"):
        parse(frame(record(at=NOW + timedelta(seconds=seconds))))


def test_winter_midnight_in_korea_uses_local_event_date():
    at = datetime(2026, 1, 8, 20, 0, tzinfo=UTC)
    q, = parse(frame(record(at=at)), now=at)
    assert q.source_date_text == "20260109"
    assert q.local_date_text == "20260108"
    assert q.source_at == at


@pytest.mark.asyncio
async def test_feed_rejects_unacknowledged_and_time_regression_without_partial_update():
    feed = StrictQuoteFeed(("QQQ", "SPY"), now=lambda: NOW)
    feed.connected = True
    with pytest.raises(InputError, match="ACKNOWLEDGED"):
        await feed._handle(frame(record()), None)
    assert feed.snapshot() == {}
    feed.acknowledged = set(feed.subscribed)
    await feed._handle(frame(record()), None)
    with pytest.raises(InputError, match="REGRESSION"):
        await feed._handle(frame(record("SPY"), record(at=NOW - timedelta(seconds=1))), None)
    assert set(feed.snapshot()) == {"QQQ"}


class Client:
    def __init__(self, *, row=None, header="", status=200, code="0"):
        self.calls = []
        self.row = row if row is not None else dict(
            tr_crcy_cd="USD", ovrs_ord_psbl_amt="240.00", max_ord_psbl_qty="2",
            frcr_ord_psbl_amt1="99999", ovrs_max_ord_psbl_qty="999",
        )
        self.header, self.status, self.code = header, status, code

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return httpx.Response(
            self.status, json=dict(rt_cd=self.code, output=self.row),
            headers={"tr_cont": self.header}, request=httpx.Request(method, "https://kis.invalid"),
        )


async def power(client, **kwargs):
    args = dict(
        symbol="SPY", limit_price="120.00", account="1234567801", access_token="secret-token",
        app_key="secret-key", app_secret="secret-app", now=lambda: NOW,
    )
    return await buying_power(client, **(args | kwargs))


@pytest.mark.asyncio
async def test_buying_power_binds_exact_symbol_market_price_not_integrated_cash():
    client = Client()
    result = await power(client)
    assert result.foreign_orderable_amount == Decimal("240")
    assert result.foreign_orderable_qty == 2
    method, path, request = client.calls[0]
    assert method == "GET" and path.endswith("inquire-psamount")
    assert request["params"] == dict(
        CANO="12345678", ACNT_PRDT_CD="01", OVRS_EXCG_CD="AMEX",
        OVRS_ORD_UNPR="120.00", ITEM_CD="SPY",
    )
    assert not hasattr(result, "cash") and not hasattr(result, "nav")


@pytest.mark.asyncio
@pytest.mark.parametrize(("field", "value"), [
    ("tr_crcy_cd", "KRW"), ("ovrs_ord_psbl_amt", None), ("ovrs_ord_psbl_amt", "-1"),
    ("max_ord_psbl_qty", "1.5"), ("max_ord_psbl_qty", "NaN"),
])
async def test_bad_buying_power_does_not_fallback_to_integrated_amount(field, value):
    client = Client()
    client.row[field] = value
    with pytest.raises(InputError):
        await power(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [
    dict(symbol="AAPL"), dict(limit_price="0"), dict(limit_price="1.001"),
    dict(limit_price="Infinity"), dict(account="wrong"),
])
async def test_invalid_order_inputs_make_no_network_call(params):
    client = Client()
    with pytest.raises(InputError):
        await power(client, **params)
    assert client.calls == []


@pytest.mark.asyncio
async def test_slow_buying_power_and_broker_errors_are_closed_and_redacted():
    times = iter([NOW, NOW + timedelta(seconds=31)])
    with pytest.raises(InputError, match="STALE_BUYING_POWER"):
        await power(Client(), now=lambda: next(times))
    with pytest.raises(InputError, match="BUYING_POWER_REJECTED"):
        await power(Client(code="secret rejected account"))
    with pytest.raises(InputError, match="TRANSPORT_FAILED"):
        await power(Client(status=500))
    with pytest.raises(InputError, match="UNEXPECTED_BUYING_POWER_PAGE"):
        await power(Client(header="M"))


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [None, {}, [], "", "bad key", "x" * 8193])
async def test_approval_key_requires_actual_nonempty_string(key):
    class Auth:
        async def request(self, method, url, **kwargs):
            assert method == "POST" and url.endswith("/oauth2/Approval")
            return httpx.Response(
                200, json=dict(approval_key=key), request=httpx.Request(method, url),
            )

    with pytest.raises(InputError, match="QUOTE_AUTHENTICATION_FAILED"):
        await approval_key(Auth(), app_key="offline", app_secret="offline")


@pytest.mark.asyncio
async def test_application_heartbeat_sends_pong_without_refreshing_a_quote():
    class Transport:
        def __init__(self):
            self.pongs = []

        async def pong(self, data):
            self.pongs.append(data)

        async def send(self, data):
            raise AssertionError("KIS heartbeat uses websocket pong, not a text echo")

    feed = StrictQuoteFeed(("QQQ",), now=lambda: NOW)
    transport = Transport()
    raw = '{"header":{"tr_id":"PINGPONG"}}'
    await feed._handle(raw, transport)
    assert transport.pongs == [raw]
    assert not feed.snapshot()
