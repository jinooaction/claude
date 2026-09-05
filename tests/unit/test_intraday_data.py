from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from auto_invest.market_data.intraday import (
    DataError,
    ReadTransport,
    collect_alpaca,
    normalize,
    write_batch,
)

NOW = datetime(2026, 9, 4, 21, tzinfo=UTC)


def raw():
    return {"t": "2026-09-04T13:30:00Z", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000}


def test_normalize_closed_regular_only():
    assert normalize("SPY", raw(), NOW)["timestamp_utc"] == "2026-09-04T13:30:00Z"
    assert normalize("SPY", raw() | {"t": "2026-09-04T12:00:00Z"}, NOW) is None
    assert normalize("SPY", raw(), datetime(2026, 9, 4, 13, 32, tzinfo=UTC)) is None
    for change in ({"v": 1.5}, {"o": float("nan")}, {"h": 50}, {"t": "2026-09-04T13:31:00Z"}):
        with pytest.raises(DataError):
            normalize("SPY", raw() | change, NOW)


@pytest.mark.asyncio
async def test_alpaca_pages_and_redacted_errors(tmp_path: Path):
    requests = []

    def handler(req):
        requests.append(req)
        assert req.method == "GET"
        assert req.url.params["feed"] == "sip"
        if len(requests) == 1:
            return httpx.Response(200, json={"bars": {"SPY": [raw()]}, "next_page_token": "next"})
        assert req.url.params["page_token"] == "next"
        return httpx.Response(
            200,
            json={
                "bars": {s: [raw()] for s in ("QQQ", "IWM", "TLT", "GLD")},
                "next_page_token": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = ReadTransport(client, interval=0)
        batch = await collect_alpaca(
            transport,
            {"APCA_API_KEY_ID": "private-key", "APCA_API_SECRET_KEY": "private-secret"},
            datetime(2026, 9, 4, tzinfo=UTC),
            NOW.replace(hour=20),
            NOW,
        )
    assert len(batch["bars"]) == 5
    write_batch(tmp_path / "batch", batch)
    assert "private-key" not in (tmp_path / "batch" / "manifest.json").read_text()
    with pytest.raises(FileExistsError):
        write_batch(tmp_path / "batch", batch)


@pytest.mark.asyncio
async def test_missing_credentials_never_calls_http():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: pytest.fail("network"))
    ) as client:
        with pytest.raises(DataError, match="DATA_ACCESS_REQUIRED"):
            await collect_alpaca(
                ReadTransport(client), {}, NOW.replace(year=2023), NOW.replace(hour=20), NOW
            )


@pytest.mark.asyncio
async def test_endpoint_allowlist_and_retry_bound():
    count = 0

    def handler(req):
        nonlocal count
        count += 1
        return httpx.Response(503, text="secret body")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = ReadTransport(client, interval=0, backoff=0)
        with pytest.raises(DataError, match="HTTP_503"):
            await transport.request("GET", "https://data.alpaca.markets/v2/stocks/bars")
        assert count == 4
        with pytest.raises(DataError, match="ENDPOINT_DENIED"):
            await transport.request("POST", "https://api.alpaca.markets/v2/orders")
        assert count == 4


@pytest.mark.asyncio
async def test_kis_trade_venues_and_datetime(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import auto_invest.market_data.intraday as module

    async def token(*args, **kwargs):
        return SimpleNamespace(access_token="private-token")

    monkeypatch.setattr(module, "get_valid_token", token)

    def handler(req):
        symbol = req.url.params["SYMB"]
        assert req.url.params["EXCD"] == ("NAS" if symbol in {"QQQ", "TLT"} else "AMS")
        assert req.url.params["NMIN"] == "5"
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "output2": [
                    dict(
                        xymd="20260904",
                        xhms="093000",
                        open="100",
                        high="101",
                        low="99",
                        last="100",
                        evol="1000",
                    )
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await module.collect_kis(
            ReadTransport(client, interval=0),
            {"KIS_APP_KEY": "key", "KIS_APP_SECRET": "secret"},
            datetime(2026, 9, 4, 13, 30, tzinfo=UTC),
            NOW.replace(hour=20),
            NOW,
            tmp_path / "token.json",
        )
    assert len(batch["bars"]) == 5
    assert all(b["timestamp_utc"] == "2026-09-04T13:30:00Z" for b in batch["bars"])
    assert "private-token" not in str(batch)


@pytest.mark.asyncio
async def test_repeated_pages_fail_closed():
    def handler(req):
        return httpx.Response(200, json={"bars": {"SPY": [raw()]}, "next_page_token": "same"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DataError, match="REPEATED_PAGE"):
            await collect_alpaca(
                ReadTransport(client, interval=0),
                {"APCA_API_KEY_ID": "key", "APCA_API_SECRET_KEY": "secret"},
                NOW.replace(year=2023),
                NOW.replace(hour=20),
                NOW,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("code,expected_calls", [(401, 1), (403, 1), (429, 4)])
async def test_auth_and_rate_failure_codes(code, expected_calls):
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(code, text="never-log-this-secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DataError, match=f"DATA_HTTP_{code}") as exc:
            await ReadTransport(client, interval=0, backoff=0).request(
                "GET", "https://data.alpaca.markets/v2/stocks/bars"
            )
        assert "secret" not in str(exc.value)
        assert len(seen) == expected_calls
