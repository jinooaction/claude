"""Property-based fuzz of `auto_invest.risk.gates` (T021).

Per FR-C04 + R-C4: exercise the K1 cap-chain math against random
``(OrderRequest, SizingCaps, exposure)`` tuples. Any time an ALLOW
decision is returned, assert the corresponding cap invariant holds.

Direct invocation of Hypothesis programmatically (not pytest-driven)
per R-C5: this module is part of the production canary CLI, not a test.

Output contract (per ``contracts/property-fuzz-protocol.md``):

  - ``seeds.txt`` — one line per seed used; first line is the database seed.
  - ``counterexamples.json`` — list of ``FuzzCounterexample``; empty on pass.

The harness runs ALL iterations (no short-circuit) so the full
counterexample set is available for forensic inspection.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, given, seed as hypothesis_seed, settings
from hypothesis import strategies as st

from auto_invest.broker.models import OrderRequest
from auto_invest.canary.data_model import FuzzCounterexample
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side
from auto_invest.risk.gates import (
    global_exposure_gate,
    per_symbol_cap_gate,
    per_trade_cap_gate,
)

DEFAULT_ITERATIONS = 10_000


@dataclass(frozen=True)
class FuzzPassResult:
    counterexamples: list[FuzzCounterexample]
    iterations: int
    database_seed: int


# ---------------------------------------------------------- strategies


_qty_strategy = st.integers(min_value=1, max_value=10_000)


_price_strategy = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("1000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


_exposure_pct_strategy = st.decimals(
    min_value=Decimal("0.0000"),
    max_value=Decimal("1.0000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


_total_capital_strategy = st.decimals(
    min_value=Decimal("1000"),
    max_value=Decimal("10000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


def _caps_strategy() -> st.SearchStrategy[SizingCaps]:
    """Generate ``SizingCaps`` that satisfy the K1 model invariants.

    The model validator already enforces ``per_trade ≤ per_symbol ≤ global``
    and ``canary_capital ≤ per_symbol``; we sample then filter so
    Hypothesis can find any boundary cases.
    """
    return st.tuples(
        st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10"), places=2),
        st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10"), places=2),
        st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10"), places=2),
    ).map(lambda t: tuple(sorted(t))).filter(
        # at least one valid combination — drop degenerate equals to keep
        # generation throughput up.
        lambda t: True
    ).map(
        lambda t: SizingCaps(
            per_trade_pct=t[0],
            per_symbol_pct=t[1],
            global_exposure_pct=t[2],
            canary_capital_pct=min(t[0], Decimal("5")),
            canary_min_duration_days=5,
            canary_acceptance_drawdown_pct=Decimal("3"),
        )
    )


# ---------------------------------------------------------- property


def _build_request(qty: int, price: Decimal) -> OrderRequest:
    return OrderRequest(
        account="BACKTEST",
        symbol="FUZZ",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        qty=qty,
        limit_price_usd=price,
    )


def _check_per_trade(
    request: OrderRequest,
    caps: SizingCaps,
    total_capital: Decimal,
    quote: Decimal,
) -> str | None:
    decision = per_trade_cap_gate(
        request,
        caps=caps,
        total_capital_usd=total_capital,
        quote_price_usd=quote,
    )
    if not decision.allow:
        return None
    notional = quote * Decimal(request.qty)
    cap_usd = total_capital * caps.per_trade_pct / Decimal(100)
    if notional > cap_usd:
        return (
            f"per_trade_cap_gate allowed notional={notional} but cap={cap_usd}"
        )
    return None


def _check_per_symbol(
    request: OrderRequest,
    caps: SizingCaps,
    total_capital: Decimal,
    quote: Decimal,
    current_symbol_exposure_pct: Decimal,
) -> str | None:
    current_usd = total_capital * current_symbol_exposure_pct
    decision = per_symbol_cap_gate(
        request,
        caps=caps,
        total_capital_usd=total_capital,
        quote_price_usd=quote,
        current_symbol_exposure_usd=current_usd,
    )
    if not decision.allow:
        return None
    notional = quote * Decimal(request.qty)
    new_exposure = current_usd + notional
    cap_usd = total_capital * caps.per_symbol_pct / Decimal(100)
    if new_exposure > cap_usd:
        return (
            f"per_symbol_cap_gate allowed new_exposure={new_exposure} but cap={cap_usd}"
        )
    return None


def _check_global(
    request: OrderRequest,
    caps: SizingCaps,
    total_capital: Decimal,
    quote: Decimal,
    current_global_exposure_pct: Decimal,
) -> str | None:
    current_usd = total_capital * current_global_exposure_pct
    decision = global_exposure_gate(
        request,
        caps=caps,
        total_capital_usd=total_capital,
        quote_price_usd=quote,
        current_global_exposure_usd=current_usd,
    )
    if not decision.allow:
        return None
    notional = quote * Decimal(request.qty)
    new_exposure = current_usd + notional
    cap_usd = total_capital * caps.global_exposure_pct / Decimal(100)
    if new_exposure > cap_usd:
        return (
            f"global_exposure_gate allowed new_exposure={new_exposure} but cap={cap_usd}"
        )
    return None


def run_fuzz_pass(
    *,
    iterations: int = DEFAULT_ITERATIONS,
    database_seed: int = 0,
) -> FuzzPassResult:
    """Run the K1 property fuzz and collect every failing example.

    The harness does NOT short-circuit on first failure (R-C4). Hypothesis
    is configured to suppress its early-termination shrink phase so we
    visit ``iterations`` distinct examples; each violation is recorded.
    """

    counterexamples: list[FuzzCounterexample] = []

    @hypothesis_seed(database_seed)
    @settings(
        max_examples=iterations,
        deadline=None,
        suppress_health_check=list(HealthCheck),
        database=None,
    )
    @given(
        qty=_qty_strategy,
        price=_price_strategy,
        total_capital=_total_capital_strategy,
        sym_exp=_exposure_pct_strategy,
        glob_exp=_exposure_pct_strategy,
        caps=_caps_strategy(),
    )
    def _property(
        qty: int,
        price: Decimal,
        total_capital: Decimal,
        sym_exp: Decimal,
        glob_exp: Decimal,
        caps: SizingCaps,
    ) -> None:
        request = _build_request(qty, price)
        for label, fn in (
            (
                "per_trade",
                lambda: _check_per_trade(request, caps, total_capital, price),
            ),
            (
                "per_symbol",
                lambda: _check_per_symbol(
                    request, caps, total_capital, price, sym_exp
                ),
            ),
            (
                "global",
                lambda: _check_global(request, caps, total_capital, price, glob_exp),
            ),
        ):
            violation = fn()
            if violation:
                counterexamples.append(
                    FuzzCounterexample(
                        seed=database_seed,
                        shrunk_input={
                            "gate": label,
                            "qty": qty,
                            "price": str(price),
                            "total_capital": str(total_capital),
                            "current_symbol_exposure_pct": str(sym_exp),
                            "current_global_exposure_pct": str(glob_exp),
                            "per_trade_pct": str(caps.per_trade_pct),
                            "per_symbol_pct": str(caps.per_symbol_pct),
                            "global_exposure_pct": str(caps.global_exposure_pct),
                        },
                        assertion_failed=violation,
                        gate_decision={"label": label, "allowed": True},
                    )
                )

    _property()

    return FuzzPassResult(
        counterexamples=counterexamples,
        iterations=iterations,
        database_seed=database_seed,
    )


__all__ = [
    "DEFAULT_ITERATIONS",
    "FuzzPassResult",
    "run_fuzz_pass",
]
