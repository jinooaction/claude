import importlib.util
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.broker.account_asset_evidence import SUMMARY_FIELDS, TABLE_FIELDS
from auto_invest.broker.domestic_account import SUMMARY_FIELDS as DOMESTIC_SUMMARY_FIELDS
from auto_invest.broker.intraday_account import AccountReadError
from auto_invest.execution.intraday_account_history import AccountHistory, AccountHistoryError
from auto_invest.persistence.db import get_connection, migrate

ACCOUNT = "1234567801"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/intraday_balance_check.py"
    spec = importlib.util.spec_from_file_location("history_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    execution = tmp_path / "execution.db"
    connection = get_connection(execution)
    migrate(connection)
    connection.execute("""INSERT INTO orders
        (correlation_id, rule_id, symbol, side, order_type, qty, state)
        VALUES ('old-order','existing-strategy','SPY','BUY','LIMIT',3,'FILLED')""")
    connection.execute("""INSERT INTO fills
        (order_correlation_id,kis_fill_id,qty,price_usd,executed_at_utc)
        VALUES ('old-order','old-fill-1',1,'40','2026-06-01T00:00:00Z'),
               ('old-order','old-fill-2',2,'41','2026-06-02T00:00:00Z')""")
    connection.close()
    before = execution.read_bytes()
    state = dict(amount="601.37", calls=0, fail_at=None)

    def handle(request):
        state["calls"] += 1
        assert request.method == "GET"
        if state.get("on_request"):
            state.pop("on_request")()
        if state["calls"] == state["fail_at"]:
            return httpx.Response(500, json=dict(msg1="PRIVATE_BROKER_ERROR"))
        endpoint = request.url.path.split("/")[-1]
        if request.url.path == "/uapi/domestic-stock/v1/trading/inquire-balance":
            assert request.url.params["FUND_STTL_ICLD_YN"] == "Y"
            body = dict(rt_cd="0", output1=[],
                        output2=[dict.fromkeys(DOMESTIC_SUMMARY_FIELDS, "0")],
                        ctx_area_fk100="", ctx_area_nk100="")
        elif endpoint == "inquire-balance":
            body = dict(rt_cd="0", output1=[dict(
                ovrs_pdno="SPY", ovrs_cblc_qty="3", ord_psbl_qty="3", tr_crcy_cd="USD",
                ovrs_excg_cd="NASD", now_pric2="41", ovrs_stck_evlu_amt="123",
            )], ctx_area_fk200="", ctx_area_nk200="")
        elif endpoint == "inquire-nccs":
            body = dict(rt_cd="0", output=[], ctx_area_fk200="", ctx_area_nk200="")
        elif endpoint == "inquire-psamount":
            body = dict(rt_cd="0", output=dict(ovrs_ord_psbl_amt="500"))
        elif endpoint == "foreign-margin":
            body = dict(rt_cd="0", output=[dict(
                crcy_cd="USD", frcr_dncl_amt1=state["amount"], ustl_buy_amt="0",
                ustl_sll_amt="0", frcr_rcvb_amt="0", frcr_mgn_amt="0",
                frcr_gnrl_ord_psbl_amt="500",
            )])
        elif endpoint == "inquire-account-balance":
            row = dict.fromkeys(TABLE_FIELDS + ("whol_weit_rt",), "0")
            body = dict(rt_cd="0", output1=[dict(row) for _ in range(20)],
                        output2=dict.fromkeys(SUMMARY_FIELDS, "0"))
        else:
            body = dict(rt_cd="0", output1=[], output2=[dict(
                crcy_cd="USD", frcr_dncl_amt_2=state["amount"],
            )], output3=dict(tot_asst_amt="PRIVATE_REPORTED_TOTAL"))
            if state.get("model_ready"):
                body["output2"][0].update(frcr_buy_mgn_amt="0", frcr_etc_mgna="0",
                                          frst_bltn_exrt="1000")
                body["output3"] = dict.fromkeys(("dncl_amt", "tot_dncl_amt", "cma_evlu_amt",
                    "tot_loan_amt", "ustl_buy_amt_smtl", "ustl_sll_amt_smtl"), "0")
                body["output1"] = [dict(pdno="SPY", buy_crcy_cd="USD", ovrs_excg_cd="NASD",
                    ccld_qty_smtl1="3", ord_psbl_qty1="3", loan_rmnd="0", frcr_evlu_amt2="123")]
                if state.get("model_fault") == "cash_change" and state["calls"] == 10:
                    body["output2"][0]["frcr_dncl_amt_2"] = "600"
                if state.get("model_fault") == "quantity_change" and state["calls"] == 10:
                    body["output1"][0]["ccld_qty_smtl1"] = "4"
        if endpoint == "foreign-margin" and state.get("model_fault") == "receivable":
            body["output"][0]["frcr_rcvb_amt"] = "1"
        return httpx.Response(200, json=body, headers={"tr_cont": "D"})

    async def token(*args, **kwargs):
        return SimpleNamespace(access_token="PRIVATE_TOKEN")

    original = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(handle),
    ))
    monkeypatch.setattr(module, "get_valid_token", token)
    monkeypatch.setattr(module, "ResilientClient", lambda client, **kwargs: client)
    for key, value in dict(KIS_APP_KEY="PRIVATE_KEY", KIS_APP_SECRET="PRIVATE_SECRET",
                           KIS_ACCOUNT_NO=ACCOUNT).items():
        monkeypatch.setenv(key, value)
    return module, tmp_path / "history.db", execution, before, state


def rows(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT * FROM account_observations ORDER BY seq").fetchall()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "cash_change", "quantity_change", "receivable"])
async def test_actual_owned_reports_reach_cash_and_holdings_models_without_extra_gets(setup, fault):
    module, history, execution, before, state = setup
    state.update(model_ready=True, model_fault=fault)
    result, code = await module.run(history_db=history, execution_db=execution)
    models = result["account_models"]
    assert code == 0 and state["calls"] == 10 and models["additional_requests"] == 0
    assert result["history"]["status"] == "COMPLETE"
    assert result["history"]["response_count"] == 10
    assert execution.read_bytes() == before
    assert not models["full_account_scope_verified"] and not models["cash_aggregation_verified"]
    assert not models["nav_verified"] and not models["live_eligible"]
    if fault in {"cash_change", "receivable"}:
        assert models["zero_adjustment_cash"]["status"] == "UNAVAILABLE"
        assert models["reported_settlement_cash"]["status"] == "UNAVAILABLE"
        assert models["reported_cash_valuation"]["status"] == "UNAVAILABLE"
    else:
        for part in ("zero_adjustment_cash", "reported_settlement_cash", "reported_cash_valuation"):
            assert models[part]["status"] == "CALCULATED"
    if fault == "quantity_change":
        assert models["current_holdings"]["reason"] == "HOLDINGS_CHANGED"
        assert models["holdings_coverage"]["status"] == "UNAVAILABLE"
    else:
        assert models["current_holdings"]["status"] == "OBSERVED"
        assert models["holdings_coverage"]["status"] == "MATCH"
    encoded = json.dumps(result)
    for private in (
        "PRIVATE", "SPY", state["amount"], ACCOUNT, "amount_usd", "reported_components",
    ):
        assert private not in encoded
    assert "SPY" in json.loads(rows(history)[0][2])["responses"][2]["data"]["output1"][0].values()


@pytest.mark.asyncio
async def test_actual_parsers_capture_baseline_and_resume_without_historical_dates(setup):
    module, history, execution, before, state = setup
    for index, amount in enumerate(("601.37", "590.12"), 1):
        state["amount"] = amount
        result, code = await module.run(history_db=history, execution_db=execution)
        assert code == 0
        assert result["history"] == dict(status="COMPLETE", observation_sequence=index,
                                          response_count=10, live_eligible=False)
        assert result["nav_verified"] is result["cash_verified"] is False
        assert amount not in json.dumps(result)
        assert result["current_account"]["position_count"] == 1
        assert result["domestic_account"]["holding_count"] == 0
        assert not result["domestic_account"]["full_account_verified"]
        domestic_comparison = result["domestic_cash_comparison"]
        assert domestic_comparison["domestic_reference_status"] == "AVAILABLE"
        assert not domestic_comparison["cash_aggregation_verified"]
        assert len(domestic_comparison["comparisons"]) == 5
        responses = json.loads(rows(history)[-1][2])["responses"]
        assert [row["endpoint"].rsplit("/", 1)[-1] for row in responses] == [
            "inquire-present-balance", "inquire-paymt-stdr-balance", "inquire-balance",
            "inquire-nccs", "inquire-psamount", "foreign-margin", "inquire-balance",
            "inquire-account-balance", "inquire-account-balance", "inquire-present-balance",
        ]
        recorded = responses[6]
        assert recorded["endpoint"] == "/uapi/domestic-stock/v1/trading/inquire-balance"
        assert recorded["params"]["FUND_STTL_ICLD_YN"] == "Y"
        assert recorded["data"]["output2"][0]["tot_loan_amt"] == "0"
        profile = result["source_structure"]
        assert profile["status"] == "SOURCE_STRUCTURE_REVIEWED"
        assert profile["cash_aggregation_verified"] is False
        assert profile["responses"][0]["USD"]["row_count"] == 1
        assert profile["responses"][0]["USD"]["fields"]["frcr_dncl_amt1"]["zero_count"] == 0
        comparison = result["cash_source_comparison"]
        assert comparison["common_margin_cash_available"] is True
        assert all(row["common_deposit_vs_reported_usd"] == "EQUAL"
                   for row in comparison["comparisons"])
        assert comparison["cash_aggregation_verified"] is False
        components = result["account_components"]
        assert components["excluded_response_count"] == 0
        assert len(components["responses"]) == 6
        holdings = next(row for row in components["responses"]
                        if row["kind"] == "ORDINARY_US_HOLDINGS")
        assert holdings["kind"] == "ORDINARY_US_HOLDINGS"
        assert holdings["groups"]["LISTED_US"]["fields"]["ovrs_cblc_qty"]["POSITIVE"] == 1
        assert components["execution_nav_verified"] is False
    records = rows(history)
    assert len(records) == 2
    first, last = [json.loads(row[2]) for row in records]
    assert first["responses"][0]["data"]["output2"][0]["frcr_dncl_amt_2"] == "601.37"
    assert last["responses"][0]["data"]["output2"][0]["frcr_dncl_amt_2"] == "590.12"
    assert last["ledger_before"] == last["ledger_after"]
    assert last["ledger_before"]["fills"] == dict(count=2, last_sequence=2)
    assert last["responses"][2]["data"]["output1"][0]["ovrs_cblc_qty"] == "3"
    assert execution.read_bytes() == before
    assert history.stat().st_mode & 0o777 == 0o600
    for secret in (ACCOUNT, "PRIVATE_KEY", "PRIVATE_SECRET", "PRIVATE_TOKEN"):
        assert secret not in json.dumps(records)
    with sqlite3.connect(history) as connection:
        for statement in ("DELETE FROM account_observations",
                          "UPDATE account_observations SET payload='{}'"):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(statement)


@pytest.mark.asyncio
async def test_failed_batch_preserves_partial_reads_and_next_run_does_not_replace_it(setup):
    module, history, execution, before, state = setup
    state["fail_at"] = 2
    with pytest.raises(AccountReadError):
        await module.run(history_db=history, execution_db=execution)
    first = rows(history)[0]
    payload = json.loads(first[2])
    assert payload["status"] == "FAILED" and len(payload["responses"]) == 2
    assert payload["responses"][-1]["http_status"] == 500
    assert "PRIVATE_BROKER_ERROR" not in first[2]
    await module.run(history_db=history, execution_db=execution)
    assert rows(history)[0] == first
    assert json.loads(rows(history)[1][2])["status"] == "COMPLETE"
    assert execution.read_bytes() == before


@pytest.mark.asyncio
async def test_changes_during_collection_are_visible_in_distinct_ledger_watermarks(setup):
    module, history, execution, _, state = setup

    def concurrent_event():
        with sqlite3.connect(execution) as connection:
            connection.execute("""INSERT INTO audit_log(ts_utc,event_type,payload_json)
                VALUES ('2026-09-10T00:00:00Z','WORKER_STARTED','{}')""")

    state["on_request"] = concurrent_event
    result, code = await module.run(history_db=history, execution_db=execution)
    assert code == 0 and result["cash_verified"] is False
    payload = json.loads(rows(history)[0][2])
    assert payload["ledger_before"]["audit_log"]["last_sequence"] == 0
    assert payload["ledger_after"]["audit_log"]["last_sequence"] == 1
    assert payload["ledger_before"]["account_binding_verified"] is False


@pytest.mark.asyncio
async def test_account_change_cannot_append_to_existing_journal(setup, monkeypatch):
    module, history, execution, _, _ = setup
    await module.run(history_db=history, execution_db=execution)
    before = history.read_bytes()
    monkeypatch.setenv("KIS_ACCOUNT_NO", "8765432101")
    with pytest.raises(AccountHistoryError, match="CHAIN_OR_ACCOUNT"):
        await module.run(history_db=history, execution_db=execution)
    assert history.read_bytes() == before


@pytest.mark.asyncio
async def test_tampered_prior_record_is_not_extended(setup):
    module, history, execution, _, _ = setup
    await module.run(history_db=history, execution_db=execution)
    with sqlite3.connect(history) as connection:
        connection.execute("DROP TRIGGER history_no_update")
        connection.execute("UPDATE account_observations SET payload='{}'")
    before = history.read_bytes()
    with pytest.raises(AccountHistoryError, match="CHAIN_OR_ACCOUNT"):
        await module.run(history_db=history, execution_db=execution)
    assert history.read_bytes() == before


@pytest.mark.parametrize("kind", ["public", "symlink", "hardlink", "same_db", "other_db"])
def test_unsafe_storage_is_rejected_without_changing_user_files(setup, kind):
    _, history, execution, before, _ = setup
    if kind == "public":
        history.touch(mode=0o644)
    elif kind == "symlink":
        history.symlink_to(execution)
    elif kind == "hardlink":
        os.link(execution, history)
    elif kind == "other_db":
        history.write_bytes(before)
        history.chmod(0o600)
    else:
        history = execution
    with pytest.raises(AccountHistoryError):
        AccountHistory(history, ACCOUNT, execution_db=execution)
    assert execution.read_bytes() == before


@pytest.mark.asyncio
async def test_no_credentials_means_no_created_history(setup, monkeypatch):
    module, history, _, _, state = setup
    monkeypatch.delenv("KIS_APP_KEY")
    result, code = await module.run(history_db=history)
    assert code == 2 and result["status"] == "DATA_ACCESS_REQUIRED"
    assert not history.exists() and state["calls"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url,account", [
    ("POST", "/uapi/overseas-stock/v1/trading/order", ACCOUNT),
    ("GET", "/uapi/overseas-stock/v1/trading/inquire-present-balance", "8765432101"),
])
async def test_recorder_rejects_writes_and_different_account_before_transport(
    tmp_path, method, url, account,
):
    class Never:
        async def request(self, *args, **kwargs):
            pytest.fail("transport must not be reached")

    history = AccountHistory(tmp_path / "history.db", ACCOUNT)
    with pytest.raises(AccountHistoryError, match="SCOPE"):
        await history.client(Never()).request(method, url, params=dict(
            CANO=account[:8], ACNT_PRDT_CD=account[8:],
        ))
