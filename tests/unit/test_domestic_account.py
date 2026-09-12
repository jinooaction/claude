import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from auto_invest.broker.domestic_account import (
    ROW_FIELDS,
    SUMMARY_FIELDS,
    URL,
    observe_domestic_account,
    public_domestic_account,
)
from auto_invest.broker.intraday_account import AccountReadError

NOW = datetime(2026, 9, 12, tzinfo=UTC)


def body(symbol="005930", quantity="3"):
    row = dict(dict.fromkeys(ROW_FIELDS, "0"), pdno=symbol,
               hldg_qty=quantity, ord_psbl_qty=quantity, evlu_amt="12345")
    return dict(rt_cd="0", output1=[row], output2=[dict.fromkeys(SUMMARY_FIELDS, "0")],
                ctx_area_fk100="", ctx_area_nk100="")


async def read(handle, **kwargs):
    async with httpx.AsyncClient(base_url="https://kis.invalid",
                                transport=httpx.MockTransport(handle)) as client:
        return await observe_domestic_account(client, access_token="private-token",
            app_key="private-key", app_secret="private-secret", account="1234567801",
            now=kwargs.pop("now", lambda: NOW), **kwargs)


@pytest.mark.asyncio
async def test_current_domestic_pages_preserve_holdings_without_public_amounts():
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "GET" and request.url.path == URL
        assert request.headers["authorization"] == "Bearer private-token"
        assert request.headers["tr_id"] == "TTTC8434R"
        assert request.url.params["CANO"] == "12345678"
        assert request.url.params["ACNT_PRDT_CD"] == "01"
        assert request.url.params["INQR_DVSN"] == "02"
        assert request.url.params["PRCS_DVSN"] == "00"
        assert request.url.params["FUND_STTL_ICLD_YN"] == "Y"
        if len(requests) == 1:
            data = body()
            data.update(ctx_area_fk100="scope", ctx_area_nk100="page2")
            return httpx.Response(200, json=data, headers={"tr_cont": "M"})
        assert request.url.params["CTX_AREA_NK100"] == "page2"
        assert request.headers["tr_cont"] == "N"
        data = body("000660", "0")
        data["output1"][0]["evlu_amt"] = "0"
        data["output2"][0]["tot_loan_amt"] = "0.00"
        return httpx.Response(200, json=data, headers={"tr_cont": "E"})

    result = await read(handle)
    assert result["positions"]["005930"]["hldg_qty"] == "3"
    assert result["positions"]["005930"]["evlu_amt"] == "12345"
    public = public_domestic_account(result)
    assert public["holding_count"] == public["zero_quantity_row_count"] == 1
    assert public["page_count"] == 2 and not public["full_account_verified"]
    assert public["summary_states"]["tot_loan_amt"] == "ZERO"
    assert all(value not in json.dumps(public) for value in
               ("005930", "12345", "private-token", "1234567801"))


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,reason", [
    ("number", "DOMESTIC_INVALID_NUMBER"), ("negative", "DOMESTIC_NEGATIVE_HOLDING"),
    ("sellable", "DOMESTIC_SELLABLE_EXCEEDS_HOLDING"),
    ("rows", "DOMESTIC_HOLDINGS_SHAPE"), ("duplicate", "DOMESTIC_DUPLICATE_HOLDING"),
    ("summary", "DOMESTIC_SUMMARY_SHAPE"), ("header", "DOMESTIC_CONTINUATION_INVALID"),
    ("cursor", "DOMESTIC_CURSOR_INVALID"), ("stalled", "DOMESTIC_CURSOR_STALLED"),
    ("error", "DOMESTIC_TRANSPORT_OR_JSON_ERROR"),
])
async def test_incomplete_or_invalid_domestic_data_is_never_success(fault, reason):
    data, header, status = body(), "D", 200
    if fault == "number":
        data["output1"][0]["evlu_amt"] = "NaN"
    elif fault == "negative":
        data["output1"][0]["loan_amt"] = "-1"
    elif fault == "sellable":
        data["output1"][0]["ord_psbl_qty"] = "4"
    elif fault == "rows":
        data["output1"] *= 51
    elif fault == "duplicate":
        data["output1"] *= 2
    elif fault == "summary":
        data["output2"] = []
    elif fault == "header":
        header = "unknown"
    elif fault == "cursor":
        data.pop("ctx_area_nk100")
    elif fault == "stalled":
        header = "M"
    elif fault == "error":
        status, data = 500, dict(msg1="PRIVATE_BROKER_ERROR")
    original = deepcopy(data)
    with pytest.raises(AccountReadError, match=f"^{reason}$"):
        await read(lambda request: httpx.Response(status, json=data, headers={"tr_cont": header}))
    assert data == original


@pytest.mark.asyncio
async def test_page_summary_change_is_refused():
    calls = []

    def handle(request):
        calls.append(request)
        data = body(str(len(calls)))
        data.update(ctx_area_fk100="scope", ctx_area_nk100=str(len(calls)))
        data["output2"][0]["tot_loan_amt"] = str(len(calls))
        return httpx.Response(200, json=data, headers={"tr_cont": "M"})

    with pytest.raises(AccountReadError, match="^DOMESTIC_SUMMARY_CHANGED$"):
        await read(handle)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_slow_responses_and_cancelled_calls_do_not_return_partial_data(monkeypatch):
    from auto_invest.broker import domestic_account as module

    async def blocked(request):
        await asyncio.Event().wait()

    monkeypatch.setattr(module, "READ_TIMEOUT_SECONDS", 0.01)
    with pytest.raises(AccountReadError, match="^DOMESTIC_READ_TIMEOUT$"):
        await read(blocked)
    monkeypatch.setattr(module, "READ_TIMEOUT_SECONDS", 30)
    task = asyncio.create_task(read(blocked))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_stale_batch_is_refused_after_response():
    times = iter([NOW, NOW, NOW + timedelta(seconds=31)])
    with pytest.raises(AccountReadError, match="^DOMESTIC_STALE_BATCH$"):
        await read(lambda request: httpx.Response(200, json=body(), headers={"tr_cont": "D"}),
                   now=lambda: next(times))


@pytest.mark.asyncio
@pytest.mark.parametrize("repeat", [False, True])
async def test_cursor_cycle_and_page_limit_are_bounded(repeat):
    calls = []

    def handle(request):
        calls.append(request)
        data = body(str(len(calls)))
        data.update(ctx_area_fk100="scope", ctx_area_nk100="same" if repeat else str(len(calls)))
        return httpx.Response(200, json=data, headers={"tr_cont": "M"})

    reason = "DOMESTIC_CURSOR_STALLED" if repeat else "DOMESTIC_PAGE_LIMIT"
    with pytest.raises(AccountReadError, match=f"^{reason}$"):
        await read(handle, max_pages=2)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_negative_summary_is_preserved_without_becoming_usd_cash():
    data = body()
    data["output2"][0]["nass_amt"] = "-42"
    result = await read(lambda request: httpx.Response(200, json=data, headers={"tr_cont": "D"}))
    assert result["currency"] == "KRW" and result["summary"]["nass_amt"] == "-42"
    assert public_domestic_account(result)["summary_states"]["nass_amt"] == "NEGATIVE"
    assert result["full_account_verified"] is False
