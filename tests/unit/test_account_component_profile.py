import json
from copy import deepcopy

import pytest

from auto_invest.broker.account_component_profile import (
    ASSETS_URL,
    BALANCE_URL,
    BASES,
    SUMMARY_FIELDS,
    TABLE_FIELDS,
    profile_account_components,
)


def response(url, rows, field="output1", **changes):
    return dict(endpoint=url, http_status=200, data=dict(rt_cd="0", **{field: rows}), **changes)


@pytest.mark.parametrize("count", [17, 20])
def test_fixed_asset_table_keeps_all_rows_and_total_without_amounts(count):
    rows = [dict.fromkeys(TABLE_FIELDS, "0") for _ in range(count)]
    rows[3]["real_nass_amt"] = "923874.12345"
    rows[4]["crdt_lnd_amt"] = "-123.98765"
    rows[4]["private"] = "NEVER_EXPORT"
    rows[5].pop("evlu_amt")
    source = [response(ASSETS_URL, rows)]
    original = deepcopy(source)
    result = profile_account_components(source)
    actual = result["responses"][0]["rows"]
    assert len(actual) == count
    assert [row["row_index"] for row in actual] == list(range(count))
    assert [row["is_total"] for row in actual] == [False] * (count - 1) + [True]
    assert actual[3]["fields"]["real_nass_amt"] == "POSITIVE"
    assert actual[4]["fields"]["crdt_lnd_amt"] == "NEGATIVE"
    assert actual[5]["fields"]["evlu_amt"] == "UNAVAILABLE"
    assert source == original
    for private in ("923874", "123.98765", "NEVER_EXPORT", "private"):
        assert private not in json.dumps(result)
    assert not any(result[key] for key in (
        "full_account_scope_verified", "execution_nav_verified", "live_eligible",
    ))


def test_otc_quantity_zero_is_distinguished_from_held_and_unknown_rows():
    rows = [dict(ovrs_excg_cd="OTCB", ovrs_cblc_qty=value,
                 now_pric2="0", ovrs_stck_evlu_amt="0", ovrs_pdno="PRIVATE_SYMBOL")
            for value in ("0", "98.3456", None)]
    rows += [dict(ovrs_excg_cd="NAS", ovrs_cblc_qty="1"),
             dict(ovrs_excg_cd=["bad"], ovrs_cblc_qty="-1")]
    groups = profile_account_components([response(BALANCE_URL, rows)])["responses"][0]["groups"]
    assert groups["OTCB"]["fields"]["ovrs_cblc_qty"] == dict(
        ZERO=1, POSITIVE=1, NEGATIVE=0, UNAVAILABLE=1,
    )
    assert groups["LISTED_US"]["row_count"] == groups["OTHER_OR_UNKNOWN"]["row_count"] == 1
    assert groups["OTCB"]["fields"]["ord_psbl_qty"]["UNAVAILABLE"] == 3
    assert "PRIVATE_SYMBOL" not in json.dumps(groups) and "98.3456" not in json.dumps(groups)


@pytest.mark.parametrize("url,basis", list(BASES.items()))
def test_summary_outputs_stay_separate_with_missing_fields(url, basis):
    rows = [dict.fromkeys(SUMMARY_FIELDS, "0"), {"tot_loan_amt": "4.56"}]
    source = response(url, rows, "output3")
    result = profile_account_components([source, source])
    assert len(result["responses"]) == 2
    for item in result["responses"]:
        assert item["kind"] == basis + "_SUMMARY" and item["row_count"] == 2
        assert item["rows"][0]["tot_loan_amt"] == "ZERO"
        assert item["rows"][1]["tot_loan_amt"] == "POSITIVE"
        assert item["rows"][1]["tot_dncl_amt"] == "UNAVAILABLE"


@pytest.mark.parametrize("rows", [[], [{}] * 19, [{}] * 21, [{}] * 2001, [None], None])
def test_malformed_asset_tables_are_excluded_not_interpreted(rows):
    result = profile_account_components([response(ASSETS_URL, rows)])
    assert result["excluded_response_count"] == 1 and not result["responses"]


@pytest.mark.parametrize("value", [None, "", "NaN", "1e2", True, 0, "1,000", "9" * 19])
def test_invalid_holding_quantity_is_not_zero(value):
    result = profile_account_components([response(BALANCE_URL, [
        dict(ovrs_excg_cd="OTCB", ovrs_cblc_qty=value),
    ])])["responses"][0]["groups"]["OTCB"]
    assert result["fields"]["ovrs_cblc_qty"]["UNAVAILABLE"] == 1
    assert result["fields"]["ovrs_cblc_qty"]["ZERO"] == 0


def test_errors_unknown_endpoints_and_limits_do_not_create_components():
    failed = response(BALANCE_URL, [])
    failed["http_status"] = 500
    result = profile_account_components([None, {"endpoint": []},
                                         {"endpoint": "PRIVATE"}, failed])
    assert result["excluded_response_count"] == 1 and not result["responses"]
    assert not profile_account_components([failed] * 201)["responses"]
    assert not profile_account_components({})["responses"]
