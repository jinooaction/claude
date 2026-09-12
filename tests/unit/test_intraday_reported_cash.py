from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import localcontext

import pytest

from auto_invest.broker.domestic_account import ROW_FIELDS, SUMMARY_FIELDS
from auto_invest.broker.intraday_reported_cash import normalize_reported_cash

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def inputs(cash="73145", rate="1000"):
    baseline = dict(status="CALCULATED", scope="REPORTED_ZERO_ADJUSTMENT_USD_BASELINE",
                    cash="601.37", reported_krw_total_deposit=cash,
                    reported_usd_krw_rate=rate,
                    observation_started_at=(NOW - timedelta(seconds=8)).isoformat(),
                    observation_completed_at=(NOW - timedelta(seconds=3)).isoformat())
    summary = dict.fromkeys(SUMMARY_FIELDS, "0")
    summary.update(dict.fromkeys(("dnca_tot_amt", "nxdy_excc_amt", "prvs_rcdl_excc_amt",
                                  "nass_amt", "tot_evlu_amt"), cash))
    domestic = dict(reporting_basis="KIS_DOMESTIC_CURRENT_BALANCE", currency="KRW",
                    pagination_complete=True, positions={}, summary=summary,
                    observation_started_at=(NOW - timedelta(seconds=2)).isoformat(),
                    observation_completed_at=(NOW - timedelta(seconds=1)).isoformat())
    return baseline, domestic


def test_reconciled_cash_preserves_each_currency_and_declares_fx_policy():
    baseline, domestic = inputs()
    before = deepcopy((baseline, domestic))
    result = normalize_reported_cash(baseline, domestic, observed_at=NOW)
    assert result["status"] == "CALCULATED"
    assert result["balances"] == {"KRW": "73145", "USD": "601.37"}
    assert result["amount_usd"] == "674.515000000000"
    assert result["reporting_fx"] == dict(usd_krw_rate="1000", basis="KIS_FIRST_POSTED_RATE",
                                         rounding="FLOOR_12_DECIMALS", executable_quote=False)
    assert result["full_account_verified"] is result["live_eligible"] is False
    assert (baseline, domestic) == before


def test_current_cash_frame_can_enclose_domestic_read_and_preserves_latest_receipt():
    baseline, domestic = inputs()
    baseline["observation_completed_at"] = NOW.isoformat()
    result = normalize_reported_cash(baseline, domestic, observed_at=NOW)
    assert result["status"] == "CALCULATED"
    assert result["observation_completed_at"] == NOW.isoformat()


@pytest.mark.parametrize("cash,expected", [("1", "601.703333333333"),
                                          ("-1", "601.036666666666")])
def test_signed_cash_conversion_rounds_down_independently_of_ambient_precision(cash, expected):
    baseline, domestic = inputs(cash, "3")
    with localcontext() as context:
        context.prec = 3
        result = normalize_reported_cash(baseline, domestic, observed_at=NOW)
    assert result["amount_usd"] == expected
    assert result["balances"]["KRW"] == cash


@pytest.mark.parametrize("fault,reason", [
    ("usd_missing", "CASH_USD_BASELINE_UNAVAILABLE"),
    ("currency", "CASH_DOMESTIC_REPORT_UNAVAILABLE"),
    ("pagination", "CASH_DOMESTIC_REPORT_UNAVAILABLE"),
    ("stale", "CASH_REPORT_INTERVAL_INVALID"),
    ("order", "CASH_REPORT_INTERVAL_INVALID"),
    ("future", "CASH_REPORT_INTERVAL_INVALID"),
    ("number", "CASH_DOMESTIC_AMOUNT_INVALID"),
    ("settlement", "CASH_DOMESTIC_SETTLEMENT_CHANGED"),
    ("loan", "CASH_DOMESTIC_OTHER_COMPONENTS_PRESENT"),
    ("trade", "CASH_DOMESTIC_OTHER_COMPONENTS_PRESENT"),
    ("hidden_loan", "CASH_DOMESTIC_OTHER_COMPONENTS_PRESENT"),
    ("krw_changed", "CASH_KRW_REPORTS_DIFFER"),
    ("fx_missing", "CASH_REPORTED_FX_UNAVAILABLE"),
    ("fx_zero", "CASH_REPORTED_FX_UNAVAILABLE"),
    ("overflow", "CASH_VALUATION_OUT_OF_RANGE"),
])
def test_uncertainty_returns_no_synthetic_cash(fault, reason):
    baseline, domestic = inputs()
    if fault == "usd_missing":
        baseline["status"] = "UNAVAILABLE"
    elif fault == "currency":
        domestic["currency"] = "USD"
    elif fault == "pagination":
        domestic["pagination_complete"] = 1
    elif fault == "stale":
        baseline["observation_started_at"] = (NOW - timedelta(seconds=31)).isoformat()
    elif fault == "order":
        domestic["observation_started_at"] = (NOW - timedelta(seconds=7)).isoformat()
    elif fault == "future":
        domestic["observation_completed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif fault == "number":
        domestic["summary"]["cma_evlu_amt"] = None
    elif fault == "settlement":
        domestic["summary"]["prvs_rcdl_excc_amt"] = "73144"
    elif fault in {"loan", "trade"}:
        domestic["summary"]["tot_loan_amt" if fault == "loan" else "thdt_buy_amt"] = "1"
    elif fault == "hidden_loan":
        domestic["positions"]["X"] = dict(dict.fromkeys(ROW_FIELDS, "0"), loan_amt="1")
    elif fault == "krw_changed":
        baseline["reported_krw_total_deposit"] = "73144"
    elif fault.startswith("fx_"):
        baseline["reported_usd_krw_rate"] = None if fault == "fx_missing" else "0"
    elif fault == "overflow":
        baseline, domestic = inputs("999999999999999999", "0.000000000001")
    result = normalize_reported_cash(baseline, domestic, observed_at=NOW)
    assert result["status"] == "UNAVAILABLE" and result["reason"] == reason
    assert result["amount_usd"] is result["balances"] is None


def test_zero_quantity_rows_are_kept_but_do_not_add_cash():
    baseline, domestic = inputs()
    domestic["positions"]["X"] = dict.fromkeys(ROW_FIELDS, "0")
    assert normalize_reported_cash(baseline, domestic, observed_at=NOW)["amount_usd"] == (
        "674.515000000000")
