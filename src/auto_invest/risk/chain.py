"""Single source of truth for the gate chain (T020, SC-005).

Both `execution/order_router.py` (live) and
`execution/backtest_broker.py` (simulated) call this function so the
chain is ordered and parameterised identically.

Returns the first deny decision encountered, or an Allow decision
attributed to the chain as a whole if every gate passes.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from auto_invest.broker.models import OrderRequest
from auto_invest.config.caps import SizingCaps
from auto_invest.config.whitelist import Whitelist
from auto_invest.risk.gates import (
    GateDecision,
    global_exposure_gate,
    halt_gate,
    per_symbol_cap_gate,
    per_trade_cap_gate,
    whitelist_gate,
)


def build_gate_chain(
    *,
    whitelist: Whitelist,
    halt_path: Path | None,
    caps: SizingCaps,
    total_capital_usd: Decimal,
    quote_price_usd: Decimal,
    current_symbol_exposure_usd: Decimal,
    current_global_exposure_usd: Decimal,
) -> tuple[tuple[Any, dict[str, Any]], ...]:
    """Return the canonical chain of (gate_fn, kwargs) tuples.

    The same chain is consumed by both the live router and the
    backtest broker. `halt_path` may be None for backtest contexts
    where the operator halt flag is not relevant; in that case the
    halt gate is omitted (it would always allow anyway).
    """
    chain: list[tuple[Any, dict[str, Any]]] = [
        (whitelist_gate, {"whitelist": whitelist}),
    ]
    if halt_path is not None:
        chain.append((halt_gate, {"halt_path": halt_path}))
    chain.extend(
        [
            (
                per_trade_cap_gate,
                {
                    "caps": caps,
                    "total_capital_usd": total_capital_usd,
                    "quote_price_usd": quote_price_usd,
                },
            ),
            (
                per_symbol_cap_gate,
                {
                    "caps": caps,
                    "total_capital_usd": total_capital_usd,
                    "quote_price_usd": quote_price_usd,
                    "current_symbol_exposure_usd": current_symbol_exposure_usd,
                },
            ),
            (
                global_exposure_gate,
                {
                    "caps": caps,
                    "total_capital_usd": total_capital_usd,
                    "quote_price_usd": quote_price_usd,
                    "current_global_exposure_usd": current_global_exposure_usd,
                },
            ),
        ]
    )
    return tuple(chain)


def evaluate_chain(
    request: OrderRequest,
    chain: tuple[tuple[Any, dict[str, Any]], ...],
) -> GateDecision:
    """Run the chain in order; return the first Deny or an Allow at the end."""
    for gate_fn, kwargs in chain:
        decision = gate_fn(request, **kwargs)
        if not decision.allow:
            return decision
    return GateDecision(allow=True, gate="chain")
