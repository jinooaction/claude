import copy
import json
from decimal import localcontext

import pytest

from auto_invest.broker.account_asset_evidence import ASSETS_URL
from auto_invest.broker.account_cash_comparison import ROOT
from auto_invest.broker.domestic_account import SUMMARY_FIELDS, URL
from auto_invest.broker.domestic_cash_comparison import compare_domestic_cash_sources


def records():
    domestic = dict.fromkeys(SUMMARY_FIELDS, "0")
    domestic.update(dict.fromkeys(("dnca_tot_amt", "nxdy_excc_amt", "prvs_rcdl_excc_amt",
                                  "nass_amt", "tot_evlu_amt"), "731.45"))
    summary = dict(dncl_amt="0", tot_dncl_amt="963.45", frcr_evlu_tota="232")
    table = [dict(evlu_amt="0") for _ in range(20)]
    table[17]["evlu_amt"] = "731.45"
    return [
        dict(endpoint=URL, http_status=200, data=dict(rt_cd="0", output2=[domestic])),
        dict(endpoint=ROOT + "inquire-present-balance", http_status=200,
             data=dict(rt_cd="0", output3=summary)),
        dict(endpoint=ASSETS_URL, http_status=200,
             data=dict(rt_cd="0", output1=table, output2=copy.deepcopy(summary))),
    ]


def test_report_relations_are_private_diagnostics_not_cash_authority():
    source = records()
    before = copy.deepcopy(source)
    result = compare_domestic_cash_sources(source)
    assert result["domestic_reference_status"] == "AVAILABLE"
    assert result["domestic_checks"]["other_components_zero"] is True
    assert result["domestic_checks"]["deposit_vs_d2"] == "EQUAL"
    current, assets = result["comparisons"]
    assert current["domestic_deposit_vs_reported_deposit"] == "DIFFERENT"
    assert current["domestic_deposit_vs_total_deposit"] == "DIFFERENT"
    assert current["domestic_plus_foreign_vs_total_deposit"] == "EQUAL"
    assert current["domestic_deposit_vs_deposit_category"] == "UNAVAILABLE"
    assert assets["domestic_deposit_vs_deposit_category"] == "EQUAL"
    assert all(row["equivalence_verified"] is False for row in result["comparisons"])
    assert result["cash_aggregation_verified"] is result["live_eligible"] is False
    assert result["temporal_equivalence_verified"] is False
    assert source == before
    assert not any(value in json.dumps(result) for value in ("731.45", "963.45", "232"))


def test_repeated_domestic_pages_compare_all_values_without_summing():
    source = records()
    duplicate = copy.deepcopy(source[0])
    duplicate["data"]["output2"][0]["dnca_tot_amt"] = "731.4500"
    source.append(duplicate)
    assert compare_domestic_cash_sources(source)["comparisons"][1][
        "domestic_deposit_vs_deposit_category"] == "EQUAL"
    duplicate["data"]["output2"][0]["tot_loan_amt"] = "1"
    changed = compare_domestic_cash_sources(source)
    assert changed["domestic_reference_status"] == "CHANGED"
    assert changed["comparisons"] == []


@pytest.mark.parametrize("value", [None, "", "NaN", "Infinity", True, 0, [], "1e3"])
def test_missing_invalid_domestic_values_are_not_zero(value):
    source = records()
    source[0]["data"]["output2"][0]["cma_evlu_amt"] = value
    result = compare_domestic_cash_sources(source)
    assert result["domestic_reference_status"] == "INVALID"
    assert result["comparisons"] == []


def test_foreign_summary_duplicates_and_transport_failure_are_unavailable():
    source = records()
    row = source[1]["data"]["output3"]
    source[1]["data"]["output3"] = [row, row]
    source[2]["http_status"] = 500
    result = compare_domestic_cash_sources(source)
    for entry in result["comparisons"]:
        assert entry["domestic_plus_foreign_vs_total_deposit"] == "UNAVAILABLE"
        assert entry["domestic_deposit_vs_deposit_category"] == "UNAVAILABLE"


def test_product21_layout_never_uses_ordinary_category_index():
    source = records()
    source[2]["data"]["output1"] = source[2]["data"]["output1"][:17]
    assert compare_domestic_cash_sources(source)["comparisons"][1][
        "domestic_deposit_vs_deposit_category"] == "UNAVAILABLE"


def test_negative_cash_and_decimal_precision_preserved():
    source = records()
    source[0]["data"]["output2"][0]["dnca_tot_amt"] = "-731.45"
    source[1]["data"]["output3"].update(frcr_evlu_tota="963.45", tot_dncl_amt="232")
    with localcontext() as context:
        context.prec = 3
        result = compare_domestic_cash_sources(source)
    assert result["domestic_checks"]["deposit_vs_d2"] == "DIFFERENT"
    assert result["comparisons"][0]["domestic_plus_foreign_vs_total_deposit"] == "EQUAL"


@pytest.mark.parametrize("source", [None, {}, [], [None, dict(endpoint=[])], [None] * 201])
def test_absent_or_malformed_sources_never_claim_available(source):
    result = compare_domestic_cash_sources(source)
    assert result["domestic_reference_status"] == "UNAVAILABLE"
    assert result["comparisons"] == []
