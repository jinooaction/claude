import copy
import json
from decimal import localcontext

import pytest

from auto_invest.broker.account_cash_comparison import ROOT, compare_cash_sources
from auto_invest.broker.account_source_profile import CASH_FIELDS, MARGIN_URL


def sources():
    margin = dict.fromkeys(CASH_FIELDS, "0")
    margin.update(crcy_cd="USD", frcr_dncl_amt1="123.45")
    data = dict(rt_cd="0", output2=[dict(crcy_cd="USD", frcr_dncl_amt_2="123.45",
                                       frst_bltn_exrt="1000")], output3=dict(
        tot_dncl_amt="100", frcr_evlu_tota="123450", evlu_amt_smtl="10000",
        ustl_sll_amt_smtl="500", ustl_buy_amt_smtl="50", tot_asst_amt="134000",
    ))
    return [dict(endpoint=MARGIN_URL, http_status=200, data=dict(rt_cd="0", output=[margin] * 10)),
            dict(endpoint=ROOT + "inquire-present-balance", http_status=200, data=data),
            dict(endpoint=ROOT + "inquire-paymt-stdr-balance", http_status=200,
                 data=copy.deepcopy(data))]


def test_same_batch_comparisons_never_certify_or_publish_amounts():
    records = sources()
    before = copy.deepcopy(records)
    result = compare_cash_sources(records)
    assert result["common_margin_cash_available"] is True
    assert result["margin_adjustments_zero"] is True
    assert [row["reporting_basis"] for row in result["comparisons"]] == ["CURRENT", "SETTLED"]
    for row in result["comparisons"]:
        assert row["common_deposit_vs_reported_usd"] == "EQUAL"
        assert row["single_usd_conversion_vs_foreign_total"] == "EQUAL"
        assert row["hts_total_formula_candidate"] == "EQUAL"
        assert row["equivalence_verified"] is False
    assert result["cash_aggregation_verified"] is result["live_eligible"] is False
    assert records == before
    for amount in ("123.45", "123450", "134000"):
        assert amount not in json.dumps(result)


@pytest.mark.parametrize("part,field,value,check,expected", [
    ("output3", "tot_asst_amt", "134001", "hts_total_formula_candidate", "DIFFERENT"),
    ("output3", "tot_dncl_amt", None, "hts_total_formula_candidate", "UNAVAILABLE"),
    ("output2", "frcr_dncl_amt_2", "99", "common_deposit_vs_reported_usd", "DIFFERENT"),
    ("output2", "frst_bltn_exrt", "0", "single_usd_conversion_vs_foreign_total", "UNAVAILABLE"),
    ("output2", "frst_bltn_exrt", "NaN", "single_usd_conversion_vs_foreign_total", "UNAVAILABLE"),
])
def test_missing_or_different_fields_preserve_evidence(part, field, value, check, expected):
    records = sources()
    target = records[1]["data"][part]
    (target[0] if isinstance(target, list) else target)[field] = value
    result = compare_cash_sources(records)
    assert result["comparisons"][0][check] == expected
    assert result["comparisons"][1][check] == "EQUAL"


def test_duplicate_currency_summary_and_multiple_margin_snapshots_are_unavailable():
    records = sources()
    records.append(copy.deepcopy(records[0]))
    records[1]["data"]["output2"] *= 2
    summary = records[1]["data"]["output3"]
    records[1]["data"]["output3"] = [summary, summary]
    result = compare_cash_sources(records)
    assert result["common_margin_cash_available"] is False
    for field in ("common_deposit_vs_reported_usd", "single_usd_conversion_vs_foreign_total",
                  "hts_total_formula_candidate"):
        assert result["comparisons"][0][field] == "UNAVAILABLE"


@pytest.mark.parametrize("amount", ["1", None, "", "invalid"])
def test_other_currency_cannot_be_ignored_or_converted_with_usd_rate(amount):
    records = sources()
    records[1]["data"]["output2"].append(dict(crcy_cd="JPY", frcr_dncl_amt_2=amount))
    row = compare_cash_sources(records)["comparisons"][0]
    assert row["single_usd_conversion_vs_foreign_total"] == "UNAVAILABLE"
    assert row["other_reported_currency_amounts_zero"] is False


def test_bad_transport_and_non_string_fields_do_not_crash_or_certify():
    records = sources()
    records[0]["data"]["output"][0]["crcy_cd"] = None
    records[1]["http_status"] = 500
    records.append(dict(endpoint=[]))
    result = compare_cash_sources(records)
    assert result["common_margin_cash_available"] is False
    assert result["comparisons"][0]["hts_total_formula_candidate"] == "UNAVAILABLE"


def test_different_country_cash_is_not_replaced_by_first_row():
    records = sources()
    records[0]["data"]["output"] = copy.deepcopy(records[0]["data"]["output"])
    records[0]["data"]["output"][0] = dict(
        records[0]["data"]["output"][0], frcr_dncl_amt1="999",
    )
    result = compare_cash_sources(records)
    assert result["common_margin_cash_available"] is False
    assert result["comparisons"][0]["common_deposit_vs_reported_usd"] == "UNAVAILABLE"


def test_ambient_decimal_precision_does_not_round_comparisons():
    with localcontext() as context:
        context.prec = 3
        result = compare_cash_sources(sources())
    assert result["comparisons"][0]["hts_total_formula_candidate"] == "EQUAL"
    assert result["comparisons"][0]["single_usd_conversion_vs_foreign_total"] == "EQUAL"
