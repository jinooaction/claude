import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.broker.intraday_inputs import (
    EXCHANGES,
    KOREA,
    NEW_YORK,
    InputError,
    StrictQuoteFeed,
    subscription_key,
)
from auto_invest.execution.intraday_program import _ValuationFeed

NOW = datetime(2026, 9, 10, 15, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_rest_discovers_market_but_only_source_timed_stream_values_account(monkeypatch):
    clock = [NOW]
    calls = []
    ready = asyncio.Event()

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json=dict(output=dict(
            last="99999" if request.url.params["EXCD"] == "AMS" else "",
        )))

    async def stream(feed, *, approval):
        await approval()
        feed.connected = True
        for key, symbol in feed.subscribed.items():
            feed.acknowledged.add(key)
            row = ["0"] * 26
            row[0:2] = [key, symbol]
            row[4:8] = [NOW.astimezone(NEW_YORK).strftime("%Y%m%d"),
                        NOW.astimezone(NEW_YORK).strftime("%H%M%S"),
                        NOW.astimezone(KOREA).strftime("%Y%m%d"),
                        NOW.astimezone(KOREA).strftime("%H%M%S")]
            row[11], row[15], row[16], row[25] = "40", "39", "41", "1"
            await feed._handle("0|HDFSCNT0|001|" + "^".join(row), None)
        ready.set()
        await asyncio.Event().wait()

    async def refresh():
        return None

    monkeypatch.setattr(StrictQuoteFeed, "serve", stream)
    async with httpx.AsyncClient(base_url="https://kis.invalid",
                                 transport=httpx.MockTransport(handler)) as broker:
        observer = SimpleNamespace(
            broker=broker, refresh_credentials=refresh, _check_connection=lambda: None,
            authority=SimpleNamespace(access_token="test", app_key="test", app_secret="test"),
        )
        valuation = _ValuationFeed(observer, ["SCHX", "IAUM"], lambda: clock[0])
        assert valuation.snapshot() == {}
        task = asyncio.create_task(valuation.serve(approval=refresh))
        try:
            await asyncio.wait_for(ready.wait(), 2)
            values = valuation.snapshot()
            assert set(values) == {"SCHX", "IAUM"}
            assert all(q.last == 40 and q.source_at == NOW for q in values.values())
            assert all(q.exchange == "AMEX" for q in values.values())
            assert set(StrictQuoteFeed().subscribed.values()) == set(EXCHANGES)
            for symbol in values:
                with pytest.raises(InputError, match="SYMBOL_NOT_ALLOWED"):
                    subscription_key(symbol)
            clock[0] += timedelta(seconds=31)
            assert valuation.snapshot() == {}
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert valuation.snapshot() == {}
        assert {r.url.params["SYMB"] for r in calls} == {"SCHX", "IAUM"}


@pytest.mark.asyncio
async def test_unresolved_otc_price_is_not_zero_or_a_receipt_timed_mark():
    async def refresh():
        return None

    async with httpx.AsyncClient(base_url="https://kis.invalid", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=dict(output=dict(last=""))),
    )) as broker:
        observer = SimpleNamespace(
            broker=broker, refresh_credentials=refresh, _check_connection=lambda: None,
            authority=SimpleNamespace(access_token="test", app_key="test", app_secret="test"),
        )
        valuation = _ValuationFeed(observer, ["ORANY"], lambda: NOW)
        from auto_invest.broker.overseas import QuoteUnavailable
        with pytest.raises(QuoteUnavailable):
            await valuation.serve(approval=refresh)
        assert valuation.snapshot() == {}


@pytest.mark.parametrize("mapping", [
    {"SPY": "AMEX"}, {"ORANY": "OTCB"}, {"IAUM": "UNKNOWN"}, {"bad/name": "AMEX"},
])
def test_valuation_subscriptions_do_not_expand_strategy_or_guess_otc_exchange(mapping):
    with pytest.raises(InputError):
        StrictQuoteFeed(tuple(mapping), valuation_exchanges=mapping)
