from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from auto_invest.broker.account_asset_evidence import ASSETS_URL, SUMMARY_FIELDS, TABLE_FIELDS
from auto_invest.broker.intraday_asset_scope import EXCLUDED_SUMMARY, reconcile_asset_categories

NOW = datetime(2026, 9, 12, 15, tzinfo=UTC)


def total(body):
    with localcontext() as context:
        context.prec = 80
        for field in TABLE_FIELDS:
            body["output1"][-1][field] = str(sum(
                (Decimal(row[field]) for row in body["output1"][:-1]), Decimal(0)))


def inputs():
    body = dict(rt_cd="0", output1=[dict.fromkeys(TABLE_FIELDS + ("whol_weit_rt",), "0")
                                   for _ in range(20)], output2=dict.fromkeys(SUMMARY_FIELDS, "0"))
    for index, amount in ((8, "123"), (16, "600"), (17, "70")):
        body["output1"][index].update(pchs_amt=amount, evlu_amt=amount, real_nass_amt=amount)
    total(body)
    body["output2"].update(dncl_amt="70", tot_dncl_amt="70", nass_tot_amt="999")
    reports = [dict(endpoint=ASSETS_URL, http_status=200, continuation="D", data=deepcopy(body),
                    started_at=(NOW-timedelta(seconds=8-i*2)).isoformat(),
                    received_at=(NOW-timedelta(seconds=7-i*2)).isoformat()) for i in range(2)]
    cash = dict(status="CALCULATED", scope="RECONCILED_KRW_USD_ZERO_ADJUSTMENT_CASH",
                balances=dict(KRW="70", USD="600"),
                observation_started_at=(NOW-timedelta(seconds=10)).isoformat(),
                observation_completed_at=NOW.isoformat())
    holdings = dict(status="MATCH", equity_holdings_matched=True,
                    scope="CURRENT_OVERSEAS_EQUITIES_ONLY", positive_holding_count=3)
    return reports, cash, holdings


def assess(values, product="01"):
    return reconcile_asset_categories(*values, observed_at=NOW, product=product)


def test_complete_category_crosscheck_preserves_inputs_and_never_certifies_current_scope():
    values = inputs()
    original = deepcopy(values)
    result = assess(values)
    assert result["status"] == "MATCH" and result["category_count"] == 19
    assert result["current_positive_holding_count"] == 3
    assert not result["full_account_scope_verified"] and not result["live_eligible"]
    assert values == original
    assert "999" not in str(result) and "600" not in str(result)


@pytest.mark.parametrize("category", sorted(set(range(19)) - {8, 16, 17}))
def test_each_other_category_is_checked_even_when_only_purchase_value_is_nonzero(category):
    values = inputs()
    body = values[0][0]["data"]
    body["output1"][category]["pchs_amt"] = "1"
    total(body)
    assert assess(values)["reason"] == "ASSET_SCOPE_OTHER_ASSET_PRESENT"


@pytest.mark.parametrize("field", EXCLUDED_SUMMARY)
def test_each_separate_liability_and_subscription_field_must_be_zero(field):
    values = inputs()
    values[0][1]["data"]["output2"][field] = "1"
    assert assess(values)["reason"] == "ASSET_SCOPE_OTHER_LIABILITY_PRESENT"


@pytest.mark.parametrize("fault,reason", [
    ("sum", "ASSET_SCOPE_CATEGORY_SUM_DIFFERS"),
    ("row_loan", "ASSET_SCOPE_OTHER_LIABILITY_PRESENT"),
    ("cash", "ASSET_SCOPE_CASH_UNAVAILABLE"),
    ("cash_shape", "ASSET_SCOPE_CURRENCY_UNAVAILABLE"),
    ("holdings", "ASSET_SCOPE_HOLDINGS_UNAVAILABLE"),
    ("missing", "ASSET_SCOPE_REPORTS_MISSING"),
    ("partial", "ASSET_SCOPE_RESPONSE_INVALID"),
    ("http", "ASSET_SCOPE_RESPONSE_INVALID"),
    ("interval", "ASSET_SCOPE_INTERVAL_INVALID"),
    ("stale", "ASSET_SCOPE_INTERVAL_INVALID"),
    ("krw", "ASSET_SCOPE_KRW_DIFFERS"),
    ("extra_equity", "ASSET_SCOPE_EQUITY_PRESENCE_DIFFERS"),
    ("cash_presence", "ASSET_SCOPE_FOREIGN_CASH_PRESENCE_DIFFERS"),
    ("change", "ASSET_SCOPE_COMPONENTS_CHANGED"),
])
def test_missing_inconsistent_or_changed_inputs_remain_unavailable(fault, reason):
    values = inputs()
    reports, cash, holdings = values
    body = reports[1]["data"]
    if fault == "sum":
        body["output1"][-1]["evlu_amt"] = "0"
    elif fault == "row_loan":
        body["output1"][8]["crdt_lnd_amt"] = "1"
        total(body)
    elif fault == "cash":
        cash["scope"] = []
    elif fault == "cash_shape":
        cash["balances"]["EUR"] = "0"
    elif fault == "holdings":
        holdings["equity_holdings_matched"] = False
    elif fault == "missing":
        reports.pop()
    elif fault == "partial":
        reports[1]["continuation"] = "M"
    elif fault == "http":
        reports[1]["http_status"] = 403
    elif fault == "interval":
        reports[1]["started_at"] = (NOW-timedelta(seconds=9)).isoformat()
    elif fault == "stale":
        cash["observation_started_at"] = (NOW-timedelta(seconds=31)).isoformat()
    elif fault == "krw":
        body["output2"]["dncl_amt"] = "71"
    elif fault == "extra_equity":
        holdings["positive_holding_count"] = 0
    elif fault == "cash_presence":
        cash["balances"]["USD"] = "0"
    else:
        body["output1"][8]["pchs_amt"] = "124"
        total(body)
    assert assess(values)["reason"] == reason


@pytest.mark.parametrize("product", ["21", "", "001", "AB", None])
def test_other_or_unknown_product_layouts_are_not_reinterpreted(product):
    assert assess(inputs(), product)["reason"] == "ASSET_SCOPE_PRODUCT_UNSUPPORTED"


def test_price_movement_and_native_nav_difference_do_not_change_asset_classification():
    values = inputs()
    body = values[0][1]["data"]
    body["output1"][8].update(evlu_amt="125", evlu_pfls_amt="2", real_nass_amt="125")
    body["output2"]["nass_tot_amt"] = "998"
    total(body)
    with localcontext() as context:
        context.prec = 2
        assert assess(values)["status"] == "MATCH"
