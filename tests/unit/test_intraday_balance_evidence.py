import copy
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.broker.intraday_balance_evidence import (
    CURRENT,
    SETTLED,
    observe_balance_evidence,
    public_balance_evidence,
)

NOW = datetime(2026, 9, 8, 15, 1, tzinfo=UTC)


def payload(amount="601.37"):
    return dict(
        rt_cd="0",
        output1=[dict(pdno="PRIVATE_ASSET")],
        output2=[dict(crcy_cd="USD", frcr_dncl_amt_2=amount)],
        output3=dict(tot_asst_amt="SECRET_TOTAL"),
    )


async def read(handler, **kwargs):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://kis.test"
    ) as client:
        return await observe_balance_evidence(
            client,
            access_token="secret-token",
            app_key="secret-key",
            app_secret="secret-secret",
            account="1234567801",
            **kwargs,
        )


@pytest.mark.asyncio
async def test_three_gets_preserve_bases_signed_amounts_and_never_report_nav():
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.params["WCRC_FRCR_DVSN_CD"] == "02"
        assert request.url.params["INQR_DVSN_CD"] == "00"
        if request.url.path.endswith(SETTLED):
            assert request.url.params["BASS_DT"] == "20260909"  # KST, not UTC date
            assert request.headers["tr_id"] == "CTRP6010R"
        else:
            assert request.url.params["NATN_CD"] == "000"
            assert request.url.params["TR_MKET_CD"] == "00"
            assert request.headers["tr_id"] == "CTRP6504R"
        return httpx.Response(200, json=payload("-601.37"), headers={"tr_cont": "D"})

    snapshot = await read(handle, now=lambda: NOW)
    assert [r.url.path.rsplit("/", 1)[-1] for r in requests] == [CURRENT, SETTLED, CURRENT]
    assert snapshot["current_after"]["currency_rows"][0]["reported_amount"] == "-601.37"
    assert snapshot["reported_usd_field_comparison"] == "EQUAL"
    public = public_balance_evidence(snapshot)
    for key in ("cash_verified", "nav_verified", "full_account_scope_verified", "live_eligible"):
        assert snapshot[key] is public[key] is False
    assert public["orders_submitted"] == 0
    text = json.dumps(public)
    for private in (
        "601.37",
        "PRIVATE_ASSET",
        "SECRET_TOTAL",
        "1234567801",
        "secret-",
        "currency_page_digests",
    ):
        assert private not in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,comparison",
    [
        ("different", "DIFFERENT"),
        ("changing", "UNAVAILABLE"),
        ("multi", "UNAVAILABLE"),
        ("missing", "UNAVAILABLE"),
    ],
)
async def test_numeric_comparison_requires_stable_unique_observations(case, comparison):
    current_reads = 0

    def handle(request):
        nonlocal current_reads
        body = payload()
        if request.url.path.endswith(CURRENT):
            current_reads += 1
            if case == "changing" and current_reads == 2:
                body["output2"][0]["frcr_dncl_amt_2"] = "602.00"
        else:
            if case == "different":
                body["output2"][0]["frcr_dncl_amt_2"] = "599"
            if case == "multi":
                body["output2"] *= 10  # Identical rows must not be deduplicated.
            if case == "missing":
                body["output2"] = []
        return httpx.Response(200, json=body, headers={"tr_cont": "D"})

    snapshot = await read(handle, now=lambda: NOW)
    assert snapshot["reported_usd_field_comparison"] == comparison
    if case == "multi":
        assert len(snapshot["settlement"]["currency_rows"]) == 10


@pytest.mark.asyncio
async def test_changed_other_current_fields_prevent_comparison():
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        body = payload()
        body["output2"][0]["frcr_buy_mgn_amt"] = "1" if calls == 3 else "0"
        return httpx.Response(200, json=body, headers={"tr_cont": "D"})

    snapshot = await read(handle, now=lambda: NOW)
    assert not snapshot["current_read_stable"]
    assert snapshot["reported_usd_field_comparison"] == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_blank_and_other_currencies_are_not_assigned_to_usd():
    body = payload()
    body["output2"] += [
        dict(crcy_cd=" ", frcr_dncl_amt_2="ignored"),
        dict(crcy_cd="JPY", frcr_dncl_amt_2="90000"),
    ]
    snapshot = await read(
        lambda r: httpx.Response(200, json=body, headers={"tr_cont": "D"}), now=lambda: NOW
    )
    assert snapshot["settlement"]["blank_currency_rows"] == 1
    assert len(snapshot["settlement"]["currency_rows"]) == 2
    assert public_balance_evidence(snapshot)["observations"]["settlement"]["usd_row_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value,code",
    [
        ("crcy_cd", None, "CURRENCY"),
        ("crcy_cd", "USD-secret", "CURRENCY"),
        ("frcr_dncl_amt_2", None, "REPORTED_AMOUNT"),
        ("frcr_dncl_amt_2", True, "REPORTED_AMOUNT"),
        ("frcr_dncl_amt_2", "NaN", "REPORTED_AMOUNT"),
        ("frcr_dncl_amt_2", "Infinity", "REPORTED_AMOUNT"),
        ("frcr_dncl_amt_2", "1e3", "REPORTED_AMOUNT"),
        ("frcr_dncl_amt_2", "", "REPORTED_AMOUNT"),
    ],
)
async def test_invalid_currency_amount_fails_without_raw_values(field, value, code):
    body = payload()
    body["output2"][0][field] = value
    with pytest.raises(AccountReadError, match="BALANCE_INVALID_" + code):
        await read(
            lambda r: httpx.Response(200, json=body, headers={"tr_cont": "D"}), now=lambda: NOW
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["output1", "output2", "output3"])
@pytest.mark.parametrize("bad", [None, "private-error", ["invalid-row"]])
async def test_missing_or_malformed_output_is_not_partial_success(key, bad):
    body = payload()
    body[key] = bad
    with pytest.raises(AccountReadError, match="BALANCE_INVALID_OUTPUT"):
        await read(
            lambda r: httpx.Response(200, json=body, headers={"tr_cont": "D"}), now=lambda: NOW
        )


@pytest.mark.asyncio
async def test_pagination_uses_header_only_and_preserves_repeated_currency_rows():
    def handle(request):
        body = payload()
        subsequent = request.headers["tr_cont"] == "N"
        body["output1"][0]["pdno"] = "SECOND" if subsequent else "FIRST"
        assert not any("CTX" in key for key in request.url.params)
        return httpx.Response(200, json=body, headers={"tr_cont": "E" if subsequent else "M"})

    snapshot = await read(handle, now=lambda: NOW)
    assert snapshot["settlement"]["output_row_counts"]["output1"] == 2
    assert len(snapshot["settlement"]["currency_rows"]) == 2
    assert snapshot["reported_usd_field_comparison"] == "UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("limit,reason", [(1, "PAGE_LIMIT"), (2, "REPEATED_PAGE")])
async def test_repeated_or_exhausted_pages_fail(limit, reason):
    with pytest.raises(AccountReadError, match="BALANCE_" + reason):
        await read(
            lambda r: httpx.Response(200, json=payload(), headers={"tr_cont": "F"}),
            now=lambda: NOW,
            max_pages=limit,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,reason",
    [
        (httpx.Response(500, text="private body"), "TRANSPORT_OR_JSON_ERROR"),
        (httpx.Response(200, text="private body"), "TRANSPORT_OR_JSON_ERROR"),
        (httpx.Response(200, json=dict(rt_cd="1", msg1="private-error")), "BROKER_REJECTED"),
        (httpx.Response(200, json=payload(), headers={"tr_cont": "Z"}), "CONTINUATION_HEADER"),
        (httpx.Response(200, json=payload()), "CONTINUATION_HEADER"),
        (httpx.Response(200, json=payload(), headers={"tr_cont": ""}), "CONTINUATION_HEADER"),
    ],
)
async def test_errors_never_return_partial_or_broker_error_text(response, reason):
    with pytest.raises(AccountReadError, match="BALANCE_" + reason) as error:
        await read(lambda r: copy.deepcopy(response), now=lambda: NOW)
    assert "private" not in str(error.value) + str(error.value.shape)


@pytest.mark.asyncio
@pytest.mark.parametrize("seconds", [-1, 31])
async def test_stale_or_backward_batch_is_rejected(seconds):
    current = NOW

    def handle(request):
        nonlocal current
        current = NOW + timedelta(seconds=seconds)
        return httpx.Response(200, json=payload())

    with pytest.raises(AccountReadError, match="BALANCE_STALE_BATCH"):
        await read(handle, now=lambda: current)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        dict(max_pages=0),
        dict(max_pages=True),
        dict(max_pages=21),
        dict(now=lambda: NOW.replace(tzinfo=None)),
    ],
)
async def test_invalid_configuration_never_calls_broker(kwargs):
    def forbidden(request):
        raise AssertionError("broker must not be called")

    with pytest.raises(AccountReadError, match="BALANCE_INVALID_"):
        await read(forbidden, **kwargs)
