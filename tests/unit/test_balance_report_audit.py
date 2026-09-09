import copy
import json

import pytest

from auto_invest.broker.balance_report_audit import audit_report, select_records


def report():
    return {
        "output1": [{
            "pdno": "PRIVATE", "buy_crcy_cd": "USD", "ovrs_excg_cd": "OTCB",
            "ccld_qty_smtl1": "2.5", "ovrs_now_pric1": "10", "frcr_pchs_amt": "20",
            "frcr_evlu_amt2": "25", "evlu_pfls_amt2": "5", "bass_exrt": "1300",
        }],
        "output2": [{
            "crcy_cd": "USD", "frcr_dncl_amt_2": "-12.34", "frcr_buy_mgn_amt": "4",
            "frcr_etc_mgna": "0", "frcr_drwg_psbl_amt_1": "0",
        }],
        "output3": [{
            "pchs_amt_smtl": "26000", "evlu_amt_smtl": "32500",
            "evlu_pfls_amt_smtl": "6500", "dncl_amt": "100", "cma_evlu_amt": "0",
            "tot_dncl_amt": "100", "frcr_evlu_tota": "500", "tot_asst_amt": "33100",
            "ustl_sll_amt_smtl": "0", "ustl_buy_amt_smtl": "0", "tot_loan_amt": "0",
        }],
    }


def checks(value):
    return {r["check"]: r for r in value["checks"]}


def test_fractional_otc_rows_and_signed_cash_are_audited_without_execution_promotion():
    data = report()
    result = audit_report(data, copy.deepcopy(data))
    assert result["status"] == "MATCH"
    assert all(c["status"] == "MATCH" for c in result["checks"])
    assert result["execution_nav_verified"] is False
    assert result["cash_composition_status"] == "CONTRACT_UNVERIFIED"
    assert result["positions_checked"] == 1
    text = json.dumps(result)
    for private in ("PRIVATE", "OTCB", "32500", "-12.34", "33100"):
        assert private not in text


@pytest.mark.parametrize("field", ["frcr_evlu_amt2", "frcr_pchs_amt", "evlu_pfls_amt2"])
def test_actual_arithmetic_discrepancies_are_detected(field):
    data = report()
    data["output1"][0][field] = "1"
    result = audit_report(data, copy.deepcopy(data))
    assert result["status"] == "MISMATCH"
    assert any(c["status"] == "MISMATCH" for c in result["checks"])


@pytest.mark.parametrize("value", [None, "", "NaN", "1e3", True, 2.5, "1" * 80])
def test_missing_and_invalid_values_are_not_zero_or_partial_success(value):
    data = report()
    data["output1"][0]["frcr_evlu_amt2"] = value
    result = audit_report(data, copy.deepcopy(data))
    assert result["status"] == "INCOMPLETE"
    assert result["invalid_field_count"] > 0


def test_duplicate_positions_are_not_deduplicated_or_double_counted():
    data = report()
    data["output1"] *= 2
    result = audit_report(data, copy.deepcopy(data))
    assert result["status"] == "INCOMPLETE"
    assert checks(result)["positions_unique"]["status"] == "INCOMPLETE"
    assert checks(result)["valuation_krw"]["status"] == "INCOMPLETE"


def test_duplicate_summary_and_currency_rows_remain_ambiguous():
    data = report()
    data["output2"] *= 2
    data["output3"] *= 2
    result = audit_report(data, copy.deepcopy(data))
    assert result["status"] == "INCOMPLETE"
    assert checks(result)["currencies_unique"]["status"] == "INCOMPLETE"
    assert checks(result)["summary_unique"]["status"] == "INCOMPLETE"


@pytest.mark.parametrize("part,field", [
    ("output1", "ccld_qty_smtl1"), ("output2", "frcr_buy_mgn_amt"),
    ("output3", "ustl_buy_amt_smtl"),
])
def test_changes_outside_the_old_currency_only_digest_are_detected(part, field):
    before, after = report(), report()
    after[part][0][field] = "7"
    result = audit_report(before, after)
    assert result["status"] == "CHANGED"
    assert checks(result)[part + "_stable"]["status"] == "CHANGED"


def test_rounding_uncertainty_is_reported_not_silently_accepted():
    data = report()
    data["output3"][0]["evlu_amt_smtl"] = "32500.4"
    result = audit_report(data, copy.deepcopy(data))
    assert checks(result)["valuation_krw"]["status"] == "INCOMPLETE"
    assert checks(result)["valuation_krw"]["reason"] == "ROUNDING_DIFFERENCE"
    assert result["status"] != "MATCH"


def test_unconfirmed_fx_unit_does_not_assume_one_yen_or_dong():
    data = report()
    data["output1"][0]["buy_crcy_cd"] = "JPY"
    data["output2"][0]["crcy_cd"] = "JPY"
    result = audit_report(data, copy.deepcopy(data))
    assert checks(result)["valuation_krw"]["reason"] == "FX_UNIT_UNVERIFIED"
    assert result["status"] == "INCOMPLETE"


def test_currency_coverage_missing_is_not_complete():
    data = report()
    data["output2"] = []
    assert checks(audit_report(data, data))["currency_coverage"]["status"] == "INCOMPLETE"


def test_empty_positions_can_match_zero_securities_summary():
    data = report()
    data["output1"] = []
    for field in ("pchs_amt_smtl", "evlu_amt_smtl", "evlu_pfls_amt_smtl"):
        data["output3"][0][field] = "0"
    assert audit_report(data, data)["status"] == "MATCH"


def test_row_order_does_not_create_a_change_and_raw_extras_are_not_retained():
    data = report()
    second = dict(data["output1"][0], pdno="SECOND")
    data["output1"].append(second)
    data["output1"][0]["prdt_name"] = "SECRET NAME"
    data["output1"][0]["account"] = "SECRET ACCOUNT"
    selected = select_records(data)
    assert "SECRET" not in json.dumps(selected)
    reordered = copy.deepcopy(selected)
    reordered["output1"].reverse()
    assert checks(audit_report(selected, reordered))["output1_stable"]["status"] == "MATCH"


def test_extra_currency_cash_fields_are_validated_even_without_holdings():
    data = report()
    data["output2"].append(dict(data["output2"][0], crcy_cd="EUR", frcr_buy_mgn_amt="bad"))
    assert audit_report(data, data)["status"] == "INCOMPLETE"


def test_large_report_is_bounded_but_late_failure_affects_verdict():
    data = report()
    data["output1"] = [dict(data["output1"][0], pdno=f"ASSET{i}") for i in range(1000)]
    data["output1"][-1]["frcr_evlu_amt2"] = "1"
    result = audit_report(data, data)
    assert result["status"] == "MISMATCH"
    assert len(result["checks"]) == 100 and result["checks_truncated"]
    assert result["check_counts"]["MISMATCH"] > 0
    assert sum(result["check_counts"].values()) == result["check_count"]


@pytest.mark.parametrize("reported,direction,within,native", [
    ("32513", "HIGHER", True, "DIFFERENT"),
    ("32487", "LOWER", True, "DIFFERENT"),
    ("32513.01", "HIGHER", False, "DIFFERENT"),
    ("25", "LOWER", False, "EQUAL"),
])
def test_mismatch_diagnostics_separate_units_and_precision_without_acceptance(
    reported, direction, within, native,
):
    data = report()
    data["output3"][0]["evlu_amt_smtl"] = reported
    result = audit_report(data, data)
    check = checks(result)["valuation_krw"]
    assert check["status"] == "MISMATCH"
    assert check["diagnostic"] == dict(
        native_sum_relation=native, reported_vs_converted=direction,
        within_one_cent_per_row_fx_bound=within, cause_verified=False,
    )
    assert reported not in json.dumps(result)
    assert result["execution_nav_verified"] is False


@pytest.mark.parametrize("case", ["changing", "duplicate", "missing", "currency"])
def test_ambiguous_report_does_not_produce_mismatch_cause_diagnostics(case):
    data = report()
    data["output3"][0]["evlu_amt_smtl"] = "32510"
    before = copy.deepcopy(data)
    if case == "changing":
        before["output2"][0]["frcr_buy_mgn_amt"] = "99"
    elif case == "duplicate":
        data["output1"] *= 2
        before = copy.deepcopy(data)
    elif case == "missing":
        data["output1"][0].pop("bass_exrt")
        before = copy.deepcopy(data)
    else:
        data["output1"][0]["buy_crcy_cd"] = "JPY"
        before = copy.deepcopy(data)
    assert all("diagnostic" not in c for c in audit_report(before, data)["checks"])
