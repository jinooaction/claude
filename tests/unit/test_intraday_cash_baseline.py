import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from auto_invest.broker.account_source_profile import CASH_FIELDS
from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.intraday_cash_baseline import (
    CURRENT,
    MARGIN,
    normalize_cash_baseline,
    observe_cash_baseline,
)

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


@pytest.mark.parametrize("field,value,expected", [
    ("tot_dncl_amt", "73145.0", "73145"),
    ("tot_dncl_amt", "73144", None),
    ("frst_bltn_exrt", "1000.00", "1000"),
    ("frst_bltn_exrt", "1001", None),
    ("frst_bltn_exrt", "NaN", None),
    ("frst_bltn_exrt", "0", None),
])
def test_optional_cash_metadata_requires_equal_before_and_after_values(field, value, expected):
    source = records()
    for record in (source[0], source[-1]):
        record["data"]["output3"]["tot_dncl_amt"] = "73145"
        record["data"]["output2"][0]["frst_bltn_exrt"] = "1000"
    row = (source[-1]["data"]["output3"] if field == "tot_dncl_amt" else
           source[-1]["data"]["output2"][0])
    row[field] = value
    result = normalize_cash_baseline(source, observed_at=NOW)
    key = "reported_krw_total_deposit" if field == "tot_dncl_amt" else "reported_usd_krw_rate"
    assert result[key] == expected
    assert result["status"] == "CALCULATED" and result["cash"] == "601.37"


def records():
    currency = dict(crcy_cd="USD", frcr_dncl_amt_2="601.37",
                    frcr_buy_mgn_amt="0", frcr_etc_mgna="0")
    current = dict(rt_cd="0", output2=[currency], output3=dict.fromkeys((
        "dncl_amt", "cma_evlu_amt", "tot_loan_amt", "ustl_buy_amt_smtl", "ustl_sll_amt_smtl",
    ), "0"))
    margin_row = dict(dict.fromkeys(CASH_FIELDS, "0"), crcy_cd="USD")
    margin_row["frcr_dncl_amt1"] = "601.3700"
    margin = dict(rt_cd="0", output=[dict(margin_row) for _ in range(10)] + [
        dict(dict.fromkeys(CASH_FIELDS, "0"), crcy_cd="") for _ in range(34)
    ])
    return [dict(endpoint=url, http_status=200, continuation="D", data=deepcopy(data),
                 started_at=(NOW - timedelta(seconds=6 - i * 2)).isoformat(),
                 received_at=(NOW - timedelta(seconds=5 - i * 2)).isoformat())
            for i, (url, data) in enumerate(((CURRENT, current), (MARGIN, margin),
                                              (CURRENT, current)))]


def test_independent_usd_row_is_used_once_despite_country_repetition():
    source = records()
    original = deepcopy(source)
    result = normalize_cash_baseline(source, observed_at=NOW)
    assert result["status"] == "CALCULATED" and result["cash"] == "601.37"
    assert result["usd_margin_row_count"] == 10
    assert result["full_account_verified"] is result["live_eligible"] is False
    assert source == original


@pytest.mark.parametrize("fault,reason", [
    ("duplicate_usd", "BASELINE_USD_ROW_NOT_UNIQUE"),
    ("changed", "BASELINE_CASH_CHANGED"),
    ("margin_difference", "BASELINE_MARGIN_DEPOSIT_DIFFERS"),
    ("margin_adjustment", "BASELINE_ADJUSTMENT_PRESENT"),
    ("blank_nonzero", "BASELINE_OTHER_CASH_OR_LIABILITY_PRESENT"),
    ("other_currency", "BASELINE_OTHER_CURRENCY_PRESENT"),
    ("loan", "BASELINE_OTHER_CASH_OR_LIABILITY_PRESENT"),
    ("bad_amount", "BASELINE_AMOUNT_INVALID"),
    ("missing_amount", "BASELINE_AMOUNT_INVALID"),
    ("page", "BASELINE_INCOMPLETE_REPORT"),
    ("bad_header", "BASELINE_INCOMPLETE_REPORT"),
    ("failed", "BASELINE_BROKER_RESPONSE_INVALID"),
    ("stale", "BASELINE_STALE"),
    ("reversed", "BASELINE_TIME_ORDER"),
])
def test_uncertain_or_changed_cash_never_yields_a_baseline(fault, reason):
    source = records()
    current, margin = source[0]["data"], source[1]["data"]["output"]
    if fault == "duplicate_usd":
        current["output2"] *= 2
    elif fault == "changed":
        source[2]["data"]["output2"][0]["frcr_dncl_amt_2"] = "602"
    elif fault == "margin_difference":
        margin[0]["frcr_dncl_amt1"] = "602"
    elif fault == "margin_adjustment":
        margin[0]["ustl_buy_amt"] = "1"
    elif fault == "blank_nonzero":
        margin[-1]["frcr_rcvb_amt"] = "1"
    elif fault == "other_currency":
        current["output2"].append(dict(current["output2"][0], crcy_cd="EUR"))
    elif fault == "loan":
        current["output3"]["tot_loan_amt"] = "1"
    elif fault == "bad_amount":
        current["output2"][0]["frcr_dncl_amt_2"] = "NaN"
    elif fault == "missing_amount":
        current["output2"][0].pop("frcr_dncl_amt_2")
    elif fault in {"page", "bad_header"}:
        source[1]["continuation"] = "M" if fault == "page" else []
    elif fault == "failed":
        source[1]["http_status"] = 500
    elif fault == "stale":
        source[0]["started_at"] = (NOW - timedelta(seconds=31)).isoformat()
    elif fault == "reversed":
        source[1]["started_at"] = source[0]["started_at"]
    result = normalize_cash_baseline(source, observed_at=NOW)
    assert result["status"] == "UNAVAILABLE" and result["cash"] is None
    assert result["reason"] == reason


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{"tr_cont": "D"}, {}, {"tr_cont": " "}])
async def test_actual_collector_owns_usd_query_scope_and_brackets_margin(headers):
    source, calls = records(), []

    def handle(request):
        index = len(calls)
        calls.append(request)
        assert request.method == "GET" and request.url.path == source[index]["endpoint"]
        assert request.url.params["CANO"] == "12345678"
        assert request.url.params["ACNT_PRDT_CD"] == "01"
        assert request.headers["authorization"] == "Bearer token"
        if request.url.path == CURRENT:
            assert request.url.params["WCRC_FRCR_DVSN_CD"] == "02"
            assert request.url.params["NATN_CD"] == "000"
        return httpx.Response(200, headers=headers, json=source[index]["data"])

    async with httpx.AsyncClient(base_url="https://kis.invalid",
                                transport=httpx.MockTransport(handle)) as client:
        result = await observe_cash_baseline(client, access_token="token", app_key="key",
            app_secret="secret", account="1234567801", now=lambda: NOW)
    assert result["cash"] == "601.37" and len(calls) == 3


@pytest.mark.asyncio
async def test_hung_transport_is_bounded_and_external_cancellation_propagates(monkeypatch):
    from auto_invest.broker import intraday_cash_baseline as module

    async def handle(request):
        await asyncio.Event().wait()

    async with httpx.AsyncClient(base_url="https://kis.invalid",
                                transport=httpx.MockTransport(handle)) as client:
        kwargs = dict(access_token="token", app_key="key", app_secret="secret",
                      account="1234567801", now=lambda: NOW)
        monkeypatch.setattr(module, "READ_TIMEOUT_SECONDS", 0.01)
        with pytest.raises(AccountReadError, match="^BASELINE_READ_TIMEOUT$"):
            await observe_cash_baseline(client, **kwargs)
        monkeypatch.setattr(module, "READ_TIMEOUT_SECONDS", 30)
        task = asyncio.create_task(observe_cash_baseline(client, **kwargs))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_invalid_clock_is_rejected_before_requests():
    calls = []

    def handle(request):
        calls.append(request)
        raise AssertionError("Unexpected request")

    async with httpx.AsyncClient(base_url="https://kis.invalid",
                                transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(AccountReadError, match="^BASELINE_TIME_INVALID$"):
            await observe_cash_baseline(client, access_token="token", app_key="key",
                app_secret="secret", account="1234567801", now=lambda: NOW.replace(tzinfo=None))
    assert calls == []
