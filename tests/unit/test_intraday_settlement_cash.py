from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import localcontext

import pytest

from auto_invest.broker.account_source_profile import CASH_FIELDS
from auto_invest.broker.intraday_cash_baseline import (
    CURRENT,
    MARGIN,
    normalize_cash_baseline,
    normalize_usd_settlement_cash,
)

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def records(buy="100", sell="25", reserve="200"):
    from decimal import Decimal
    currency = dict(crcy_cd="USD", frcr_dncl_amt_2=str(Decimal("601.37") - Decimal(reserve)),
                    frcr_buy_mgn_amt=reserve, frcr_etc_mgna="0", frst_bltn_exrt="1000")
    current = dict(rt_cd="0", output2=[currency], output3=dict(
        dncl_amt="0", tot_dncl_amt="73145", cma_evlu_amt="0", tot_loan_amt="0",
        ustl_buy_amt_smtl="100000", ustl_sll_amt_smtl="25000"))
    margin = dict.fromkeys(CASH_FIELDS, "0")
    margin.update(crcy_cd="USD", frcr_dncl_amt1="601.37", ustl_buy_amt=buy,
                  ustl_sll_amt=sell, frcr_mgn_amt=reserve)
    return [dict(endpoint=url, http_status=200, continuation="D", data=deepcopy(data),
                 started_at=(NOW - timedelta(seconds=6 - i * 2)).isoformat(),
                 received_at=(NOW - timedelta(seconds=5 - i * 2)).isoformat())
            for i, (url, data) in enumerate(((CURRENT, current),
                (MARGIN, dict(rt_cd="0", output=[deepcopy(margin) for _ in range(10)])),
                (CURRENT, current)))]


def test_settlement_cash_keeps_reservation_separate_and_preserves_original_reports():
    source = records()
    before = deepcopy(source)
    result = normalize_usd_settlement_cash(source, observed_at=NOW)
    assert result["status"] == "CALCULATED" and result["cash"] == "526.37"
    assert result["available_usd"] == "401.37" and result["reserved_usd"] == "200"
    assert result["reported_components"]["ustl_buy_amt"] == "100"
    assert result["usd_margin_row_count"] == 10
    assert result["reported_krw_total_deposit"] == "73145"
    assert result["fees_inclusion_verified"] is result["full_account_verified"] is False
    assert not result["live_eligible"]
    assert normalize_cash_baseline(source, observed_at=NOW)["status"] == "UNAVAILABLE"
    assert source == before


@pytest.mark.parametrize("buy,sell,reserve,cash", [
    ("0", "0", "200", "601.37"),  # unfilled reservations do not reduce net assets
    ("50", "0", "100", "551.37"),
    ("100", "200", "0", "701.37"),
    ("700", "0", "0", "-98.63"),
])
def test_pending_and_completed_cash_legs_are_signed_arithmetic(buy, sell, reserve, cash):
    source = records(buy, sell, reserve)
    with localcontext() as context:
        context.prec = 3
        result = normalize_usd_settlement_cash(source, observed_at=NOW)
    assert result["cash"] == cash


@pytest.mark.parametrize("fault,reason", [
    ("deposit", "SETTLEMENT_CASH_ANCHOR_DIFFERS"),
    ("reserve", "SETTLEMENT_CASH_ANCHOR_DIFFERS"),
    ("noncommon", "SETTLEMENT_COMPONENTS_NOT_COMMON"),
    ("receivable", "SETTLEMENT_RECEIVABLE_PRESENT"),
    ("other", "SETTLEMENT_OTHER_CURRENCY_PRESENT"),
    ("blank", "SETTLEMENT_OTHER_CURRENCY_PRESENT"),
    ("changed", "SETTLEMENT_REPORT_CHANGED"),
    ("duplicate", "SETTLEMENT_USD_ROW_NOT_UNIQUE"),
    ("missing", "BASELINE_AMOUNT_INVALID"),
    ("stale", "SETTLEMENT_TIME_INVALID"),
    ("page", "SETTLEMENT_INCOMPLETE_REPORT"),
    ("failure", "SETTLEMENT_BROKER_RESPONSE_INVALID"),
    ("negative_summary", "SETTLEMENT_SUMMARY_AMOUNT_INVALID"),
])
def test_partial_or_conflicting_source_never_becomes_cash(fault, reason):
    source = records()
    rows = source[1]["data"]["output"]
    if fault == "deposit":
        rows[0]["frcr_dncl_amt1"] = "999"
    elif fault == "reserve":
        rows[0]["frcr_mgn_amt"] = "199"
    elif fault == "noncommon":
        rows[0]["ustl_buy_amt"] = "101"
    elif fault == "receivable":
        rows[0]["frcr_rcvb_amt"] = "1"
    elif fault in {"other", "blank"}:
        rows.append(dict(dict.fromkeys(CASH_FIELDS, "0"),
                         crcy_cd="EUR" if fault == "other" else "", ustl_buy_amt="1"))
    elif fault == "changed":
        source[-1]["data"]["output2"][0]["frcr_buy_mgn_amt"] = "201"
    elif fault == "duplicate":
        source[0]["data"]["output2"] *= 2
    elif fault == "missing":
        rows[0].pop("ustl_buy_amt")
    elif fault == "stale":
        source[0]["started_at"] = (NOW - timedelta(seconds=31)).isoformat()
    elif fault == "page":
        source[1]["continuation"] = "M"
    elif fault == "failure":
        source[1]["http_status"] = 503
    elif fault == "negative_summary":
        source[0]["data"]["output3"]["ustl_buy_amt_smtl"] = "-1"
    result = normalize_usd_settlement_cash(source, observed_at=NOW)
    assert result["status"] == "UNAVAILABLE" and result["reason"] == reason
    assert result["cash"] is None
