from decimal import localcontext

import pytest

from auto_invest.broker.overseas import _parse_execution_snapshots
from auto_invest.execution.intraday_observation_models import assess_model_quantities


def order(**changes):
    return dict(dict(order_id="order", symbol="SPY", signal_bar_end="2026-09-10T14:00:00Z",
                     decision_kind="SIGNAL", ordered_quantity=5, filled_quantity=2,
                     reported_order_date="2026-09-10"), **changes)


def bars(volume=299):
    return [dict(symbol="SPY", timestamp_utc="2026-09-10T14:00:00Z", volume=volume)]


@pytest.mark.parametrize("volume,filled,verified", [
    (299, 2, True), (299, 1, False), (299, 3, False), (500, 5, True),
    (1000, 5, True), (99, 0, True), (100, 0, False), (0, 0, True),
])
def test_full_partial_and_zero_fills_match_integer_model(volume, filled, verified):
    with localcontext() as context:
        context.prec = 2
        result = assess_model_quantities([order(filled_quantity=filled)], bars(volume), "0.01")
    assert result["model_fill_quantity_verified"] is verified


def test_unfilled_order_cannot_be_omitted_from_comparison():
    orders = [order(), order(order_id="unfilled", filled_quantity=0)]
    assert not assess_model_quantities(orders, bars(), "0.01")["model_fill_quantity_verified"]


@pytest.mark.parametrize("day", [None, "2026-09-09"])
def test_zero_fill_cannot_use_a_different_or_unknown_order_day(day):
    result = assess_model_quantities([
        order(filled_quantity=0, reported_order_date=day),
    ], bars(0), "0.01")
    assert not result["model_fill_quantity_verified"]


@pytest.mark.parametrize("changes", [dict(ordered_quantity=None), dict(ordered_quantity=True),
                                    dict(filled_quantity=-1), dict(signal_bar_end=None),
                                    dict(decision_kind="DRAIN")])
def test_missing_or_invalid_order_evidence_is_not_a_match(changes):
    assert not assess_model_quantities([order(**changes)], bars(), "0.01")[
        "model_fill_quantity_verified"
    ]


def test_missing_or_duplicate_sources_are_not_a_match():
    for orders, source in [([], bars()), ([order(), order()], bars()),
                           ([order()], []), ([order()], bars() * 2)]:
        assert not assess_model_quantities(orders, source, "0.01")["model_fill_quantity_verified"]


def row(**changes):
    return dict(dict(odno="order", pdno="SPY", sll_buy_dvsn_cd="02", ft_ccld_qty="2",
                     nccs_qty="3", ft_ccld_unpr3="101", ft_ord_qty="5"), **changes)


def test_strict_parser_keeps_original_order_quantity():
    execution = _parse_execution_snapshots([row()], "AMEX")[0]
    assert execution.reported_order_quantity == 5 and execution.filled_qty == 2


@pytest.mark.parametrize("quantity", ["0", "-1", "1.5", "NaN", "Infinity", "1"])
def test_invalid_or_smaller_than_fill_quantity_is_refused(quantity):
    with pytest.raises(ValueError, match="EXECUTIONS_ORDER_QUANTITY_INVALID"):
        _parse_execution_snapshots([row(ft_ord_qty=quantity)], "AMEX")


def test_changed_order_quantity_is_a_snapshot_conflict():
    with pytest.raises(ValueError, match="EXECUTIONS_SNAPSHOT_CONFLICT"):
        _parse_execution_snapshots([row(), row(ft_ord_qty="6")], "AMEX")
