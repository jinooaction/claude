import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.broker.account_asset_evidence import SUMMARY_FIELDS, TABLE_FIELDS
from auto_invest.broker.account_source_profile import CASH_FIELDS
from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.domestic_account import SUMMARY_FIELDS as DOMESTIC_SUMMARY_FIELDS
from auto_invest.broker.intraday_inputs import REST_URL
from auto_invest.execution.intraday_observation import KISExecutionObserver, ObservationError


@pytest.mark.asyncio
@pytest.mark.parametrize("unsettled", [False, True])
@pytest.mark.parametrize("reported_value,reported_quantity", [
    ("120", "3"), ("0", "3"), (None, "3"), ("120", "0.5"),
])
async def test_cash_baseline_reaches_normal_account_reader_without_promoting_account(
    tmp_path, reported_value, reported_quantity, unsettled,
):
    calls = []
    clock = datetime(2026, 9, 12, tzinfo=UTC)

    def handle(request):
        nonlocal clock
        calls.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        clock += timedelta(seconds=1)
        assert request.headers["authorization"] == "Bearer fresh"
        assert request.url.params["CANO"] == "12345678"
        assert request.url.params["ACNT_PRDT_CD"] == "01"
        endpoint = request.url.path.rsplit("/", 1)[1]
        if request.url.path == "/uapi/domestic-stock/v1/trading/inquire-balance":
            data = dict(output1=[], output2=[dict.fromkeys(DOMESTIC_SUMMARY_FIELDS, "0")],
                        ctx_area_fk100="", ctx_area_nk100="")
            data["output2"][0].update(dict.fromkeys(("dnca_tot_amt", "nxdy_excc_amt",
                "prvs_rcdl_excc_amt", "nass_amt", "tot_evlu_amt"), "73145"))
        elif endpoint == "inquire-balance":
            row = dict(ovrs_pdno="ORANY", ovrs_excg_cd="OTCB", tr_crcy_cd="USD",
                       ovrs_cblc_qty=reported_quantity, ord_psbl_qty="0", now_pric2="40")
            if reported_value is not None:
                row["ovrs_stck_evlu_amt"] = reported_value
            data = dict(output1=[row], ctx_area_fk200="", ctx_area_nk200="")
        elif endpoint == "inquire-present-balance":
            data = dict(output2=[dict(crcy_cd="USD", frcr_dncl_amt_2="601.37",
                frcr_buy_mgn_amt="0", frcr_etc_mgna="0", frst_bltn_exrt="1000")],
                output3=dict.fromkeys((
                    "dncl_amt", "cma_evlu_amt", "tot_loan_amt", "ustl_buy_amt_smtl",
                    "ustl_sll_amt_smtl"), "0"))
            data["output3"]["tot_dncl_amt"] = "73145"
            holding = dict(pdno="ORANY", buy_crcy_cd="USD", ovrs_excg_cd="OTCB",
                           ccld_qty_smtl1=reported_quantity, ord_psbl_qty1="0", loan_rmnd="0")
            if reported_value is not None:
                holding["frcr_evlu_amt2"] = reported_value
            data["output1"] = [holding]
            if unsettled:
                data["output2"][0].update(frcr_dncl_amt_2="401.37", frcr_buy_mgn_amt="200")
                data["output3"].update(ustl_buy_amt_smtl="100000", ustl_sll_amt_smtl="25000")
        elif endpoint == "foreign-margin":
            row = dict(dict.fromkeys(CASH_FIELDS, "0"), crcy_cd="USD",
                       frcr_dncl_amt1="601.37", frcr_gnrl_ord_psbl_amt="601.37")
            if unsettled:
                row.update(ustl_buy_amt="100", ustl_sll_amt="25", frcr_mgn_amt="200")
            data = dict(output=[dict(row) for _ in range(10)])
        elif endpoint == "inquire-account-balance":
            data = dict(output1=[dict.fromkeys(TABLE_FIELDS + ("whol_weit_rt",), "0")
                                 for _ in range(20)], output2=dict.fromkeys(SUMMARY_FIELDS, "0"))
            for index, amount in ((8, "120"), (16, "601370"), (17, "73145")):
                data["output1"][index].update(
                    pchs_amt=amount, evlu_amt=amount, real_nass_amt=amount)
            for field in TABLE_FIELDS:
                data["output1"][-1][field] = str(sum(
                    int(row[field]) for row in data["output1"][:-1]))
            data["output2"].update(dncl_amt="73145", tot_dncl_amt="73145")
        else:
            return account_response(request)
        return httpx.Response(200, headers={"tr_cont": "D"}, json=dict(rt_cd="0", **data))

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        observer = KISExecutionObserver(authority(http), lambda: {},
            token_cache=tmp_path / "token.json", now=lambda: clock)
        result = await observer._read()
    baseline = result["reported_cash_baseline"]
    assert baseline["status"] == ("UNAVAILABLE" if unsettled else "CALCULATED")
    assert baseline["cash"] == (None if unsettled else "601.37")
    assert baseline["settlement_cash"]["cash"] == ("526.37" if unsettled else "601.37")
    assert result["reported_cash_valuation"]["amount_usd"] == (
        "599.515000000000" if unsettled else "674.515000000000")
    assert result["reported_cash_valuation"]["balances"] == {
        "KRW": "73145", "USD": "526.37" if unsettled else "601.37"}
    if unsettled:
        assert result["reported_cash_valuation"]["fees_inclusion_verified"] is False
        assert result["reported_cash_valuation"]["scope"] == (
            "RECONCILED_KRW_USD_REPORTED_SETTLEMENT_CASH")
    assert result["full_account_scope_verified"] is False
    assert result["cash_aggregation_verified"] is False
    assert result["reported_holdings_coverage"]["status"] == "MATCH"
    assert result["reported_holdings_coverage"]["positive_holding_count"] == 1
    assert not result["reported_holdings_coverage"]["full_account_verified"]
    assert result["reported_asset_scope"]["status"] == "MATCH"
    assert result["reported_asset_scope"]["category_count"] == 19
    assert not result["reported_asset_scope"]["full_account_scope_verified"]
    assert result["nav"] is None and result["nav_verified"] is False
    assert result["unverified_assets"]["ORANY"]["tradability_verified"] is False
    if reported_value is None or reported_quantity == "0.5":
        assert result["reported_asset_values"] == {}
    else:
        assert result["reported_asset_values"]["ORANY"] == dict(quantity=3,
            amount_usd=reported_value,
            observation_started_at=(clock - timedelta(seconds=8)).isoformat(),
            observation_completed_at=(clock - timedelta(seconds=4)).isoformat())
    domestic = result["reported_domestic_account"]
    assert domestic["positions"] == {} and domestic["pagination_complete"]
    assert domestic["currency"] == "KRW" and not domestic["full_account_verified"]
    assert [request.method for request in calls] == ["POST"] + ["GET"] * 9
    assert [r.url.path.rsplit("/", 1)[1] for r in calls[1:]] == [
        "inquire-present-balance", "inquire-balance", "inquire-nccs", "inquire-psamount",
        "foreign-margin", "inquire-balance", "inquire-account-balance",
        "inquire-account-balance", "inquire-present-balance",
    ]
    assert result["account_frame"]["request_count"] == 9
    assert result["observation_started_at"] == (clock - timedelta(seconds=9)).isoformat()
    assert result["observation_completed_at"] == clock.isoformat()
    assert result["reported_cash_valuation"]["observation_completed_at"] == clock.isoformat()
    assert len(result["account_frame"]["asset_reports"]) == 2
    assert result["reported_account_assets"]["reporting_basis"] == "SETTLEMENT_ACCOUNT_ASSET_TABLE"


def authority(http):
    return SimpleNamespace(
        account_no="1234567801", app_key="offline-key", app_secret="offline-secret",
        access_token="expired", broker=ResilientClient(
            http, rate_limiter=AsyncTokenBucket(100, 100),
            breaker=CircuitBreaker(3, 30), max_retries=1,
        ),
    )


def account_response(request):
    if request.url.path.endswith("/inquire-account-balance"):
        return httpx.Response(200, headers={"tr_cont": "D"}, json=dict(rt_cd="0",
            output1=[dict.fromkeys(TABLE_FIELDS + ("whol_weit_rt",), "0") for _ in range(20)],
            output2=dict.fromkeys(SUMMARY_FIELDS, "0")))
    if request.url.path == "/uapi/domestic-stock/v1/trading/inquire-balance":
        return httpx.Response(200, headers={"tr_cont": "D"}, json=dict(rt_cd="0", output1=[],
            output2=[dict.fromkeys(DOMESTIC_SUMMARY_FIELDS, "0")],
            ctx_area_fk100="", ctx_area_nk100=""))
    endpoint = request.url.path.rsplit("/", 1)[1]
    rows = {
        "inquire-balance": dict(output1=[], ctx_area_fk200="", ctx_area_nk200=""),
        "inquire-nccs": dict(output=[], ctx_area_fk200="", ctx_area_nk200=""),
        "inquire-psamount": dict(output={"ovrs_ord_psbl_amt": "99999"}),
        "foreign-margin": dict(output=[]),
        "inquire-present-balance": dict(output2=[], output3={}),
    }
    return httpx.Response(200, json=dict(rt_cd="0", **rows[endpoint]))


@pytest.mark.asyncio
async def test_real_authentication_and_reader_share_token_but_do_not_approve_nav(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        assert request.headers["authorization"] == "Bearer fresh"
        assert request.url.params["CANO"] == "12345678"
        assert request.url.params["ACNT_PRDT_CD"] == "01"
        return account_response(request)

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        owner = authority(http)
        observer = KISExecutionObserver(owner, lambda: {}, token_cache=tmp_path / "token.json")
        for _ in range(2):
            with pytest.raises(ObservationError, match="^ACCOUNT_SCOPE_UNVERIFIED$"):
                await observer()
            assert owner.access_token == "fresh"
    assert [r.method for r in calls] == ["POST"] + ["GET"] * 18
    assert all(r.method == "GET" or r.url.path == "/oauth2/tokenP" for r in calls)
    assert (tmp_path / "token.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["account", "credentials", "broker", "redirect"])
async def test_connection_mutation_refused_before_credentials_leave_process(tmp_path, change):
    calls = []

    def handle(request):
        calls.append(request)
        raise AssertionError("Unexpected request")

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        owner = authority(http)
        observer = KISExecutionObserver(owner, lambda: {}, token_cache=tmp_path / "token.json")
        if change == "account":
            owner.account_no = "8765432101"
        elif change == "credentials":
            owner.app_secret = "changed"
        elif change == "broker":
            owner.broker = authority(http).broker
        else:
            http.follow_redirects = True
        with pytest.raises(ObservationError, match="^ACCOUNT_CONNECTION_INVALID$"):
            await observer()
    assert calls == []


@pytest.mark.asyncio
async def test_account_changed_during_token_request_is_refused_before_reads(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        owner.account_no = "8765432101"
        return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        owner = authority(http)
        observer = KISExecutionObserver(owner, lambda: {}, token_cache=tmp_path / "token.json")
        with pytest.raises(ObservationError, match="^ACCOUNT_CONNECTION_INVALID$"):
            await observer()
        assert owner.access_token == "expired"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_authentication_error_is_closed_and_does_not_attempt_account_reads(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(403, text="private account and credential details")

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        owner = authority(http)
        with pytest.raises(ObservationError, match="^ACCOUNT_AUTHENTICATION_UNAVAILABLE$"):
            await KISExecutionObserver(owner, lambda: {}, token_cache=tmp_path / "token.json")()
        assert owner.access_token == "expired"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_unofficial_origin_is_rejected_on_construction(tmp_path):
    async with httpx.AsyncClient(base_url="https://kis.invalid") as http:
        with pytest.raises(ObservationError, match="^ACCOUNT_CONNECTION_INVALID$"):
            KISExecutionObserver(authority(http), lambda: {}, token_cache=tmp_path / "token.json")


@pytest.mark.asyncio
async def test_domestic_failure_never_returns_a_partial_account_as_complete(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        if request.url.path == "/uapi/domestic-stock/v1/trading/inquire-balance":
            return httpx.Response(403, json=dict(msg1="PRIVATE_DOMESTIC_ERROR"))
        return account_response(request)

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        observer = KISExecutionObserver(authority(http), lambda: {},
                                       token_cache=tmp_path / "token.json")
        with pytest.raises(ObservationError, match="^ACCOUNT_INPUT_UNAVAILABLE$"):
            await observer()
    assert calls[-1].url.path == "/uapi/domestic-stock/v1/trading/inquire-balance"
    assert all(request.method == "GET" or request.url.path == "/oauth2/tokenP" for request in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_request", range(1, 10))
async def test_each_frame_request_failure_prevents_partial_account_return(tmp_path, failed_request):
    reads = 0

    def handle(request):
        nonlocal reads
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        reads += 1
        if reads == failed_request:
            return httpx.Response(403, json=dict(msg1="PRIVATE_FRAME_ERROR"))
        return account_response(request)

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        observer = KISExecutionObserver(authority(http), lambda: {}, token_cache=tmp_path / "token")
        with pytest.raises(ObservationError, match="^ACCOUNT_INPUT_UNAVAILABLE$"):
            await observer()
    assert reads == failed_request


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["reverse", "stale", "account", "credentials", "redirect"])
async def test_frame_stops_at_first_changed_connection_or_invalid_clock(tmp_path, fault):
    reads = 0
    clock = datetime(2026, 9, 12, tzinfo=UTC)

    def handle(request):
        nonlocal reads, clock
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        reads += 1
        if reads == 4:
            if fault in {"reverse", "stale"}:
                clock += timedelta(seconds=-1 if fault == "reverse" else 31)
            elif fault == "account":
                owner.account_no = "8765432101"
            elif fault == "credentials":
                owner.app_secret = "changed"
            else:
                http.follow_redirects = True
        return account_response(request)

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        owner = authority(http)
        observer = KISExecutionObserver(owner, lambda: {}, token_cache=tmp_path / "token",
                                       now=lambda: clock)
        with pytest.raises(ObservationError, match="^ACCOUNT_INPUT_UNAVAILABLE$"):
            await observer()
    assert reads == 4


@pytest.mark.asyncio
async def test_cancelling_frame_cancels_pending_transport_and_prevents_further_reads(tmp_path):
    entered, cancelled = asyncio.Event(), asyncio.Event()
    reads = 0

    async def handle(request):
        nonlocal reads
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        reads += 1
        if reads == 4:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        return account_response(request)

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        observer = KISExecutionObserver(authority(http), lambda: {}, token_cache=tmp_path / "token")
        task = asyncio.create_task(observer._read())
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set() and reads == 4


@pytest.mark.asyncio
async def test_wall_clock_timeout_cancels_transport_even_with_frozen_source_clock(
    tmp_path, monkeypatch,
):
    import auto_invest.broker.intraday_account_frame as module

    monkeypatch.setattr(module, "READ_TIMEOUT_SECONDS", 0.02)
    cancelled = asyncio.Event()
    reads = 0

    async def handle(request):
        nonlocal reads
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        reads += 1
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        observer = KISExecutionObserver(authority(http), lambda: {}, token_cache=tmp_path / "token",
                                       now=lambda: datetime(2026, 9, 12, tzinfo=UTC))
        with pytest.raises(ObservationError, match="^ACCOUNT_INPUT_UNAVAILABLE$"):
            await observer()
    assert cancelled.is_set() and reads == 1


@pytest.mark.asyncio
async def test_current_holdings_changed_during_frame_are_preserved_but_never_matched(tmp_path):
    currents = 0

    def handle(request):
        nonlocal currents
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        if request.url.path.endswith("/inquire-present-balance"):
            currents += 1
            rows = [] if currents == 1 else [dict(pdno="AAPL", buy_crcy_cd="USD",
                ovrs_excg_cd="NAS", ccld_qty_smtl1="1", ord_psbl_qty1="1", loan_rmnd="0")]
            return httpx.Response(200, headers={"tr_cont": "D"},
                                  json=dict(rt_cd="0", output1=rows, output2=[], output3={}))
        return account_response(request)

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        observer = KISExecutionObserver(authority(http), lambda: {}, token_cache=tmp_path / "token")
        result = await observer._read()
    assert result["reported_cash_baseline"]["current_holdings"]["reason"] == "HOLDINGS_CHANGED"
    assert result["reported_holdings_coverage"]["status"] == "UNAVAILABLE"
    assert not result["full_account_scope_verified"] and not result["nav_verified"]
