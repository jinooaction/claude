from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from auto_invest.broker.intraday_holdings_coverage import (
    CURRENT,
    MARGIN,
    compare_current_holdings,
    normalize_current_holdings,
)

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def records():
    rows = [dict(pdno="AAPL", buy_crcy_cd="USD", ovrs_excg_cd="NASD", ccld_qty_smtl1="2",
                 cblc_qty13="999", ord_psbl_qty1="2", loan_rmnd="0", frcr_evlu_amt2="250"),
            dict(pdno="ORANY", buy_crcy_cd="USD", ovrs_excg_cd="OTCB", ccld_qty_smtl1="0.5",
                 cblc_qty13="0", ord_psbl_qty1="0", loan_rmnd="0", frcr_evlu_amt2="20")]
    return [dict(endpoint=url, http_status=200, continuation="D", data=dict(rt_cd="0",
                 output1=deepcopy(rows)),
                 started_at=(NOW - timedelta(seconds=6 - i * 2)).isoformat(),
                 received_at=(NOW - timedelta(seconds=5 - i * 2)).isoformat())
            for i, url in enumerate((CURRENT, MARGIN, CURRENT))]


def ordinary():
    return dict(currency="USD", account_scope="US_ORDINARY_OVERSEAS_STOCK",
                pagination_complete=True, positions={"AAPL": dict(quantity=2)},
                unverified_assets={"ORANY": dict(reported_quantity="0.500",
                                                 reported_market_code="OTCB")},
                observation_started_at=(NOW - timedelta(seconds=10)).isoformat(),
                observation_completed_at=(NOW - timedelta(seconds=7)).isoformat())


def test_current_quantities_match_fractional_otc_without_adopting_settled_quantities():
    source = records()
    before = deepcopy(source)
    current = normalize_current_holdings(source, observed_at=NOW)
    assert current["status"] == "OBSERVED"
    assert current["positions"]["AAPL"]["quantity"] == "2"
    assert current["positions"]["ORANY"]["quantity"] == "0.5"
    result = compare_current_holdings(current, ordinary(), observed_at=NOW)
    assert result["status"] == "MATCH" and result["positive_holding_count"] == 2
    assert result["equity_holdings_matched"] is True
    assert result["full_account_verified"] is result["live_eligible"] is False
    assert source == before


def test_price_changes_are_not_quantity_changes_and_receive_no_source_timestamp():
    source = records()
    source[-1]["data"]["output1"][0]["frcr_evlu_amt2"] = "251.5"
    source[-1]["data"]["output1"][0]["ccld_qty_smtl1"] = "2.00"
    current = normalize_current_holdings(source, observed_at=NOW)
    assert current["status"] == "OBSERVED"
    assert current["positions"]["AAPL"]["reported_value"] == "251.5"
    assert current["positions"]["AAPL"]["price_source_at"] is None
    assert compare_current_holdings(current, ordinary(), observed_at=NOW)["status"] == "MATCH"


@pytest.mark.parametrize("start,end,expected", [(-5, -2, "MATCH"), (-20, -4, "UNAVAILABLE"),
                                              (-2, 1, "UNAVAILABLE"), (-2, -5, "UNAVAILABLE")])
def test_ordinary_read_must_be_enclosed_or_sequential_never_partially_overlap(start, end, expected):
    current = normalize_current_holdings(records(), observed_at=NOW)
    current["observation_started_at"] = (NOW - timedelta(seconds=10)).isoformat()
    current["observation_completed_at"] = NOW.isoformat()
    view = ordinary()
    view["observation_started_at"] = (NOW + timedelta(seconds=start)).isoformat()
    view["observation_completed_at"] = (NOW + timedelta(seconds=end)).isoformat()
    assert compare_current_holdings(current, view, observed_at=NOW)["status"] == expected


def test_missing_valuation_is_preserved_without_losing_valid_quantity_coverage():
    source = records()
    for record in (source[0], source[-1]):
        record["data"]["output1"][1].pop("frcr_evlu_amt2")
    current = normalize_current_holdings(source, observed_at=NOW)
    assert current["positions"]["ORANY"]["reported_value"] is None
    assert compare_current_holdings(current, ordinary(), observed_at=NOW)["status"] == "MATCH"


def test_zero_quantity_rows_remain_in_report_but_not_positive_holdings_comparison():
    source = records()
    for record in (source[0], source[-1]):
        record["data"]["output1"].append(dict(record["data"]["output1"][0], pdno="ZERO",
                                              ccld_qty_smtl1="0", ord_psbl_qty1="0"))
    current = normalize_current_holdings(source, observed_at=NOW)
    assert current["positions"]["ZERO"]["reported_value"] == "250"
    assert compare_current_holdings(current, ordinary(), observed_at=NOW)["status"] == "MATCH"


@pytest.mark.parametrize("field,value", [("ccld_qty_smtl1", "3"), ("ord_psbl_qty1", "1"),
                                         ("loan_rmnd", "1"), ("ovrs_excg_cd", "NYSE"),
                                         ("buy_crcy_cd", "HKD")])
def test_nonprice_changes_are_not_a_stable_holdings_observation(field, value):
    source = records()
    source[-1]["data"]["output1"][0][field] = value
    result = normalize_current_holdings(source, observed_at=NOW)
    assert result["reason"] == "HOLDINGS_CHANGED" and result["positions"] is None


@pytest.mark.parametrize("fault,reason", [
    ("duplicate", "HOLDINGS_DUPLICATE_SYMBOL"),
    ("quantity_missing", "HOLDINGS_AMOUNT_INVALID"),
    ("loan_missing", "HOLDINGS_AMOUNT_INVALID"),
    ("bad_value", "HOLDINGS_VALUE_INVALID"),
    ("oversellable", "HOLDINGS_AMOUNT_INVALID"),
    ("page", "HOLDINGS_PAGE_INCOMPLETE"),
    ("failure", "HOLDINGS_RESPONSE_INVALID"),
    ("stale", "HOLDINGS_INTERVAL_INVALID"),
])
def test_missing_or_invalid_reports_never_produce_coverage(fault, reason):
    source = records()
    row = source[0]["data"]["output1"][0]
    if fault == "duplicate":
        source[0]["data"]["output1"].append(deepcopy(row))
    elif fault == "quantity_missing":
        row.pop("ccld_qty_smtl1")
    elif fault == "loan_missing":
        row.pop("loan_rmnd")
    elif fault == "bad_value":
        row["frcr_evlu_amt2"] = "NaN"
    elif fault == "oversellable":
        row["ord_psbl_qty1"] = "3"
    elif fault == "page":
        source[0]["continuation"] = "M"
    elif fault == "failure":
        source[1]["http_status"] = 403
    elif fault == "stale":
        source[0]["started_at"] = (NOW - timedelta(seconds=31)).isoformat()
    result = normalize_current_holdings(source, observed_at=NOW)
    assert result["status"] == "UNAVAILABLE" and result["reason"] == reason


@pytest.mark.parametrize("fault,reason", [
    ("missing", "HOLDINGS_SCOPE_OR_QUANTITY_DIFFERS"),
    ("extra", "HOLDINGS_SCOPE_OR_QUANTITY_DIFFERS"),
    ("quantity", "HOLDINGS_SCOPE_OR_QUANTITY_DIFFERS"),
    ("otc_market", "HOLDINGS_SCOPE_OR_QUANTITY_DIFFERS"),
    ("currency", "HOLDINGS_OUTSIDE_US_SCOPE"),
    ("market", "HOLDINGS_OUTSIDE_US_SCOPE"),
    ("loan", "HOLDINGS_QUANTITY_OR_LOAN_INVALID"),
    ("ordinary_scope", "HOLDINGS_ORDINARY_SCOPE_INVALID"),
    ("time", "HOLDINGS_INTERVAL_INVALID"),
])
def test_scope_differences_do_not_disappear_when_comparing(fault, reason):
    current = normalize_current_holdings(records(), observed_at=NOW)
    account = ordinary()
    if fault == "missing":
        current["positions"].pop("ORANY")
    elif fault == "extra":
        current["positions"]["EXTRA"] = deepcopy(current["positions"]["AAPL"])
    elif fault == "quantity":
        account["positions"]["AAPL"]["quantity"] = 1
    elif fault == "otc_market":
        current["positions"]["ORANY"]["market"] = "NYSE"
    elif fault == "currency":
        current["positions"]["ORANY"]["currency"] = "JPY"
    elif fault == "market":
        current["positions"]["ORANY"]["market"] = "SEHK"
    elif fault == "loan":
        current["positions"]["ORANY"]["loan"] = "1"
    elif fault == "ordinary_scope":
        account["account_scope"] = "PARTIAL"
    elif fault == "time":
        account["observation_completed_at"] = NOW.isoformat()
    result = compare_current_holdings(current, account, observed_at=NOW)
    assert result["status"] == "UNAVAILABLE" and result["reason"] == reason
    assert result["equity_holdings_matched"] is False
