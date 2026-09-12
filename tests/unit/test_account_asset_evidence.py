import copy
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.broker.account_asset_evidence import (
    ASSETS_URL,
    SUMMARY_FIELDS,
    TABLE_FIELDS,
    observe_account_assets,
)
from auto_invest.broker.intraday_account import AccountReadError

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def payload(product="01"):
    row = dict.fromkeys(TABLE_FIELDS + ("whol_weit_rt",), "0")
    rows = [dict(row) for _ in range(17 if product == "21" else 20)]
    rows[0].update(pchs_amt="120", evlu_amt="130", evlu_pfls_amt="10",
                   crdt_lnd_amt="20", real_nass_amt="110", whol_weit_rt="100")
    rows[-1] = dict(rows[0])
    summary = dict.fromkeys(SUMMARY_FIELDS, "0")
    summary["nass_tot_amt"] = "110"
    return dict(rt_cd="0", output1=rows, output2=summary)


async def read(handler, **kwargs):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://kis.test",
    ) as client:
        return await observe_account_assets(
            client, access_token="SECRET_TOKEN", app_key="SECRET_KEY",
            app_secret="SECRET_SECRET", account=kwargs.pop("account", "1234567801"),
            now=kwargs.pop("now", lambda: NOW), **kwargs,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("product,count", [("01", 19), ("21", 16)])
async def test_reads_complete_official_tables_and_sums_with_no_execution_authority(product, count):
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "GET" and request.url.path == ASSETS_URL
        assert dict(request.url.params) == dict(
            CANO="12345678", ACNT_PRDT_CD=product, INQR_DVSN_1="", BSPR_BF_DT_APLY_YN="",
        )
        assert request.headers["tr_id"] == "CTRP6548R"
        assert request.headers["tr_cont"] == ""
        body = payload(product)
        body["output1"][0]["account"] = "PRIVATE_ACCOUNT"
        return httpx.Response(200, json=body, headers={"tr_cont": ""})

    result = await read(handle, account="12345678" + product)
    assert len(requests) == 2
    assert result["status"] == "MATCH"
    assert result["category_count"] == count
    assert result["nonzero_category_count"] == 1
    assert len(result["checks"]) == 6
    assert result["execution_nav_verified"] is False
    assert result["orders_submitted"] == 0
    public = json.dumps(result)
    for value in ("120", "130", "110", "SECRET", "12345678", "PRIVATE_ACCOUNT"):
        assert value not in public


@pytest.mark.asyncio
@pytest.mark.parametrize("field", TABLE_FIELDS)
async def test_every_category_is_included_in_its_column_total(field):
    body = payload()
    body["output1"][-2][field] = "1"  # Last category before the total must be included.
    result = await read(lambda r: httpx.Response(200, json=body, headers={"tr_cont": "D"}))
    assert result["status"] == "MISMATCH"
    assert any(c == dict(check="category_sum_" + field, status="MISMATCH")
               for c in result["checks"])


@pytest.mark.asyncio
@pytest.mark.parametrize("amount,relation", [("111", "DIFFERENT"), ("110", "EQUAL")])
async def test_unknown_cross_summary_identity_cannot_fail_or_certify_the_table(amount, relation):
    body = payload()
    body["output2"]["nass_tot_amt"] = amount
    result = await read(lambda r: httpx.Response(200, json=body, headers={"tr_cont": "E"}))
    assert result["status"] == "MATCH"
    assert result["schema_version"] == 2
    assert result["comparisons"] == [dict(
        check="table_net_assets_vs_summary", relation=relation,
        equivalence_verified=False, reason="AGGREGATION_CONTRACT_UNVERIFIED",
    )]
    assert result["execution_nav_verified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("part,field", [("output1", "real_nass_amt"),
                                        ("output2", "dncl_amt")])
async def test_changed_asset_or_cash_fields_are_not_a_stable_account(part, field):
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        body = payload()
        if calls == 2:
            row = body[part][0] if part == "output1" else body[part]
            row[field] = "112"
        return httpx.Response(200, json=body, headers={"tr_cont": "D"})

    result = await read(handle)
    assert result["status"] == "CHANGED"
    assert result["comparisons"][0]["relation"] == "UNAVAILABLE"
    assert result["comparisons"][0]["reason"] == "REPORT_CHANGED"


@pytest.mark.asyncio
@pytest.mark.parametrize("part,bad,reason", [
    ("output1", [], "CATEGORY_TABLE_SHAPE"),
    ("output1", [{}] * 19, "CATEGORY_TABLE_SHAPE"),
    ("output1", [{}] * 21, "CATEGORY_TABLE_SHAPE"),
    ("output1", [None] * 20, "CATEGORY_TABLE_SHAPE"),
    ("output2", [], "SUMMARY_SHAPE"),
    ("output2", [{}], "SUMMARY_SHAPE"),
])
async def test_wrong_category_or_summary_shape_is_never_partial_success(part, bad, reason):
    body = payload()
    body[part] = bad
    with pytest.raises(AccountReadError, match="ASSETS_" + reason):
        await read(lambda r: httpx.Response(200, json=body, headers={"tr_cont": "D"}))


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "", True, 1.2, "NaN", "Infinity", "1e3", "9" * 80])
@pytest.mark.parametrize("part,field", [("output1", "whol_weit_rt"),
                                        ("output2", SUMMARY_FIELDS[-1])])
async def test_invalid_numbers_including_last_summary_field_are_not_zero(part, field, value):
    body = payload()
    (body[part][-1] if part == "output1" else body[part])[field] = value
    with pytest.raises(AccountReadError, match="ASSETS_INVALID_NUMBER") as exc:
        await read(lambda r: httpx.Response(200, json=body, headers={"tr_cont": "D"}))
    assert exc.value.shape["field"] == field
    assert str(exc.value) == "ASSETS_INVALID_NUMBER"


@pytest.mark.asyncio
@pytest.mark.parametrize("header", [None, "M", "F", "PRIVATE_VALUE"])
async def test_incomplete_or_unknown_pagination_is_rejected(header):
    headers = {} if header is None else {"tr_cont": header}
    with pytest.raises(AccountReadError, match="ASSETS_INCOMPLETE_RESPONSE"):
        await read(lambda r: httpx.Response(200, json=payload(), headers=headers))


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["business", "http", "json", "transport"])
async def test_remote_errors_do_not_leak_broker_text(case):
    def handle(request):
        if case == "transport":
            raise httpx.ConnectError("PRIVATE_ERROR")
        if case == "json":
            return httpx.Response(200, text="PRIVATE_ERROR")
        return httpx.Response(503 if case == "http" else 200,
                              json=dict(rt_cd="1", msg1="PRIVATE_ERROR"))

    with pytest.raises(AccountReadError) as exc:
        await read(handle)
    assert "PRIVATE" not in str(exc.value)


@pytest.mark.asyncio
async def test_late_second_read_is_rejected():
    times = iter([NOW] * 4 + [NOW + timedelta(seconds=31)])
    with pytest.raises(AccountReadError, match="ASSETS_STALE_BATCH"):
        await read(lambda r: httpx.Response(200, json=payload(), headers={"tr_cont": "D"}),
                   now=lambda: next(times))


@pytest.mark.asyncio
async def test_negative_net_assets_and_zero_categories_are_preserved():
    body = payload()
    for row in (body["output1"][0], body["output1"][-1]):
        row["real_nass_amt"] = "-1.25"
    body["output2"]["nass_tot_amt"] = "-1.25"
    result = await read(lambda r: httpx.Response(200, json=copy.deepcopy(body),
                                                headers={"tr_cont": "D"}))
    assert result["status"] == "MATCH"


@pytest.mark.asyncio
@pytest.mark.parametrize("include_transactions", [False, True])
async def test_operator_command_reads_both_reports_and_keeps_amounts_private(
    monkeypatch, include_transactions,
):
    path = Path(__file__).resolve().parents[2] / "scripts/intraday_balance_check.py"
    spec = importlib.util.spec_from_file_location("asset_balance_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.path.endswith("inquire-period-trans"):
            body = dict(rt_cd="0", output1=[dict(
                trad_dt="20260908", sttl_dt="20260909", pdno="SPY", crcy_cd="USD",
                sll_buy_dvsn_cd="02", ccld_qty="1", tr_frcr_amt2="601.37",
                frcr_excc_amt_1="602", dmst_frcr_fee1="0.63", frcr_fee1="0",
            )], output2=[], ctx_area_fk100="", ctx_area_nk100="")
        elif request.url.path == ASSETS_URL:
            body = payload()
        else:
            body = dict(rt_cd="0", output1=[], output2=[dict(
                crcy_cd="USD", frcr_dncl_amt_2="601.37",
            )], output3=dict(tot_asst_amt="110"))
        return httpx.Response(200, json=body, headers={"tr_cont": "D"})

    async def token(*args, **kwargs):
        return SimpleNamespace(access_token="PRIVATE_TOKEN")

    original_client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(handle),
    ))
    monkeypatch.setattr(module, "get_valid_token", token)
    monkeypatch.setattr(module, "ResilientClient", lambda client, **kwargs: client)
    for key, value in dict(KIS_APP_KEY="PRIVATE_KEY", KIS_APP_SECRET="PRIVATE_SECRET",
                           KIS_ACCOUNT_NO="1234567801").items():
        monkeypatch.setenv(key, value)
    result, code = await module.run(**(dict(
        transactions_from="20260901", transactions_through="20260910",
    ) if include_transactions else {}))
    assert code == 0 and len(requests) == (6 if include_transactions else 5)
    assert all(r.method == "GET" for r in requests)
    assert [r.url.path.rsplit("/", 1)[-1] for r in requests[:5]] == [
        "inquire-present-balance", "inquire-paymt-stdr-balance",
        "inquire-account-balance", "inquire-account-balance", "inquire-present-balance",
    ]
    if include_transactions:
        assert result["transactions"]["row_count"] == 1
        assert result["transactions"]["execution_parity_verified"] is False
        assert result["transactions"]["settlement_audit"]["status"] == "MATCH"
        assert requests[-1].url.params["ERLM_STRT_DT"] == "20260901"
    assert result["account_assets"]["status"] == "MATCH"
    assert result["nav_verified"] is False
    for private in ("PRIVATE", "601.37", "12345678", "110", "SPY", "0.63"):
        assert private not in json.dumps(result)
