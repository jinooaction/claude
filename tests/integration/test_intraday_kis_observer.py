from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.broker.account_source_profile import CASH_FIELDS
from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.intraday_inputs import REST_URL
from auto_invest.execution.intraday_observation import KISExecutionObserver, ObservationError


@pytest.mark.asyncio
async def test_cash_baseline_reaches_normal_account_reader_without_promoting_account(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        assert request.headers["authorization"] == "Bearer fresh"
        assert request.url.params["CANO"] == "12345678"
        assert request.url.params["ACNT_PRDT_CD"] == "01"
        endpoint = request.url.path.rsplit("/", 1)[1]
        if endpoint == "inquire-present-balance":
            data = dict(output2=[dict(crcy_cd="USD", frcr_dncl_amt_2="601.37",
                frcr_buy_mgn_amt="0", frcr_etc_mgna="0")], output3=dict.fromkeys((
                    "dncl_amt", "cma_evlu_amt", "tot_loan_amt", "ustl_buy_amt_smtl",
                    "ustl_sll_amt_smtl"), "0"))
        elif endpoint == "foreign-margin":
            row = dict(dict.fromkeys(CASH_FIELDS, "0"), crcy_cd="USD",
                       frcr_dncl_amt1="601.37", frcr_gnrl_ord_psbl_amt="601.37")
            data = dict(output=[dict(row) for _ in range(10)])
        else:
            return account_response(request)
        return httpx.Response(200, headers={"tr_cont": "D"}, json=dict(rt_cd="0", **data))

    async with httpx.AsyncClient(base_url=REST_URL, transport=httpx.MockTransport(handle)) as http:
        observer = KISExecutionObserver(authority(http), lambda: {},
            token_cache=tmp_path / "token.json", now=lambda: datetime(2026, 9, 12, tzinfo=UTC))
        result = await observer._read()
    assert result["reported_cash_baseline"]["cash"] == "601.37"
    assert result["reported_cash_baseline"]["status"] == "CALCULATED"
    assert result["full_account_scope_verified"] is False
    assert result["cash_aggregation_verified"] is False
    assert result["nav"] is None and result["nav_verified"] is False
    assert [request.method for request in calls] == ["POST"] + ["GET"] * 7


def authority(http):
    return SimpleNamespace(
        account_no="1234567801", app_key="offline-key", app_secret="offline-secret",
        access_token="expired", broker=ResilientClient(
            http, rate_limiter=AsyncTokenBucket(100, 100),
            breaker=CircuitBreaker(3, 30), max_retries=1,
        ),
    )


def account_response(request):
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
    assert [r.method for r in calls] == ["POST"] + ["GET"] * 14
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
