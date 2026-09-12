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
from auto_invest.execution.intraday_program import _StrategyQuoteView, _ValuationFeed

NOW = datetime(2026, 9, 10, 15, 0, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize("has_reported_asset", [False, True])
async def test_rest_discovers_market_but_only_source_timed_stream_values_account(
    monkeypatch, has_reported_asset,
):
    clock = [NOW]
    calls = []
    ready = asyncio.Event()
    connections = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json=dict(output=dict(
            last="99999" if request.url.params["EXCD"] == "AMS" else "",
        )))

    async def stream(feed, *, approval):
        connections.append(feed)
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

    async def read():
        report = dict(quantity=3, amount_usd="120", observation_started_at=NOW.isoformat(),
                      observation_completed_at=NOW.isoformat())
        return dict(reported_asset_values={"ORANY": report} if has_reported_asset else {},
                    unverified_assets={"ORANY": {}} if has_reported_asset else {})

    monkeypatch.setattr(StrictQuoteFeed, "serve", stream)
    async with httpx.AsyncClient(base_url="https://kis.invalid",
                                 transport=httpx.MockTransport(handler)) as broker:
        observer = SimpleNamespace(
            broker=broker, refresh_credentials=refresh, _read=read, _check_connection=lambda: None,
            authority=SimpleNamespace(access_token="test", app_key="test", app_secret="test"),
        )
        symbols = ["SCHX", "IAUM"] + (["ORANY"] if has_reported_asset else [])
        valuation = _ValuationFeed(observer, symbols, lambda: clock[0])
        assert valuation.snapshot() == {}
        task = asyncio.create_task(_StrategyQuoteView(valuation).serve(approval=refresh))
        try:
            await asyncio.wait_for(ready.wait(), 2)
            values = valuation.snapshot()
            assert set(values) == set(EXCHANGES) | {"SCHX", "IAUM"}
            assert all(q.last == 40 and q.source_at == NOW for q in values.values())
            assert all(values[s].exchange == "AMEX" for s in ("SCHX", "IAUM"))
            assert set(_StrategyQuoteView(valuation).snapshot()) == set(EXCHANGES)
            assert len(connections) == 1 and len(connections[0].subscribed) == 7
            assert set(StrictQuoteFeed().subscribed.values()) == set(EXCHANGES)
            for symbol in ("SCHX", "IAUM"):
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

    async def read():
        return dict(reported_asset_values={}, unverified_assets={})

    async with httpx.AsyncClient(base_url="https://kis.invalid", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=dict(output=dict(last=""))),
    )) as broker:
        observer = SimpleNamespace(
            broker=broker, refresh_credentials=refresh, _read=read, _check_connection=lambda: None,
            authority=SimpleNamespace(access_token="test", app_key="test", app_secret="test"),
        )
        valuation = _ValuationFeed(observer, ["ORANY"], lambda: NOW)
        from auto_invest.broker.overseas import QuoteUnavailable
        with pytest.raises(QuoteUnavailable):
            await valuation.serve(approval=refresh)
        assert valuation.snapshot() == {}


@pytest.mark.asyncio
async def test_known_unsupported_holding_without_report_is_not_hidden_from_subscription():
    async def read():
        return dict(reported_asset_values={}, unverified_assets={"ORANY": {
            "reported_market_code": "OTCB", "reported_valuation_usd": None}})

    async def approval():
        raise AssertionError("No stream should start")

    observer = SimpleNamespace(_read=read, _check_connection=lambda: None)
    feed = _ValuationFeed(observer, ["ORANY"], lambda: NOW)
    with pytest.raises(ValueError, match="^PROGRAM_REPORTED_ASSET_UNAVAILABLE$"):
        await feed.serve(approval=approval)
    assert feed.snapshot() == {}


@pytest.mark.parametrize("mapping", [
    {"SPY": "AMEX"}, {"ORANY": "OTCB"}, {"IAUM": "UNKNOWN"}, {"bad/name": "AMEX"},
])
def test_valuation_subscriptions_do_not_expand_strategy_or_guess_otc_exchange(mapping):
    with pytest.raises(InputError):
        StrictQuoteFeed(tuple(mapping), valuation_exchanges=mapping)


def test_total_subscription_limit_includes_strategy_symbols_before_network():
    with pytest.raises(ValueError, match="SUBSCRIPTION_LIMIT"):
        _ValuationFeed(None, [f"X{i}" for i in range(36)], lambda: NOW)
    external = {f"X{i}": "AMEX" for i in range(35)}
    feed = StrictQuoteFeed(tuple(EXCHANGES) + tuple(external), valuation_exchanges=external)
    assert len(feed.subscribed) == 40
    with pytest.raises(InputError, match="SUBSCRIPTIONS"):
        StrictQuoteFeed(tuple(EXCHANGES) + tuple(external) + ("MORE",),
                        valuation_exchanges=external | {"MORE": "AMEX"})
