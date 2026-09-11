from decimal import localcontext

import pytest

from auto_invest.execution.intraday_observation_models import assess_next_bar_costs

MODEL = dict(spread_bps_per_side=1, slippage_bps_per_side=5, commission_bps_per_side=1)


def evidence(**changes):
    return dict(dict(order_id="order", symbol="SPY", quantity=2, side="BUY",
                     signal_bar_end="2026-09-10T14:00:00Z", decision_kind="SIGNAL",
                     before_submission="2026-09-10T14:01:00Z",
                     response_received="2026-09-10T14:04:00Z",
                     average_fill_price="100.06", reported_fees="0.02"), **changes)


def bars():
    return [dict(symbol="SPY", timestamp_utc="2026-09-10T14:00:00Z", open=100)]


@pytest.mark.parametrize("side,price,verified", [
    ("BUY", "100.06", True), ("BUY", "100.060000000001", False),
    ("BUY", "99.94", True), ("SELL", "99.94", True),
    ("SELL", "99.939999999999", False), ("SELL", "100.06", True),
])
def test_reference_price_direction_and_exact_boundary(side, price, verified):
    with localcontext() as context:
        context.prec = 2
        result = assess_next_bar_costs(
            [evidence(side=side, average_fill_price=price)], bars(), MODEL,
        )
    assert result["next_bar_price_bound_verified"] is verified
    assert result["next_bar_fee_bound_verified"]


def test_fee_limit_uses_reference_not_actual_execution_gross():
    # 0.02001 is below the former 200.12 * 1bp limit but exceeds research's 200 * 1bp.
    result = assess_next_bar_costs([evidence(reported_fees="0.02001")], bars(), MODEL)
    assert result["next_bar_price_bound_verified"]
    assert not result["next_bar_fee_bound_verified"]
    assert result["cost_issues"] == ["NEXT_BAR_FEE_BOUND_EXCEEDED"]


@pytest.mark.parametrize("changes", [
    dict(response_received="2026-09-10T14:05:00Z"), dict(signal_bar_end=None),
    dict(average_fill_price="NaN"), dict(reported_fees=None), dict(reported_fees="-1"),
    dict(quantity=True), dict(side="unknown"),
])
def test_missing_or_invalid_evidence_never_establishes_cost_bound(changes):
    result = assess_next_bar_costs([evidence(**changes)], bars(), MODEL)
    assert not result["next_bar_price_bound_verified"]
    assert not result["next_bar_fee_bound_verified"]


@pytest.mark.parametrize("source", [[], bars() * 2, [dict(symbol="SPY", timestamp_utc=
                         "2026-09-10T14:00:00Z", open="NaN")]])
def test_missing_duplicate_or_invalid_reference_is_unverified(source):
    assert not assess_next_bar_costs([evidence()], source, MODEL)["next_bar_price_bound_verified"]


@pytest.mark.parametrize("model", [None, {}, dict(MODEL, spread_bps_per_side=-1),
                                    dict(MODEL, slippage_bps_per_side=10000)])
def test_cost_model_is_required_and_bounded(model):
    assert not assess_next_bar_costs([evidence()], bars(), model)["next_bar_fee_bound_verified"]
