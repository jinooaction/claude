import hashlib
import importlib.util
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.broker.models import BrokerExecution
from auto_invest.config.enums import Side
from auto_invest.execution.intraday_cost_reconciliation import (
    CostReconciliationError,
    reconcile_cost_inputs,
)
from auto_invest.persistence import db


@pytest.fixture
def ledger(tmp_path):
    path = tmp_path / "existing.db"
    conn = db.get_connection(path)
    db.migrate(conn)
    conn.execute("""INSERT INTO orders
        (correlation_id, rule_id, symbol, side, order_type, qty, state, kis_order_id)
        VALUES ('local-1', 'intraday', 'SPY', 'BUY', 'LIMIT', 2, 'FILLED', 'broker-1')""")
    for index, price in enumerate(("100", "102")):
        conn.execute("""INSERT INTO fills
            (order_correlation_id, kis_fill_id, qty, price_usd, executed_at_utc)
            VALUES ('local-1', ?, 1, ?, '2000-01-01T00:00:00Z')""", (str(index), price))
    conn.commit()
    conn.close()
    return path


def execution(**changes):
    return BrokerExecution(**dict(dict(
        kis_order_id="broker-1", symbol="SPY", side=Side.BUY, market="AMEX",
        filled_qty=2, avg_fill_price_usd=Decimal("101"), unfilled_qty=0, terminal=True,
    ), **changes))


def transaction(**changes):
    return dict(dict(
        trad_dt="20260910", sttl_dt="20260911", pdno="SPY", crcy_cd="USD",
        sll_buy_dvsn_cd="02", ccld_qty="2", tr_frcr_amt2="202",
        frcr_excc_amt_1="202.50", dmst_frcr_fee1="0.40", frcr_fee1="0.10",
    ), **changes)


def test_order_ids_match_cumulative_fills_without_using_observation_dates_or_writing(ledger):
    before = hashlib.sha256(ledger.read_bytes()).digest()
    result = reconcile_cost_inputs(ledger, [execution()], [transaction()])
    assert result["status"] == "MATCH"
    assert result["matched_order_count"] == 1
    assert result["report_totals_match"] is True
    assert not result["per_order_fees_verified"]
    assert not result["account_cash_verified"]
    assert not result["execution_parity_verified"]
    assert result["scope"] == "SUPPLIED_BROKER_REPORTS"
    assert hashlib.sha256(ledger.read_bytes()).digest() == before
    assert all(value not in str(result) for value in ("SPY", "broker-1", "local-1", "202.50"))


@pytest.mark.parametrize("change,issue", [
    ({"kis_order_id": "external"}, "BROKER_ORDER_NOT_UNIQUELY_IN_LEDGER"),
    ({"symbol": "AAPL"}, "LEDGER_ORDER_IDENTITY_MISMATCH"),
    ({"side": Side.SELL}, "LEDGER_ORDER_IDENTITY_MISMATCH"),
    ({"filled_qty": 3}, "LEDGER_FILL_TOTAL_MISMATCH"),
    ({"avg_fill_price_usd": Decimal("101.000000000001")}, "LEDGER_FILL_TOTAL_MISMATCH"),
])
def test_broker_order_identity_quantity_and_notional_are_not_guessed(ledger, change, issue):
    result = reconcile_cost_inputs(ledger, [execution(**change)], [transaction()])
    assert result["status"] == "MISMATCH"
    assert issue in result["issues"]


@pytest.mark.parametrize("rows,issue", [
    ([], "NO_COMPARABLE_TRADES"),
    ([transaction(), transaction()], "TRANSACTION_EXECUTION_TOTAL_MISMATCH"),
    ([transaction(crcy_cd="EUR")], "NON_USD_TRANSACTION_SCOPE"),
    ([transaction(frcr_excc_amt_1="202.51")], "SETTLEMENT_ARITHMETIC_UNVERIFIED"),
])
def test_missing_duplicate_currency_and_cost_discrepancies_fail(ledger, rows, issue):
    result = reconcile_cost_inputs(ledger, [execution()], rows)
    assert result["report_totals_match"] is False
    assert issue in result["issues"]


def test_duplicate_order_id_cannot_double_count_an_execution(ledger):
    with pytest.raises(CostReconciliationError, match="COST_ORDER_IDENTITY_INVALID"):
        reconcile_cost_inputs(ledger, [execution(), execution()], [transaction()])


def test_aggregated_statement_does_not_allocate_fees_to_individual_orders(ledger):
    conn = db.get_connection(ledger)
    conn.execute("""INSERT INTO orders
        (correlation_id, rule_id, symbol, side, order_type, qty, state, kis_order_id)
        VALUES ('local-2', 'intraday', 'SPY', 'BUY', 'LIMIT', 2, 'FILLED', 'broker-2')""")
    conn.execute("""INSERT INTO fills
        (order_correlation_id, kis_fill_id, qty, price_usd, executed_at_utc)
        VALUES ('local-2', 'second', 2, '101', '2000-01-01T00:00:00Z')""")
    conn.commit()
    conn.close()
    result = reconcile_cost_inputs(ledger, [execution(), execution(kis_order_id="broker-2")], [
        transaction(ccld_qty="4", tr_frcr_amt2="404", frcr_excc_amt_1="405",
                    dmst_frcr_fee1="0.8", frcr_fee1="0.2"),
    ])
    assert result["report_totals_match"] is True
    assert result["matched_order_count"] == 2
    assert result["per_order_fees_verified"] is False


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(CostReconciliationError, match="COST_LEDGER_UNAVAILABLE"):
        reconcile_cost_inputs(path, [execution()], [transaction()])
    assert not path.exists()


@pytest.mark.asyncio
async def test_existing_command_connects_actual_transaction_and_execution_readers_to_db(
    ledger, monkeypatch,
):
    script = Path(__file__).resolve().parents[2] / "scripts/intraday_balance_check.py"
    spec = importlib.util.spec_from_file_location("cost_comparison_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("inquire-period-trans"):
            payload = dict(rt_cd="0", output1=[transaction()], output2=[])
        elif request.url.path.endswith("inquire-ccnl"):
            payload = dict(rt_cd="0", output=[dict(
                odno="broker-1", pdno="SPY", sll_buy_dvsn_cd="02", ovrs_excg_cd="AMEX",
                ft_ccld_qty="2", nccs_qty="0", ft_ccld_unpr3="101",
            )])
        else:
            raise AssertionError("Unexpected route")
        return httpx.Response(200, headers={"tr_cont": "D"}, json=payload)

    async def token(*args, **kwargs):
        return SimpleNamespace(access_token="offline")

    async def other_account_reports(*args, **kwargs):
        return {}

    original = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: original(
        **kw, transport=httpx.MockTransport(handle),
    ))
    monkeypatch.setattr(module, "ResilientClient", lambda client, **kwargs: client)
    monkeypatch.setattr(module, "get_valid_token", token)
    monkeypatch.setattr(module, "observe_balance_evidence", other_account_reports)
    monkeypatch.setattr(module, "observe_account_assets", other_account_reports)
    monkeypatch.setattr(module, "public_balance_evidence", lambda _: {"cash_verified": False})
    for name, value in dict(KIS_APP_KEY="offline", KIS_APP_SECRET="offline",
                            KIS_ACCOUNT_NO="1234567801").items():
        monkeypatch.setenv(name, value)
    before = hashlib.sha256(ledger.read_bytes()).digest()
    result, code = await module.run(
        transactions_from="20260910", transactions_through="20260910", execution_db=ledger,
    )
    assert code == 0
    assert result["transactions"]["ledger_comparison"]["status"] == "MATCH"
    assert result["transactions"]["execution_parity_verified"] is False
    assert len(calls) == 4 and all(request.method == "GET" for request in calls)
    assert all(request.url.params["CANO"] == "12345678" for request in calls)
    assert hashlib.sha256(ledger.read_bytes()).digest() == before
