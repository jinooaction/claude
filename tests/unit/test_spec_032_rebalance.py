"""Spec 032 slice 1 — cross-sectional rebalancing planner unit tests.

Covers SC-01..06, SC-09 (determinism), SC-11 (config validation).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.strategy.rebalance import (
    PlannedOrder,
    rebalance_plan,
    select_symbols,
    target_weights,
)

_D0 = date(2024, 1, 1)


def _series(values: list[float]) -> dict[date, Decimal]:
    return {_D0 + timedelta(days=i): Decimal(str(v)) for i, v in enumerate(values)}


# --------------------------------------------------------------- select_symbols


def test_select_top_n_excludes_sentinel():
    ranked = [
        ("AAA", Decimal("2.0")),
        ("BBB", Decimal("1.0")),
        ("CCC", Decimal("0.0")),
        ("DDD", Decimal("-Inf")),  # data-poor sentinel
    ]
    assert select_symbols(ranked, top_n=2) == ["AAA", "BBB"]
    # top_n larger than eligible count clamps; DDD (sentinel) never selected.
    assert select_symbols(ranked, top_n=10) == ["AAA", "BBB", "CCC"]


def test_select_top_pct():
    ranked = [(f"S{i}", Decimal(str(10 - i))) for i in range(10)]
    # 30% of 10 eligible = ceil(3) = 3.
    assert select_symbols(ranked, top_pct=30.0) == ["S0", "S1", "S2"]


def test_select_requires_exactly_one_cutoff():
    ranked = [("A", Decimal("1")), ("B", Decimal("0"))]
    with pytest.raises(ValueError):
        select_symbols(ranked, top_n=1, top_pct=50.0)
    with pytest.raises(ValueError):
        select_symbols(ranked, top_n=None, top_pct=None)


def test_select_empty_when_all_sentinel():
    ranked = [("A", Decimal("-Inf")), ("B", Decimal("-Inf"))]
    assert select_symbols(ranked, top_n=2) == []


# --------------------------------------------------------------- target_weights


def test_equal_weights_sum_to_one_over_exactly_top_n():
    ranked = [("A", Decimal("3")), ("B", Decimal("2")), ("C", Decimal("1"))]
    w = target_weights(ranked_scores=ranked, closes_by_symbol={}, weight_scheme="equal", top_n=2)
    assert set(w) == {"A", "B"}  # SC-01: exactly the top N
    assert sum(w.values()) == Decimal("1.000000")
    assert w["A"] == w["B"]


def test_score_proportional_is_monotone_in_score():
    ranked = [("A", Decimal("2")), ("B", Decimal("1")), ("C", Decimal("0"))]
    w = target_weights(
        ranked_scores=ranked,
        closes_by_symbol={},
        weight_scheme="score_proportional",
        top_n=3,
    )
    assert sum(w.values()) == Decimal("1.000000")
    assert w["A"] > w["B"] > w["C"]  # SC-02: higher score -> higher weight


def test_inverse_vol_favours_low_volatility():
    # CALM rises ~steadily (low vol); WILD oscillates hard (high vol).
    calm = _series([100 + i * 0.1 for i in range(40)])
    wild = _series([100 + (8 if i % 2 == 0 else -8) for i in range(40)])
    ranked = [("CALM", Decimal("1")), ("WILD", Decimal("1"))]
    w = target_weights(
        ranked_scores=ranked,
        closes_by_symbol={"CALM": calm, "WILD": wild},
        weight_scheme="inverse_vol",
        top_n=2,
        lookback_bars=30,
    )
    assert sum(w.values()) == Decimal("1.000000")
    assert w["CALM"] > w["WILD"]  # SC-03: lower vol -> higher weight


@pytest.mark.parametrize("scheme", ["min_variance", "max_sharpe", "erc"])
def test_optimizer_schemes_yield_valid_vector(scheme):
    # 40 sessions of data for three names -> optimizers have enough history.
    a = _series([100 + i * 0.2 for i in range(40)])
    b = _series([100 + i * 0.1 + (1 if i % 3 == 0 else 0) for i in range(40)])
    c = _series([100 - i * 0.05 + (2 if i % 2 == 0 else -2) for i in range(40)])
    ranked = [("A", Decimal("3")), ("B", Decimal("2")), ("C", Decimal("1"))]
    w = target_weights(
        ranked_scores=ranked,
        closes_by_symbol={"A": a, "B": b, "C": c},
        weight_scheme=scheme,
        top_n=3,
        lookback_bars=30,
    )
    assert set(w) == {"A", "B", "C"}
    assert sum(w.values()) == Decimal("1.000000")
    assert all(v >= 0 for v in w.values())  # long-only


def test_optimizer_falls_back_on_insufficient_data():
    # Only 5 closes -> covariance returns None -> fallback chain still produces
    # a valid sum-1 vector (SC-04), never raises.
    a = _series([100, 101, 102, 103, 104])
    b = _series([100, 99, 101, 100, 102])
    ranked = [("A", Decimal("2")), ("B", Decimal("1"))]
    for scheme in ("min_variance", "max_sharpe", "erc", "inverse_vol"):
        w = target_weights(
            ranked_scores=ranked,
            closes_by_symbol={"A": a, "B": b},
            weight_scheme=scheme,
            top_n=2,
            lookback_bars=30,
        )
        assert sum(w.values()) == Decimal("1.000000")
        assert set(w) == {"A", "B"}


def test_target_weights_empty_when_no_eligible():
    ranked = [("A", Decimal("-Inf"))]
    assert (
        target_weights(ranked_scores=ranked, closes_by_symbol={}, weight_scheme="equal", top_n=1)
        == {}
    )


def test_unknown_weight_scheme_raises():
    ranked = [("A", Decimal("1")), ("B", Decimal("0"))]
    with pytest.raises(ValueError):
        target_weights(
            ranked_scores=ranked,
            closes_by_symbol={},
            weight_scheme="bogus",
            top_n=2,
        )


def test_target_weights_deterministic():
    ranked = [("A", Decimal("3")), ("B", Decimal("2")), ("C", Decimal("1"))]
    kw = dict(
        ranked_scores=ranked,
        closes_by_symbol={},
        weight_scheme="score_proportional",
        top_n=3,
    )
    assert target_weights(**kw) == target_weights(**kw)  # SC-09


# --------------------------------------------------------------- rebalance_plan


def test_rebalance_buys_targets_and_exits_dropouts():
    # Target AAA/BBB at 50% each; currently holding CCC which dropped out.
    orders = rebalance_plan(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={"CCC": 10},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100"), "CCC": Decimal("50")},
        capital_usd=Decimal("10000"),
        invested_fraction=Decimal("1"),
    )
    assert PlannedOrder("AAA", "BUY", 50) in orders
    assert PlannedOrder("BBB", "BUY", 50) in orders
    # SC-05: a dropped-out holding is fully sold (the missing sell dimension).
    assert PlannedOrder("CCC", "SELL", 10) in orders


def test_rebalance_trims_overweight_and_adds_underweight():
    # Hold 80 AAA (overweight), target 50 -> SELL 30. No BBB -> BUY 50.
    orders = rebalance_plan(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={"AAA": 80},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100")},
        capital_usd=Decimal("10000"),
        invested_fraction=Decimal("1"),
    )
    assert PlannedOrder("AAA", "SELL", 30) in orders
    assert PlannedOrder("BBB", "BUY", 50) in orders


def test_no_trade_band_suppresses_small_moves():
    # Target 50 vs current 49 share: weight move = 1% (49->50% of capital).
    # Threshold 5% suppresses it; threshold 0% lets the 1-share trade through.
    base = dict(
        target_weights={"AAA": Decimal("0.5")},
        holdings={"AAA": 49},
        prices={"AAA": Decimal("100")},
        capital_usd=Decimal("10000"),
        invested_fraction=Decimal("1"),
    )
    assert rebalance_plan(**base, rebalance_threshold_pct=Decimal("5")) == []  # SC-06
    assert rebalance_plan(**base, rebalance_threshold_pct=Decimal("0")) == [
        PlannedOrder("AAA", "BUY", 1)
    ]


def test_min_notional_drops_odd_lots():
    orders = rebalance_plan(
        target_weights={"AAA": Decimal("0.5")},
        holdings={"AAA": 49},
        prices={"AAA": Decimal("100")},
        capital_usd=Decimal("10000"),
        invested_fraction=Decimal("1"),
        min_notional_usd=Decimal("500"),  # the 1-share, $100 trade is below this
    )
    assert orders == []


def test_exit_ignores_no_trade_band():
    # A full exit must fire even under a wide band (we always cut a dropout).
    orders = rebalance_plan(
        target_weights={},  # nothing is a target anymore
        holdings={"CCC": 3},
        prices={"CCC": Decimal("10")},
        capital_usd=Decimal("10000"),
        rebalance_threshold_pct=Decimal("90"),
        min_notional_usd=Decimal("1000"),
    )
    assert orders == [PlannedOrder("CCC", "SELL", 3)]


def test_invested_fraction_keeps_cash_buffer():
    # 95% invested -> target dollar = 0.95 * 10000 = 9500 -> 95 shares at $100.
    orders = rebalance_plan(
        target_weights={"AAA": Decimal("1.0")},
        holdings={},
        prices={"AAA": Decimal("100")},
        capital_usd=Decimal("10000"),
        invested_fraction=Decimal("0.95"),
    )
    assert orders == [PlannedOrder("AAA", "BUY", 95)]


def test_hold_replace_lets_winners_run_and_only_buys_new_entrants():
    # Held: AAA (grew, in target), CCC (dropped out). Target: AAA, BBB(new).
    # hold_replace must: NOT trim AAA (let it run), SELL CCC (exit), BUY BBB (new).
    orders = rebalance_plan(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={"AAA": 100, "CCC": 10},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100"), "CCC": Decimal("50")},
        capital_usd=Decimal("10000"),
        invested_fraction=Decimal("1"),
        mode="hold_replace",
    )
    syms = {(o.symbol, o.side) for o in orders}
    assert ("AAA", "SELL") not in syms and ("AAA", "BUY") not in syms  # winner runs
    assert ("CCC", "SELL") in syms  # dropout exited
    assert ("BBB", "BUY") in syms  # new entrant bought
    # default mode WOULD trim AAA (100 held vs 50 target) — contrast:
    default = rebalance_plan(
        target_weights={"AAA": Decimal("0.5"), "BBB": Decimal("0.5")},
        holdings={"AAA": 100, "CCC": 10},
        prices={"AAA": Decimal("100"), "BBB": Decimal("100"), "CCC": Decimal("50")},
        capital_usd=Decimal("10000"),
        invested_fraction=Decimal("1"),
    )
    assert PlannedOrder("AAA", "SELL", 50) in default  # default trims the winner


def test_rebalance_plan_is_sorted_and_deterministic():
    kw = dict(
        target_weights={"ZZZ": Decimal("0.5"), "AAA": Decimal("0.5")},
        holdings={"MMM": 5},
        prices={
            "ZZZ": Decimal("100"),
            "AAA": Decimal("100"),
            "MMM": Decimal("100"),
        },
        capital_usd=Decimal("10000"),
        invested_fraction=Decimal("1"),
    )
    orders = rebalance_plan(**kw)
    assert orders == rebalance_plan(**kw)
    assert [o.symbol for o in orders] == sorted(o.symbol for o in orders)


def test_nearest_lot_rounding_only_rounds_up_when_it_reduces_target_error():
    base = dict(
        target_weights={"SPYM": Decimal("0.333334"), "GLDM": Decimal("0.166666")},
        holdings={},
        prices={"SPYM": Decimal("86.89"), "GLDM": Decimal("80.46")},
        capital_usd=Decimal("293"),
        invested_fraction=Decimal("0.99"),
        mode="hold_replace",
        min_notional_usd=Decimal("50"),
    )

    floor = rebalance_plan(**base, lot_rounding="floor")
    assert [(order.symbol, order.side, order.qty) for order in floor] == [("SPYM", "BUY", 1)]
    nearest = rebalance_plan(**base, lot_rounding="nearest")
    assert [(order.symbol, order.side, order.qty) for order in nearest] == [
        ("GLDM", "BUY", 1),
        ("SPYM", "BUY", 1),
    ]


# --------------------------------------------------------------- config (SC-11)


def _cfg(**overrides):
    base = dict(
        id="port-1",
        universe=("aaa", "bbb", "ccc"),
        weights={"momentum": Decimal("1")},
        top_n=2,
    )
    base.update(overrides)
    return PortfolioRebalanceConfig(**base)


def test_config_normalizes_universe_uppercase():
    cfg = _cfg()
    assert cfg.universe == ("AAA", "BBB", "CCC")


def test_config_requires_exactly_one_cutoff():
    with pytest.raises(ValidationError):
        _cfg(top_n=2, top_pct=10.0)
    with pytest.raises(ValidationError):
        _cfg(top_n=None, top_pct=None)


def test_config_rejects_unknown_factor():
    with pytest.raises(ValidationError):
        _cfg(weights={"bogus": Decimal("1")})


def test_config_rejects_all_zero_weights():
    with pytest.raises(ValidationError):
        _cfg(weights={"momentum": Decimal("0")})


def test_config_rejects_tiny_universe():
    with pytest.raises(ValidationError):
        _cfg(universe=("AAA",))


def test_config_invested_fraction_bounds():
    with pytest.raises(ValidationError):
        _cfg(invested_fraction=Decimal("0"))
    with pytest.raises(ValidationError):
        _cfg(invested_fraction=Decimal("1.5"))
    assert _cfg(invested_fraction=Decimal("0.5")).invested_fraction == Decimal("0.5")


def test_config_rejects_unknown_weight_scheme():
    with pytest.raises(ValidationError):
        _cfg(weight_scheme="bogus")


def test_config_accepts_all_known_weight_schemes():
    for scheme in (
        "equal",
        "score_proportional",
        "inverse_vol",
        "min_variance",
        "max_sharpe",
        "erc",
    ):
        assert _cfg(weight_scheme=scheme).weight_scheme == scheme
