from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from auto_invest.config.caps import SizingCaps
from auto_invest.portfolio.fundability import (
    assess_fundability,
    validate_fundability_evidence,
)
from auto_invest.strategy.rebalance import rebalance_plan


def _caps(*, per_trade: str = "50", per_symbol: str = "60") -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal(per_trade),
        per_symbol_pct=Decimal(per_symbol),
        global_exposure_pct=Decimal("100"),
        canary_capital_pct=Decimal("10"),
        canary_min_duration_days=14,
        canary_acceptance_drawdown_pct=Decimal("10"),
    )


def test_exact_whole_share_preview_is_fundable_and_self_verifying() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        order_prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        planned_orders=[("AAA", "BUY", 4), ("BBB", "BUY", 5)],
        capital_usd=Decimal("1000"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(),
    )

    evidence = result.as_dict()
    assert result.fundable is True
    assert result.projected_quantities == {"AAA": 4, "BBB": 5}
    assert result.l1_weight_error == Decimal("0.100")
    assert validate_fundability_evidence(
        evidence, expected_capital_usd=Decimal("1000")
    )


def test_small_capital_that_cannot_express_three_legs_fails_weight_error() -> None:
    result = assess_fundability(
        target_weights={
            "AAA": Decimal("0.333333"),
            "BBB": Decimal("0.333333"),
            "CCC": Decimal("0.333334"),
        },
        holdings={},
        prices={symbol: Decimal("60") for symbol in ("AAA", "BBB", "CCC")},
        order_prices={symbol: Decimal("60") for symbol in ("AAA", "BBB")},
        planned_orders=[("AAA", "BUY", 1), ("BBB", "BUY", 1)],
        capital_usd=Decimal("145"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(per_trade="50", per_symbol="60"),
    )

    assert result.fundable is False
    assert "l1_weight_error" in result.reasons
    assert "max_leg_weight_error" in result.reasons


def test_preregistered_two_active_proxies_fit_current_research_capital() -> None:
    prices = {"SCHX": Decimal("30.21"), "IAUM": Decimal("45.79")}
    targets = {"SCHX": Decimal("0.333333"), "IAUM": Decimal("0.333333")}
    planned = rebalance_plan(
        target_weights=targets,
        holdings={},
        prices=prices,
        capital_usd=Decimal("145"),
        invested_fraction=Decimal("0.99"),
        min_notional_usd=Decimal("20"),
        mode="hold_replace",
        lot_rounding="nearest",
    )
    result = assess_fundability(
        target_weights=targets,
        holdings={},
        prices=prices,
        order_prices=prices,
        planned_orders=[
            (order.symbol, order.side, order.qty) for order in planned
        ],
        capital_usd=Decimal("145"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(per_trade="50", per_symbol="60"),
    )

    assert [(order.symbol, order.qty) for order in planned] == [
        ("IAUM", 1),
        ("SCHX", 2),
    ]
    assert result.fundable is True
    assert result.max_leg_weight_error <= Decimal("0.15")


def test_below_one_share_target_does_not_veto_bounded_nonempty_portfolio() -> None:
    result = assess_fundability(
        target_weights={
            "SCHX": Decimal("0.333334"),
            "IAUM": Decimal("0.083333"),
        },
        holdings={},
        prices={"SCHX": Decimal("30.09"), "IAUM": Decimal("43.28")},
        order_prices={"SCHX": Decimal("30.09")},
        planned_orders=[("SCHX", "BUY", 2)],
        capital_usd=Decimal("142"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(per_trade="50", per_symbol="60"),
    )

    assert result.active_target_count == 2
    assert result.funded_target_count == 1
    assert result.funded_target_ratio == Decimal("0.5")
    assert result.whole_share_eligible_target_count == 1
    assert result.funded_whole_share_target_count == 1
    assert result.funded_whole_share_target_ratio == Decimal("1")
    assert result.whole_share_ineligible_targets == {
        "IAUM": {
            "target_notional_usd": Decimal("11.71495314"),
            "one_share_price_usd": Decimal("43.28"),
        }
    }
    assert result.l1_weight_error <= Decimal("0.25")
    assert result.max_leg_weight_error <= Decimal("0.15")
    assert result.fundable is True
    assert validate_fundability_evidence(
        result.as_dict(), expected_capital_usd=Decimal("142")
    )


def test_all_below_one_share_targets_remain_unfundable() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.1"), "BBB": Decimal("0.1")},
        holdings={},
        prices={"AAA": Decimal("50"), "BBB": Decimal("50")},
        order_prices={},
        planned_orders=[],
        capital_usd=Decimal("100"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(),
    )

    assert result.whole_share_eligible_target_count == 0
    assert result.fundable is False
    assert "whole_share_eligible_targets_present" in result.reasons


def test_unfunded_whole_share_eligible_target_remains_unfundable() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.1")},
        holdings={},
        prices={"AAA": Decimal("5")},
        order_prices={},
        planned_orders=[],
        capital_usd=Decimal("100"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(),
    )

    assert result.whole_share_eligible_target_count == 1
    assert result.funded_whole_share_target_ratio == Decimal("0")
    assert result.fundable is False
    assert "funded_whole_share_target_ratio" in result.reasons


def test_below_one_share_target_still_counts_toward_weight_error() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.2")},
        holdings={},
        prices={"AAA": Decimal("30")},
        order_prices={},
        planned_orders=[],
        capital_usd=Decimal("100"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(),
    )

    assert result.whole_share_eligible_target_count == 0
    assert result.max_leg_weight_error == Decimal("0.198")
    assert "max_leg_weight_error" in result.reasons


def test_legacy_fundability_schema_cannot_inherit_new_denominator_semantics() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.5")},
        holdings={},
        prices={"AAA": Decimal("10")},
        order_prices={"AAA": Decimal("10")},
        planned_orders=[("AAA", "BUY", 5)],
        capital_usd=Decimal("100"),
        invested_fraction=Decimal("1"),
        caps=_caps(),
    )
    legacy = result.as_dict()
    legacy["schema_version"] = "1.0"

    assert validate_fundability_evidence(legacy) is False


def test_zero_order_minimum_notional_path_fails_funded_targets() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={},
        prices={"AAA": Decimal("40"), "BBB": Decimal("40")},
        order_prices={},
        planned_orders=[],
        capital_usd=Decimal("100"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(),
    )

    assert result.fundable is False
    assert "funded_target_ratio" in result.reasons


def test_missing_quote_and_per_trade_cap_below_one_share_fail_closed() -> None:
    missing_quote = assess_fundability(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={},
        prices={"AAA": Decimal("100")},
        order_prices={"AAA": Decimal("100")},
        planned_orders=[("AAA", "BUY", 5)],
        capital_usd=Decimal("1000"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(),
    )
    cap_blocked = assess_fundability(
        target_weights={"AAA": Decimal("1")},
        holdings={},
        prices={"AAA": Decimal("150")},
        order_prices={"AAA": Decimal("150")},
        planned_orders=[("AAA", "BUY", 6)],
        capital_usd=Decimal("1000"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(per_trade="10", per_symbol="60"),
    )

    assert "quote_coverage" in missing_quote.reasons
    assert "exposure_caps" in cap_blocked.reasons


def test_unpriced_existing_holding_cannot_be_ignored_by_global_cap() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("1")},
        holdings={"UNPRICED": 10},
        prices={"AAA": Decimal("100")},
        order_prices={"AAA": Decimal("100")},
        planned_orders=[("AAA", "BUY", 9)],
        capital_usd=Decimal("1000"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(per_trade="100", per_symbol="100"),
    )

    assert result.fundable is False
    assert "exposure_quote_coverage" in result.reasons


def test_existing_holding_above_symbol_cap_fails_even_without_a_new_buy() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.7")},
        holdings={"AAA": 7},
        prices={"AAA": Decimal("100")},
        order_prices={},
        planned_orders=[],
        capital_usd=Decimal("1000"),
        invested_fraction=Decimal("1"),
        caps=_caps(per_trade="50", per_symbol="60"),
    )

    assert result.fundable is False
    assert "exposure_caps" in result.reasons


def test_preview_applies_sells_before_buys_like_the_live_rebalancer() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.4")},
        holdings={"AAA": 8},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        order_prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        planned_orders=[("BBB", "BUY", 4), ("AAA", "SELL", 3)],
        capital_usd=Decimal("1000"),
        invested_fraction=Decimal("1"),
        caps=_caps(per_trade="50", per_symbol="60"),
    )

    assert result.fundable is True
    assert result.projected_quantities == {"AAA": 5, "BBB": 4}


def test_serialized_preview_is_recomputed_and_rejects_tampering_or_wrong_capital() -> None:
    result = assess_fundability(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        order_prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        planned_orders=[("AAA", "BUY", 4), ("BBB", "BUY", 5)],
        capital_usd=Decimal("1000"),
        invested_fraction=Decimal("0.99"),
        caps=_caps(),
    )
    evidence = result.as_dict()
    tampered = deepcopy(evidence)
    tampered["projected_weights"]["AAA"] = "0.50"

    assert validate_fundability_evidence(tampered) is False
    assert (
        validate_fundability_evidence(evidence, expected_capital_usd=Decimal("999"))
        is False
    )
    assert validate_fundability_evidence([]) is False
