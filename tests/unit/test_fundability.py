from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from auto_invest.config.caps import SizingCaps
from auto_invest.portfolio.fundability import (
    assess_fundability,
    validate_fundability_evidence,
)


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
