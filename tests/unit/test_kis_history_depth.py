import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from auto_invest.market_data.intraday import KIS_BARS, DataError, ReadTransport
from auto_invest.market_data.kis_history_depth import probe_kis_history_depth

ENV = {"KIS_APP_KEY": "private_test_app_key_123", "KIS_APP_SECRET": "private_test_secret_456"}


def bar(day="20230103", time="093000", volume="100"):
    return dict(xymd=day, xhms=time, open="100", high="102", low="99", last="101", evol=volume)


async def run(tmp_path, monkeypatch, bodies, limit=80):
    monkeypatch.setattr("auto_invest.market_data.kis_history_depth.get_valid_token",
                        AsyncMock(return_value=SimpleNamespace(access_token="private_token_789")))
    calls = []

    def handler(request):
        assert request.method == "GET" and str(request.url).split("?")[0] == KIS_BARS
        assert request.url.params["SYMB"] == "SPY" and request.url.params["NREC"] == "120"
        calls.append(dict(request.url.params))
        return httpx.Response(200, json=bodies[len(calls) - 1])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await probe_kis_history_depth(ReadTransport(client, interval=0), ENV,
            tmp_path / "token.json", tmp_path / "history", max_pages=limit)
    return result, calls


@pytest.mark.asyncio
async def test_old_history_is_observed_and_cursor_follows_last_bar(tmp_path, monkeypatch):
    bodies = [dict(rt_cd="0", output2=[bar(time="093500")]),
              dict(rt_cd="0", output2=[bar()]), dict(rt_cd="0", output2=[])]
    result, calls = await run(tmp_path, monkeypatch, bodies)
    assert calls[0]["KEYB"] == "" and calls[1]["KEYB"] == "20230103093000"
    assert calls[1]["NEXT"] == "1" and calls[2]["KEYB"] == "20230103092500"
    assert result["stop_reason"] == "EMPTY_PAGE" and result["regular_bars"] == 2
    assert result["observed_older_than_30_days"] is True
    assert result["provider_history_limit_proven"] is False and result["live_eligible"] is False
    source = next((tmp_path / "history").glob("run-*"))
    assert len(list(source.glob("page-*.json"))) == 3
    assert source.stat().st_mode & 0o077 == 0
    for path in source.glob("*.json"):
        assert path.stat().st_mode & 0o077 == 0
        assert "private_" not in path.read_text()
    assert json.loads((source / "completed.json").read_text())["orders_submitted"] == 0


@pytest.mark.asyncio
async def test_page_cap_does_not_claim_supplier_limit(tmp_path, monkeypatch):
    result, calls = await run(tmp_path, monkeypatch, [dict(rt_cd="0", output2=[bar()])], limit=1)
    assert result["stop_reason"] == "PAGE_LIMIT_REACHED" and len(calls) == 1
    assert result["provider_history_limit_proven"] is False


@pytest.mark.asyncio
async def test_repeating_page_stops_without_duplicate_inflation(tmp_path, monkeypatch):
    result, calls = await run(tmp_path, monkeypatch, [dict(rt_cd="0", output2=[bar()])] * 2)
    assert result["stop_reason"] == "CURSOR_NOT_ADVANCING"
    assert result["raw_unique_bars"] == 1 and len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["volume", "conflict", "schema", "reflection", "future"])
async def test_invalid_evidence_is_never_completed(tmp_path, monkeypatch, fault):
    bodies = [dict(rt_cd="0", output2=[bar()])]
    if fault == "volume":
        bodies[0]["output2"][0]["evol"] = "0.5"
    elif fault == "conflict":
        bodies.append(dict(rt_cd="0", output2=[bar(volume="200")]))
    elif fault == "schema":
        bodies[0] = dict(rt_cd="1", output2=[])
    elif fault == "reflection":
        bodies[0]["message"] = ENV["KIS_APP_KEY"]
    else:
        bodies[0]["output2"][0]["xymd"] = (datetime.now(UTC) + timedelta(days=5)).strftime("%Y%m%d")
    with pytest.raises(DataError):
        await run(tmp_path, monkeypatch, bodies)
    assert not list((tmp_path / "history").glob("*/completed.json"))
    assert all("private_" not in p.read_text() for p in (tmp_path / "history").glob("*/*.json"))


@pytest.mark.asyncio
async def test_page_cap_and_output_link_refused(tmp_path, monkeypatch):
    with pytest.raises(DataError, match="PAGE_LIMIT"):
        await run(tmp_path, monkeypatch, [], limit=81)
    (tmp_path / "real").mkdir()
    (tmp_path / "history").symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(DataError, match="OUTPUT_LINK"):
        await run(tmp_path, monkeypatch, [])
