"""Spec 007 T022 — property-based fuzz of `auto_invest.risk.gates`.

Covers:
  - Smoke: zero counterexamples on stock K1 code (baseline).
  - SC-C02: an off-by-one injection into ``per_trade_cap_gate`` is
    detected within 10k iterations.
  - Counterexample shape matches data-model.md `FuzzCounterexample`.
"""

from __future__ import annotations

from decimal import Decimal

from auto_invest.canary import fuzz as fuzz_module
from auto_invest.canary.data_model import FuzzCounterexample
from auto_invest.canary.fuzz import (
    DEFAULT_ITERATIONS,
    run_fuzz_pass,
)


def test_clean_k1_passes_with_no_counterexamples() -> None:
    """A clean ``risk.gates`` produces zero counterexamples on a default seed."""
    result = run_fuzz_pass(iterations=500, database_seed=42)
    assert result.counterexamples == []
    assert result.iterations == 500
    assert result.database_seed == 42


def test_off_by_one_in_per_trade_is_caught_under_10k_iterations(
    monkeypatch,
) -> None:
    """SC-C02 — replace ``per_trade_cap_gate`` with an off-by-one variant.

    The bug: change ``notional > cap_value`` to ``notional > cap_value + 1``
    so an over-cap order is wrongly allowed by 1 USD. Property fuzz
    MUST catch this within the default 10k iterations.
    """
    def buggy_per_trade_cap_gate(request, *, caps, total_capital_usd, quote_price_usd):
        # Off-by-one: under-tight cap. Allow slightly-over-cap orders.
        from auto_invest.risk.gates import GateDecision

        price = (
            request.limit_price_usd
            if request.limit_price_usd is not None
            else quote_price_usd
        )
        notional = price * Decimal(request.qty)
        cap_value = total_capital_usd * caps.per_trade_pct / Decimal(100)
        if notional > cap_value + Decimal(1):  # BUG: should be > cap_value
            return GateDecision(
                allow=False,
                gate="per_trade_cap_gate",
                reason=f"notional ${notional} exceeds per-trade cap ${cap_value}",
            )
        return GateDecision(allow=True, gate="per_trade_cap_gate")

    monkeypatch.setattr(
        fuzz_module,
        "per_trade_cap_gate",
        buggy_per_trade_cap_gate,
    )

    # Use a moderate iteration budget to keep the test fast while still
    # being statistically likely to hit a violation. The default 10k
    # iterations is the *budget*; in practice a single off-by-one bug
    # surfaces within a few hundred uniformly-random examples.
    result = run_fuzz_pass(iterations=2000, database_seed=42)
    assert len(result.counterexamples) > 0, (
        "SC-C02 regression: property fuzz failed to catch a deliberate"
        " off-by-one in per_trade_cap_gate within 2000 iterations."
    )
    ce = result.counterexamples[0]
    assert ce.assertion_failed.startswith("per_trade_cap_gate")
    assert ce.gate_decision == {"label": "per_trade", "allowed": True}


def test_counterexample_shape_matches_data_model(monkeypatch) -> None:
    """A counterexample is exactly the shape declared in data-model.md."""
    from auto_invest.risk.gates import GateDecision

    def always_allow_over(request, *, caps, total_capital_usd, quote_price_usd):
        return GateDecision(allow=True, gate="per_trade_cap_gate")

    monkeypatch.setattr(
        fuzz_module,
        "per_trade_cap_gate",
        always_allow_over,
    )

    result = run_fuzz_pass(iterations=50, database_seed=1)
    assert len(result.counterexamples) > 0
    ce = result.counterexamples[0]
    assert isinstance(ce, FuzzCounterexample)
    assert isinstance(ce.shrunk_input, dict)
    assert "gate" in ce.shrunk_input
    assert "qty" in ce.shrunk_input
    assert "per_trade_pct" in ce.shrunk_input
    assert isinstance(ce.assertion_failed, str)


def test_default_iterations_matches_fr_c04_minimum() -> None:
    """FR-C04: minimum 10000 fuzz iterations."""
    assert DEFAULT_ITERATIONS >= 10_000
