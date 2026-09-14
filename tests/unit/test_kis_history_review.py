import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from auto_invest.market_data.intraday import CALENDAR, NY, SYMBOLS, DataError, ReadTransport
from auto_invest.market_data.kis_history_depth import probe_kis_history_depth
from auto_invest.market_data.kis_history_review import acquire_kis_history_review

ENV = {"KIS_APP_KEY": "key_private_1234567", "KIS_APP_SECRET": "secret_private_1234567"}


def rows(day):
    start = CALENDAR.session_open(day).to_pydatetime()
    end = CALENDAR.session_close(day).to_pydatetime()
    return [dict(xymd=(start + timedelta(minutes=i * 5)).astimezone(NY).strftime("%Y%m%d"),
                 xhms=(start + timedelta(minutes=i * 5)).astimezone(NY).strftime("%H%M%S"),
                 open="100", high="102", low="99", last="101", evol="1000")
            for i in range(int((end - start).total_seconds() / 300))]


@pytest.mark.asyncio
@pytest.mark.parametrize("gap", [False, True])
async def test_http_sources_and_open_day_filter(tmp_path, monkeypatch, gap):
    monkeypatch.setattr("auto_invest.market_data.kis_history_depth.get_valid_token",
                        AsyncMock(return_value=SimpleNamespace(access_token="token_private_1234567")))
    counts = {s: 0 for s in SYMBOLS}

    def handler(request):
        assert request.method == "GET"
        symbol = request.url.params["SYMB"]
        assert request.url.params["EXCD"] == ("NAS" if symbol in {"QQQ", "TLT"} else "AMS")
        page = counts[symbol]
        counts[symbol] += 1
        if page == 0:
            values = rows("2023-01-04") + rows("2023-01-05")[:1]
            if gap and symbol == "GLD":
                values = values[1:]
        elif page == 1:
            values = rows("2023-01-03")
        else:
            values = []
        return httpx.Response(200, json=dict(rt_cd="0", output2=values))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await acquire_kis_history_review(ReadTransport(client, interval=0), ENV,
            tmp_path / "token.json", tmp_path / "history",
            now=datetime(2023, 1, 5, 15, tzinfo=UTC))
    assert counts == {s: 4 for s in SYMBOLS}
    assert result["first_common_date"] == "2023-01-03"
    assert result["last_common_date"] == "2023-01-04"
    assert result["complete_sessions"] == (1 if gap else 2)
    assert result["missing_calendar_sessions"] == (1 if gap else 0)
    assert result["independent_evidence_valid"] is True
    assert result["decision"]["passed"] is False and result["live_eligible"] is False
    run = next((tmp_path / "history").glob("review-*"))
    source = json.loads((run / "dataset/source.json").read_text())
    assert len(source["source_runs"]) == 5
    assert all(not r["timestamp_utc"].startswith("2023-01-05") for r in source["bars"])
    assert len(list((run / "sources").glob("run-*/page-*.json"))) == 20
    assert (run / "completed.json").exists()
    diagnostic = json.loads((run / "short-window-diagnostic.json").read_text())
    assert diagnostic["promotion_eligible"] is False
    assert len(diagnostic["runs"]) == (0 if gap else 36)
    assert diagnostic["status"] == ("DATA_INCOMPLETE" if gap else "REPLAYED")


@pytest.mark.asyncio
async def test_unlisted_symbol_refused_before_auth_or_network(tmp_path):
    with pytest.raises(DataError, match="SYMBOL_DENIED"):
        await probe_kis_history_depth(None, ENV, tmp_path / "token", tmp_path / "history",
                                      symbol="OTHER")
    assert not (tmp_path / "history").exists()
