"""Risk gates — deny-by-default checks before any order reaches the broker.

Each gate is a pure function returning a `GateDecision`. The order
router runs them in declared order; a single Deny short-circuits the
pipeline and the result is recorded as `ORDER_REJECTED_BY_GATE` in
the audit log.

Constitution mapping:
  - whitelist_gate          -> principle II (deny-by-default)
  - halt_gate               -> FR-013 (operator halt)
  - per_trade_cap_gate      -> principle I (sizing)
  - per_symbol_cap_gate     -> principle I (sizing)
  - global_exposure_gate    -> principle I (sizing)
  - stage_uniqueness_gate   -> principle VI (staged rollout) + FR-012
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from auto_invest.broker.models import OrderRequest
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import Side, StrategyStage
from auto_invest.config.whitelist import Whitelist
from auto_invest.worker.halt import is_halted


@dataclass(frozen=True)
class GateDecision:
    allow: bool
    gate: str
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


_STAGE_RANK: dict[StrategyStage, int] = {
    StrategyStage.BACKTEST: 0,
    StrategyStage.CANARY: 1,
    StrategyStage.FULL_LIVE: 2,
}


def _allow(gate: str) -> GateDecision:
    return GateDecision(allow=True, gate=gate)


def _deny(gate: str, reason: str, **metadata: Any) -> GateDecision:
    return GateDecision(allow=False, gate=gate, reason=reason, metadata=dict(metadata))


def _effective_price(request: OrderRequest, quote_price_usd: Decimal) -> Decimal:
    """Return limit_price for LIMIT orders, falling back to the live quote."""
    if request.limit_price_usd is not None:
        return request.limit_price_usd
    return quote_price_usd


def _signed_qty(request: OrderRequest) -> Decimal:
    """Positive for BUY (exposure increases), negative for SELL."""
    return Decimal(request.qty) if request.side is Side.BUY else -Decimal(request.qty)


def whitelist_gate(
    request: OrderRequest,
    *,
    whitelist: Whitelist,
) -> GateDecision:
    """Reject if any of symbol / account / order_type is not on the whitelist."""
    name = "whitelist_gate"
    if request.symbol not in whitelist.symbols:
        return _deny(
            name,
            f"symbol {request.symbol!r} is not on the whitelist",
            symbol=request.symbol,
        )
    if request.account not in whitelist.accounts:
        return _deny(name, "account is not on the whitelist")
    if request.order_type not in whitelist.order_types:
        return _deny(
            name,
            f"order_type {request.order_type.value!r} is not on the whitelist",
            order_type=request.order_type.value,
        )
    return _allow(name)


def halt_gate(
    request: OrderRequest,
    *,
    halt_path: Path,
) -> GateDecision:
    """Reject when the operator halt flag is set."""
    name = "halt_gate"
    if is_halted(halt_path):
        return _deny(name, "halt flag is set; new orders are blocked")
    return _allow(name)


def per_trade_cap_gate(
    request: OrderRequest,
    *,
    caps: SizingCaps,
    total_capital_usd: Decimal,
    quote_price_usd: Decimal,
) -> GateDecision:
    """Reject when notional (price * qty) exceeds the per-trade cap."""
    name = "per_trade_cap_gate"
    price = _effective_price(request, quote_price_usd)
    notional = price * Decimal(request.qty)
    cap_value = total_capital_usd * caps.per_trade_pct / Decimal(100)
    if notional > cap_value:
        return _deny(
            name,
            f"notional ${notional} exceeds per-trade cap ${cap_value}",
            notional_usd=str(notional),
            cap_usd=str(cap_value),
            cap_pct=str(caps.per_trade_pct),
        )
    return _allow(name)


def per_symbol_cap_gate(
    request: OrderRequest,
    *,
    caps: SizingCaps,
    total_capital_usd: Decimal,
    quote_price_usd: Decimal,
    current_symbol_exposure_usd: Decimal,
) -> GateDecision:
    """Reject when symbol exposure after fill exceeds the per-symbol cap.

    Sells reduce exposure, so they cannot violate an upper-bound cap and
    are short-circuited as Allow. (Short-selling prevention is a
    separate concern, out of scope for v1.)
    """
    name = "per_symbol_cap_gate"
    price = _effective_price(request, quote_price_usd)
    delta = price * _signed_qty(request)
    if delta <= 0:
        return _allow(name)
    new_exposure = current_symbol_exposure_usd + delta
    cap_value = total_capital_usd * caps.per_symbol_pct / Decimal(100)
    if new_exposure > cap_value:
        return _deny(
            name,
            f"symbol exposure would become ${new_exposure}, exceeds cap ${cap_value}",
            would_become_usd=str(new_exposure),
            cap_usd=str(cap_value),
            cap_pct=str(caps.per_symbol_pct),
        )
    return _allow(name)


def global_exposure_gate(
    request: OrderRequest,
    *,
    caps: SizingCaps,
    total_capital_usd: Decimal,
    quote_price_usd: Decimal,
    current_global_exposure_usd: Decimal,
) -> GateDecision:
    """Reject when total deployed capital after fill exceeds the global cap.

    Sells short-circuit to Allow for the same reason as per_symbol_cap_gate.
    """
    name = "global_exposure_gate"
    price = _effective_price(request, quote_price_usd)
    delta = price * _signed_qty(request)
    if delta <= 0:
        return _allow(name)
    new_exposure = current_global_exposure_usd + delta
    cap_value = total_capital_usd * caps.global_exposure_pct / Decimal(100)
    if new_exposure > cap_value:
        return _deny(
            name,
            f"global exposure would become ${new_exposure}, exceeds cap ${cap_value}",
            would_become_usd=str(new_exposure),
            cap_usd=str(cap_value),
            cap_pct=str(caps.global_exposure_pct),
        )
    return _allow(name)


def stage_uniqueness_gate(
    *,
    rule_id: str,
    symbol: str,
    proposed_stage: StrategyStage,
    active_stages_for_symbol: dict[str, StrategyStage],
) -> GateDecision:
    """Reject if a higher-stage version of this strategy is already active.

    Per FR-012 / constitution VI: starting a CANARY rule for `symbol` is
    forbidden while a FULL_LIVE rule for the same symbol exists, and
    similarly for BACKTEST -> CANARY. The same `rule_id` is treated as
    self and ignored.
    """
    name = "stage_uniqueness_gate"
    proposed_rank = _STAGE_RANK[proposed_stage]
    for active_rule_id, active_stage in active_stages_for_symbol.items():
        if active_rule_id == rule_id:
            continue
        if _STAGE_RANK[active_stage] > proposed_rank:
            return _deny(
                name,
                f"a higher-stage version ({active_rule_id} at "
                f"{active_stage.value}) is active for {symbol!r}",
                active_rule_id=active_rule_id,
                active_stage=active_stage.value,
                proposed_stage=proposed_stage.value,
            )
    return _allow(name)
