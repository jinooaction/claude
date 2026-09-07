from datetime import UTC, datetime, timedelta

import httpx
import pytest

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.intraday_account import (
    AccountReadError,
    observe_account,
    public_contract_result,
)

NOW = datetime(2026, 9, 7, tzinfo=UTC)


def replies():
    return {
        "inquire-balance": dict(
            rt_cd="0",
            ctx_area_fk200="",
            ctx_area_nk200="",
            output1=[
                dict(
                    ovrs_pdno="TLT",
                    ovrs_cblc_qty="1.00000000",
                    ord_psbl_qty="1",
                    tr_crcy_cd="USD",
                    ovrs_excg_cd="NASD",
                    now_pric2="82.21",
                    ovrs_stck_evlu_amt="82.21",
                )
            ],
        ),
        "inquire-nccs": dict(rt_cd="0", output=[], ctx_area_fk200="", ctx_area_nk200=""),
        "inquire-psamount": dict(
            rt_cd="0", output=dict(ovrs_ord_psbl_amt="600", frcr_ord_psbl_amt1="999999")
        ),
        "foreign-margin": dict(
            rt_cd="0",
            output=[
                dict(
                    crcy_cd="USD",
                    frcr_dncl_amt1="700",
                    ustl_buy_amt="100",
                    ustl_sll_amt="10",
                    frcr_rcvb_amt="0",
                    frcr_mgn_amt="50",
                    frcr_gnrl_ord_psbl_amt="600",
                )
            ],
        ),
    }


async def read(handler, **kwargs):
    async with httpx.AsyncClient(
        base_url="https://kis.invalid", transport=httpx.MockTransport(handler)
    ) as http:
        client = ResilientClient(
            http,
            rate_limiter=AsyncTokenBucket(1000, 1000),
            breaker=CircuitBreaker(3, 30),
            max_retries=0,
        )
        return await observe_account(
            client,
            account="1234567801",
            access_token="secret-token",
            app_key="secret-key",
            app_secret="secret-secret",
            **kwargs,
        )


@pytest.mark.asyncio
async def test_get_only_no_nav_or_cash_field_fallback():
    data = replies()
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.headers["custtype"] == "P"
        return httpx.Response(200, json=data[request.url.path.split("/")[-1]])

    snapshot = await read(handle, now=lambda: NOW)
    assert len(requests) == 4
    assert snapshot["usd_orderable_amount"] == "600"
    assert snapshot["reported_cash_components"]["frcr_dncl_amt1"] == "700"
    assert snapshot["nav"] is None and snapshot["nav_verified"] is False
    assert snapshot["live_eligible"] is False
    assert snapshot["full_account_scope_verified"] is False
    assert snapshot["positions"]["TLT"]["quantity"] == 1
    public = str(public_contract_result(snapshot))
    for forbidden in ("1234567801", "TLT", "600", "secret"):
        assert forbidden not in public


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["inquire-balance", "inquire-nccs"])
async def test_continuation_preserves_cursor_and_header(endpoint):
    data = replies()
    calls = []

    def handle(request):
        path = request.url.path.split("/")[-1]
        if path != endpoint:
            return httpx.Response(200, json=data[path])
        calls.append(request)
        body = dict(data[path])
        if len(calls) == 1:
            body["ctx_area_fk200"], body["ctx_area_nk200"] = " FK ", " NK "
            body["output1" if path == "inquire-balance" else "output"] = []
            return httpx.Response(200, json=body, headers={"tr_cont": "M"})
        assert request.headers["tr_cont"] == "N"
        assert request.url.params["CTX_AREA_FK200"] == " FK "
        assert request.url.params["CTX_AREA_NK200"] == " NK "
        return httpx.Response(200, json=body, headers={"tr_cont": "D"})

    snapshot = await read(handle, now=lambda: NOW)
    assert snapshot["pagination_complete"] is True
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["inquire-balance", "inquire-nccs"])
@pytest.mark.parametrize("header", ["D", "E"])
async def test_terminal_header_may_retain_search_context(endpoint, header):
    data = replies()
    data[endpoint].update(ctx_area_fk200="retained-search", ctx_area_nk200="retained-key")
    snapshot = await read(
        lambda request: httpx.Response(
            200, json=data[request.url.path.split("/")[-1]], headers={"tr_cont": header}
        ),
        now=lambda: NOW,
    )
    assert snapshot["pagination_complete"]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [1, 3])
async def test_incomplete_or_repeated_cursor_never_returns_partial_account(limit):
    data = replies()
    data["inquire-balance"].update(ctx_area_fk200="same", ctx_area_nk200="same")
    with pytest.raises(AccountReadError, match="ACCOUNT_(PAGE_LIMIT|CURSOR_STALLED)"):
        await read(
            lambda request: httpx.Response(
                200, json=data[request.url.path.split("/")[-1]], headers={"tr_cont": "M"}
            ),
            now=lambda: NOW,
            max_pages=limit,
        )


@pytest.mark.asyncio
async def test_nccs_unclassified_header_does_not_ignore_nonempty_cursor():
    data = replies()
    data["inquire-nccs"].update(ctx_area_fk200="same", ctx_area_nk200="same")
    with pytest.raises(AccountReadError, match="ACCOUNT_CURSOR_STALLED") as error:
        await read(
            lambda request: httpx.Response(
                200, json=data[request.url.path.split("/")[-1]], headers={"tr_cont": ""}
            ),
            now=lambda: NOW,
        )
    assert error.value.shape["endpoint"] == "inquire-nccs"
    assert error.value.shape["cursor_repeated"] is True
    assert "same" not in str(error.value.shape)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "", {}, "secret broker error"])
async def test_missing_or_ambiguous_empty_orders_rejected(value):
    data = replies()
    data["inquire-nccs"]["output"] = value
    with pytest.raises(AccountReadError, match="INVALID_INQUIRE_NCCS_ROWS"):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ovrs_cblc_qty", "1.5"),
        ("ovrs_cblc_qty", "-1"),
        ("now_pric2", "NaN"),
        ("ord_psbl_qty", "2"),
        ("tr_crcy_cd", "KRW"),
    ],
)
async def test_invalid_holding_is_not_silently_truncated_or_converted(field, value):
    data = replies()
    data["inquire-balance"]["output1"][0][field] = value
    with pytest.raises(AccountReadError):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("market", ["NAS", " NAS ", "NASD", "NYSE", "AMEX"])
async def test_documented_us_account_exchange_codes(market):
    data = replies()
    data["inquire-balance"]["output1"][0].update(ovrs_excg_cd=market, tr_crcy_cd=" USD ")
    snapshot = await read(
        lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
        now=lambda: NOW,
    )
    assert snapshot["positions"]["TLT"]["quantity"] == 1
    assert snapshot["nav_verified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("market", ["SEHK", "", None, [], "secret-free-text"])
async def test_unknown_or_invalid_exchange_still_blocks(market):
    data = replies()
    data["inquire-balance"]["output1"][0]["ovrs_excg_cd"] = market
    with pytest.raises(AccountReadError, match="NON_US_MARKET") as error:
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )
    assert "secret-free-text" not in str(error.value.shape)
    assert error.value.shape["endpoint"] == "inquire-balance"
    if market == "SEHK":
        assert error.value.shape["market_code"] == "SEHK"
    else:
        assert error.value.shape["market_code"] == "REDACTED"


@pytest.mark.asyncio
@pytest.mark.parametrize("market", ["12345678", "SECRET123456789"])
async def test_market_diagnostic_never_publishes_account_or_long_token(market):
    data = replies()
    data["inquire-psamount"]["output"]["ovrs_excg_cd"] = market
    with pytest.raises(AccountReadError) as error:
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )
    assert error.value.shape == dict(
        endpoint="inquire-psamount", market_category="OTHER", market_code="REDACTED"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", ["1", "0.5", "0"])
async def test_observed_otcb_assets_remain_unverified_and_separate(quantity):
    data = replies()
    data["inquire-balance"]["output1"].append(
        dict(ovrs_pdno="OTC.TEST", ovrs_cblc_qty=quantity, ovrs_excg_cd="OTCB", tr_crcy_cd="USD")
    )
    snapshot = await read(
        lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
        now=lambda: NOW,
    )
    assert set(snapshot["positions"]) == {"TLT"}
    asset = snapshot["unverified_assets"]["OTC.TEST"]
    assert asset["reported_quantity"] == quantity
    assert asset["reported_market_code"] == "OTCB"
    assert asset["reported_valuation_usd"] is None
    assert not asset["valuation_verified"] and not asset["tradability_verified"]
    assert not asset["exchange_verified"]
    assert snapshot["nav"] is None and not snapshot["full_account_scope_verified"]
    assert "UNSUPPORTED_ACCOUNT_ASSETS_PRESENT" in snapshot["issues"]
    public = public_contract_result(snapshot)
    assert public["status"] == "INTRADAY_ACCOUNT_READ_WITH_UNVERIFIED_ASSETS"
    assert public["unverified_asset_count"] == 1
    assert public["position_count"] == 1
    assert public["live_eligible"] is False
    assert "OTC.TEST" not in str(public)


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", ["-1", "NaN", None, "999999999999999999999"])
async def test_unverified_asset_invalid_quantity_still_blocks(quantity):
    data = replies()
    data["inquire-balance"]["output1"][0].update(ovrs_excg_cd="OTCB", ovrs_cblc_qty=quantity)
    with pytest.raises(AccountReadError, match="INVALID_OVRS_CBLC_QTY"):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["normal_first", "otcb_first", "both_otcb"])
async def test_duplicate_assets_across_scopes_never_hide_holdings(order):
    data = replies()
    original = data["inquire-balance"]["output1"][0]
    opaque = dict(original, ovrs_excg_cd="OTCB")
    rows = [original, opaque] if order == "normal_first" else [opaque, original]
    if order == "both_otcb":
        rows = [opaque, dict(opaque)]
    data["inquire-balance"]["output1"] = rows
    with pytest.raises(AccountReadError, match="DUPLICATE_ACCOUNT_POSITION"):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
async def test_unverified_asset_non_usd_still_blocks():
    data = replies()
    data["inquire-balance"]["output1"][0].update(ovrs_excg_cd="OTCB", tr_crcy_cd="HKD")
    with pytest.raises(AccountReadError, match="NON_USD_ROW"):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
async def test_otcb_open_orders_are_not_promoted_to_supported_market():
    data = replies()
    data["inquire-nccs"]["output"] = [dict(ovrs_excg_cd="OTCB", tr_crcy_cd="USD")]
    with pytest.raises(AccountReadError, match="NON_US_MARKET"):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[], [{"crcy_cd": "HKD"}]])
async def test_unreported_usd_margin_is_unknown_not_zero_or_orderable_cash(rows):
    data = replies()
    data["foreign-margin"]["output"] = rows
    snapshot = await read(
        lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
        now=lambda: NOW,
    )
    assert snapshot["reported_cash_components"] is None
    assert snapshot["usd_margin_reported"] is False
    assert snapshot["usd_orderable_amount"] == "600"
    assert "USD_MARGIN_COMPONENTS_NOT_REPORTED" in snapshot["issues"]
    assert snapshot["nav"] is None and not snapshot["full_account_scope_verified"]
    public = public_contract_result(snapshot)
    assert public["status"] == "INTRADAY_ACCOUNT_READ_WITH_UNVERIFIED_CASH"
    assert not public["usd_margin_reported"] and not public["live_eligible"]


@pytest.mark.asyncio
async def test_margin_currency_padding_preserves_reported_amounts():
    data = replies()
    data["foreign-margin"]["output"][0]["crcy_cd"] = " USD "
    snapshot = await read(
        lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
        now=lambda: NOW,
    )
    assert snapshot["usd_margin_reported"]
    assert snapshot["reported_cash_components"]["frcr_dncl_amt1"] == "700"


@pytest.mark.asyncio
async def test_duplicate_usd_margin_is_not_summed_or_hidden():
    data = replies()
    data["foreign-margin"]["output"].append(
        dict(data["foreign-margin"]["output"][0], crcy_cd=" USD ")
    )
    with pytest.raises(AccountReadError, match="USD_MARGIN_ROW_COUNT") as error:
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )
    assert error.value.shape == {"usd_margin_rows": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", [None, "", "US", "secret-data", 840])
async def test_malformed_margin_currency_still_blocks(currency):
    data = replies()
    data["foreign-margin"]["output"][0]["crcy_cd"] = currency
    with pytest.raises(AccountReadError, match="INVALID_MARGIN_CURRENCY"):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
async def test_reported_usd_margin_with_missing_amount_is_not_treated_as_unreported():
    data = replies()
    del data["foreign-margin"]["output"][0]["frcr_dncl_amt1"]
    with pytest.raises(AccountReadError, match="INVALID_FRCR_DNCL_AMT1"):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
async def test_missing_foreign_currency_amount_never_uses_integrated_buying_power():
    data = replies()
    del data["inquire-psamount"]["output"]["ovrs_ord_psbl_amt"]
    with pytest.raises(AccountReadError, match="INVALID_OVRS_ORD_PSBL_AMT"):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
async def test_broker_free_text_is_never_in_error():
    with pytest.raises(AccountReadError) as error:
        await read(
            lambda _: httpx.Response(200, json={"rt_cd": "1", "msg1": "secret-key"}),
            now=lambda: NOW,
        )
    assert str(error.value) == "ACCOUNT_BROKER_REJECTED"


@pytest.mark.asyncio
async def test_whole_poll_age_not_last_call_age():
    clock = [NOW]
    data = replies()

    def handler(request):
        clock[0] += timedelta(seconds=10)
        return httpx.Response(200, json=data[request.url.path.split("/")[-1]])

    with pytest.raises(AccountReadError, match="STALE_ACCOUNT_OBSERVATION"):
        await read(handler, now=lambda: clock[0])


@pytest.mark.asyncio
async def test_empty_holdings_and_open_partial_order_are_separate():
    data = replies()
    data["inquire-balance"]["output1"] = []
    data["inquire-nccs"]["output"] = dict(
        odno="order-123",
        pdno="SPY",
        nccs_qty="3",
        ft_ord_qty="5",
        ft_ccld_qty="2",
        sll_buy_dvsn_cd="02",
        tr_crcy_cd="USD",
        ovrs_excg_cd="AMEX",
    )
    snapshot = await read(
        lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
        now=lambda: NOW,
    )
    assert snapshot["positions"] == {}
    assert snapshot["open_orders"][0]["remaining_quantity"] == 3
    assert snapshot["open_orders"][0]["filled_quantity"] == 2
    assert "order-123" not in str(public_contract_result(snapshot))


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["duplicate", "excess", "fraction", "side"])
async def test_invalid_open_orders_block_snapshot(defect):
    data = replies()
    order = dict(
        odno="123",
        pdno="TLT",
        nccs_qty="3",
        ft_ord_qty="5",
        ft_ccld_qty="2",
        sll_buy_dvsn_cd="02",
    )
    data["inquire-nccs"]["output"] = [order]
    if defect == "duplicate":
        data["inquire-nccs"]["output"].append(dict(order))
    elif defect == "excess":
        order["nccs_qty"] = "4"
    elif defect == "fraction":
        order["nccs_qty"] = "1.5"
    else:
        order["sll_buy_dvsn_cd"] = "unknown"
    with pytest.raises(AccountReadError):
        await read(
            lambda request: httpx.Response(200, json=data[request.url.path.split("/")[-1]]),
            now=lambda: NOW,
        )


@pytest.mark.asyncio
async def test_transport_failure_does_not_expose_headers():
    with pytest.raises(AccountReadError) as error:
        await read(lambda _: httpx.Response(503, text="secret-token"), now=lambda: NOW)
    assert str(error.value) == "ACCOUNT_TRANSPORT_OR_JSON_ERROR"
