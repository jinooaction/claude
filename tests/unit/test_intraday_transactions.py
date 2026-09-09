import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.intraday_transactions import (
    audit_settlements,
    observe_transactions,
    public_transactions,
)

NOW = datetime(2026, 9, 10, tzinfo=UTC)
ARGS = dict(account="1234567801", access_token="offline", app_key="offline",
            app_secret="offline", start_date="20260901", end_date="20260910", now=lambda: NOW)


def row():
    return dict(trad_dt="20260908", sttl_dt="20260910", pdno="SPY", crcy_cd="USD",
                sll_buy_dvsn_cd="02", ccld_qty="0.125", tr_frcr_amt2="75.25",
                frcr_excc_amt_1="75.40", dmst_frcr_fee1="0.10", frcr_fee1="0.05")


def body(**changes):
    return dict(dict(rt_cd="0", output1=[row()], output2={"dmst_fee_smtl": "0.10"},
                     ctx_area_fk100="", ctx_area_nk100=""), **changes)


def test_settlement_arithmetic_keeps_currencies_and_duplicate_transactions_separate():
    buy = row()
    sell = dict(row(), sll_buy_dvsn_cd="01", tr_frcr_amt2="80", frcr_excc_amt_1="79.85")
    euro = dict(row(), crcy_cd="EUR")
    result = audit_settlements([buy, buy, sell, euro])
    assert result["status"] == "MATCH"
    assert result["arithmetic_verified"] is True
    assert result["currency_totals"] == {
        "USD": dict(gross_buy="150.50", gross_sell="80", domestic_fee="0.30",
                    foreign_fee="0.15", net_settlement="-70.95"),
        "EUR": dict(gross_buy="75.25", gross_sell="0", domestic_fee="0.10",
                    foreign_fee="0.05", net_settlement="-75.40"),
    }


@pytest.mark.parametrize("changes", [
    {"frcr_excc_amt_1": "75.39"}, {"dmst_frcr_fee1": "0"},
    {"sll_buy_dvsn_cd": "01"}, {"frcr_excc_amt_1": "75.399999999999"},
])
def test_one_discrepancy_withholds_entire_validated_total(changes):
    result = audit_settlements([row(), dict(row(), **changes)])
    assert result["status"] == "MISMATCH"
    assert result["matched_row_count"] == 1
    assert result["mismatched_row_indices"] == [1]
    assert result["currency_totals"] is None
    assert result["arithmetic_verified"] is False


def test_empty_report_is_not_zero_cost_evidence():
    result = audit_settlements([])
    assert result["status"] == "NO_TRANSACTIONS"
    assert result["currency_totals"] is None
    assert result["arithmetic_verified"] is False


def test_high_precision_amounts_are_not_rounded_by_ambient_decimal_context():
    from decimal import localcontext

    value = dict(row(), tr_frcr_amt2="999999999999999999.000000000001",
                 dmst_frcr_fee1="0.000000000001", frcr_fee1="0.000000000001",
                 frcr_excc_amt_1="999999999999999999.000000000003")
    with localcontext() as context:
        context.prec = 6
        result = audit_settlements([value, value])
    assert result["arithmetic_verified"] is True
    assert result["currency_totals"]["USD"]["net_settlement"] == "-1999999999999999998.000000000006"


@pytest.mark.asyncio
async def test_all_pages_preserve_duplicate_rows_fractional_quantity_and_fee_components():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, headers={"tr_cont": "M" if len(calls) == 1 else "D"},
                              json=body(ctx_area_fk100="next", ctx_area_nk100="cursor"))

    async with httpx.AsyncClient(base_url="https://offline.invalid",
                                transport=httpx.MockTransport(handle)) as client:
        result = await observe_transactions(client, **ARGS)
    assert result["rows"] == [row(), row()]
    assert result["source_rows"] == [row(), row()]
    assert result["summary_pages"] == [[{"dmst_fee_smtl": "0.10"}]] * 2
    assert all(request.method == "GET" for request in calls)
    assert calls[0].headers["tr_id"] == "CTOS4001R"
    assert calls[1].headers["tr_cont"] == "N"
    assert calls[1].url.params["CTX_AREA_NK100"] == "cursor"
    assert calls[0].url.params["ERLM_STRT_DT"] == "20260901"
    public = public_transactions(result)
    assert public["row_count"] == 2 and not public["cash_verified"]
    assert public["settlement_audit"]["arithmetic_verified"] is True
    assert "currency_totals" not in public["settlement_audit"]
    assert not public["execution_parity_verified"]
    assert all(value not in str(public) for value in ("SPY", "75.25", "20260908", "12345678"))


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["missing_fee", "nan", "negative", "no_continuation",
                                   "broker_failure", "missing_output", "bad_date", "bad_side"])
async def test_invalid_or_incomplete_report_has_no_partial_success(bad):
    value, headers = body(), {"tr_cont": "D"}
    if bad == "missing_fee":
        del value["output1"][0]["frcr_fee1"]
    elif bad in {"nan", "negative"}:
        value["output1"][0]["frcr_fee1"] = "NaN" if bad == "nan" else "-0.1"
    elif bad == "no_continuation":
        headers = {}
    elif bad == "broker_failure":
        value.update(rt_cd="1", msg1="private secret")
    elif bad == "missing_output":
        del value["output2"]
    elif bad == "bad_date":
        value["output1"][0]["trad_dt"] = "20260230"
    else:
        value["output1"][0]["sll_buy_dvsn_cd"] = "00"
    async with httpx.AsyncClient(base_url="https://offline.invalid", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, headers=headers, json=value)
    )) as client:
        with pytest.raises(AccountReadError, match="^TRANSACTIONS_[A-Z_]+$"):
            await observe_transactions(client, **ARGS)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["stalled", "limit", "second_error", "stale"])
async def test_later_page_failure_never_returns_earlier_rows(failure):
    calls = []
    clock = [NOW]

    def handle(request):
        calls.append(request)
        if len(calls) == 2 and failure == "second_error":
            raise RuntimeError("private account")
        if failure == "stale":
            clock[0] += timedelta(seconds=31)
        return httpx.Response(200, headers={"tr_cont": "M"}, json=body(ctx_area_fk100="same"))

    async with httpx.AsyncClient(base_url="https://offline.invalid",
                                transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(AccountReadError, match="^TRANSACTIONS_[A-Z_]+$"):
            await observe_transactions(client, **dict(ARGS, now=lambda: clock[0]),
                                       max_pages=1 if failure == "limit" else 20)


@pytest.mark.asyncio
async def test_request_cancellation_propagates():
    entered = asyncio.Event()

    async def handle(request):
        entered.set()
        await asyncio.Event().wait()

    async with httpx.AsyncClient(base_url="https://offline.invalid",
                                transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(observe_transactions(client, **ARGS))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_stuck_transport_is_bounded_even_when_source_clock_does_not_move(monkeypatch):
    from auto_invest.broker import intraday_transactions

    monkeypatch.setattr(intraday_transactions, "READ_TIMEOUT_SECONDS", .01)
    exited = asyncio.Event()

    async def handle(request):
        try:
            await asyncio.Event().wait()
        finally:
            exited.set()

    async with httpx.AsyncClient(base_url="https://offline.invalid",
                                transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(TimeoutError):
            await observe_transactions(client, **ARGS)
    assert exited.is_set()


@pytest.mark.asyncio
async def test_complete_http_report_with_bad_arithmetic_is_never_promoted_to_cash():
    value = body(output1=[dict(row(), frcr_excc_amt_1="75.41")])
    async with httpx.AsyncClient(base_url="https://offline.invalid", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"tr_cont": "D"}, json=value)
    )) as client:
        result = await observe_transactions(client, **ARGS)
    assert result["pagination_complete"] is True
    assert result["settlement_audit"]["status"] == "MISMATCH"
    assert result["settlement_audit"]["currency_totals"] is None
    assert result["source_rows"] == value["output1"]
    public = public_transactions(result)
    assert public["settlement_audit"]["mismatched_row_count"] == 1
    assert public["cash_verified"] is False
    assert public["execution_parity_verified"] is False
    assert "75.41" not in str(public)
