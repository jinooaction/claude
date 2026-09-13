import json
from decimal import localcontext

import pytest

from auto_invest.execution.intraday_execution_evidence import ExecutionCostAssessment
from auto_invest.execution.intraday_observation_models import (
    ObservationModelError,
    assess_intervals,
    assess_next_bar_timing,
    settled_usd_cash,
)


def row(**changes):
    return dict(dict(frcr_dncl_amt1="600.123456789012", ustl_buy_amt="0",
                     ustl_sll_amt="0", frcr_rcvb_amt="0", frcr_mgn_amt="0"), **changes)


def test_cash_uses_only_explicitly_supported_report_scope():
    result = settled_usd_cash([row()])
    assert result["cash"] == "600.123456789012"
    assert not result["full_account_verified"]
    assert settled_usd_cash([row()], unclassified_rows=1)["cash"] is None
    assert settled_usd_cash([row(), row()])["cash"] is None
    assert settled_usd_cash([])["cash"] is None


@pytest.mark.parametrize("field", ["ustl_buy_amt", "ustl_sll_amt", "frcr_rcvb_amt", "frcr_mgn_amt"])
def test_cash_never_guesses_netting_or_fee_inclusion(field):
    assert settled_usd_cash([row(**{field: "1"})])["cash"] is None


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "", 1, None])
def test_bad_cash_is_not_zero(value):
    assert settled_usd_cash([row(frcr_dncl_amt1=value)])["cash"] is None


def interval(**changes):
    return dict(dict(order_id="o1", symbol="SPY", quantity=2,
                     before_submission="2026-09-10T14:01:00Z",
                     response_received="2026-09-10T14:07:00Z"), **changes)


@pytest.mark.parametrize(("changes", "verified"), [
    ({}, True),
    ({"decision_kind": "STRATEGY_EXIT"}, True),
    ({"decision_kind": "DRAIN"}, False),
    ({"signal_bar_end": None}, False),
    ({"signal_bar_end": "2026-09-10T14:00:00"}, False),
    ({"signal_bar_end": "2026-09-10T14:01:00Z"}, False),
    ({"before_submission": "2026-09-10T13:59:59Z"}, False),
    ({"response_received": "2026-09-10T14:05:00Z"}, False),
    ({"response_received": "2026-09-10T14:07:00Z"}, False),
    ({"response_received": "2026-09-10T14:00:30Z"}, False),
])
def test_next_bar_requires_entire_closed_interval(changes, verified):
    evidence = interval(signal_bar_end="2026-09-10T14:00:00Z", decision_kind="SIGNAL",
                        response_received="2026-09-10T14:04:59.999999Z")
    evidence.update(changes)
    result = assess_next_bar_timing([evidence])
    assert result["next_bar_timing_verified"] is verified
    assert bool(result["timing_issues"]) is not verified


@pytest.mark.parametrize("evidence", [[], None, [{}], [None], ["bad"]])
def test_missing_signal_evidence_is_not_timing_proof(evidence):
    assert not assess_next_bar_timing(evidence)["next_bar_timing_verified"]


def bars():
    return [dict(symbol="SPY", timestamp_utc=f"2026-09-10T14:{minute}:00Z", volume=200)
            for minute in ("00", "05")]


def check(intervals=None, market=None):
    return assess_intervals([interval()] if intervals is None else intervals,
                            bars() if market is None else market,
                            participation="0.01", observed_at="2026-09-10T14:10:00Z")


def test_unknown_exact_time_can_pass_when_every_possible_bar_has_capacity():
    with localcontext() as context:
        context.prec = 2
        result = check()
    assert result["interval_volume_verified"]
    assert result["possible_bar_count"] == 2
    assert not result["exact_execution_time_verified"]
    assert not result["full_execution_parity_verified"]


def test_high_volume_in_one_bar_does_not_hide_another_low_volume_bar():
    market = bars()
    market[0]["volume"] = 199
    market[1]["volume"] = 100000
    assert check(market=market)["issues"] == ["WORST_CASE_VOLUME_LIMIT_EXCEEDED"]


def test_multiple_orders_share_the_same_worst_case_volume_budget():
    assert "WORST_CASE_VOLUME_LIMIT_EXCEEDED" in check(
        [interval(), interval(order_id="o2")],
    )["issues"]


def test_boundary_receipt_does_not_exclude_the_next_bar():
    result = check([interval(response_received="2026-09-10T14:05:00Z")], bars()[:1])
    assert result["issues"] == ["INTERVAL_BAR_COVERAGE_MISSING"]


@pytest.mark.parametrize("change", [
    dict(quantity=True), dict(quantity=0), dict(before_submission="2026-09-10T14:08:00Z"),
    dict(response_received="2026-09-10T14:11:00Z"), dict(before_submission="2026-09-10T14:00:00"),
])
def test_invalid_interval_is_rejected(change):
    with pytest.raises(ObservationModelError):
        check([interval(**change)])


def test_missing_duplicate_and_future_bars_cannot_certify_coverage():
    assert not check(market=[])["interval_volume_verified"]
    for market in (bars() + bars(), [dict(bars()[0], timestamp_utc="2026-09-10T14:10:00Z")]):
        with pytest.raises(ObservationModelError):
            check(market=market)


@pytest.mark.parametrize("invalid", [None, {}, [None], [{}]])
def test_bad_shape_uses_a_closed_error(invalid):
    with pytest.raises(ObservationModelError):
        check(intervals=invalid if invalid is not None else {})


def test_interval_consumer_binds_model_inputs_without_replacing_cost_authorization():
    assessment = ExecutionCostAssessment("account", "strategy", "runtime", ("start", "end"),
                                         "cost", "{}", (), ("missing",),
                                         json.dumps([interval()]))
    first = assessment.assess_interval_volume(bars(), participation="0.01",
                                              observed_at="2026-09-10T14:10:00Z")
    assert first["interval_volume_verified"]
    assert first["cost_digest"] == "cost"
    assert first["execution_identity"] == "strategy"
    assert not first["market_source_authentication_verified"]
    second = assessment.assess_interval_volume(bars(), participation="0.005",
                                               observed_at="2026-09-10T14:10:00Z")
    assert not second["interval_volume_verified"]
    assert second["interval_digest"] != first["interval_digest"]
    assert assessment.digest == "cost"
