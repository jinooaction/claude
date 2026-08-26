"""Exact small-capital feasibility checks for an already planned portfolio."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from auto_invest.config.caps import SizingCaps

MIN_FUNDED_TARGET_RATIO = Decimal("0.66")
MAX_L1_WEIGHT_ERROR = Decimal("0.25")
MAX_LEG_WEIGHT_ERROR = Decimal("0.15")


@dataclass(frozen=True)
class FundabilityAssessment:
    """Projected post-order allocation under the live lot and cap rules."""

    fundable: bool
    capital_usd: Decimal
    investable_usd: Decimal
    active_target_count: int
    funded_target_count: int
    funded_target_ratio: Decimal
    quote_coverage_ratio: Decimal
    invested_fraction: Decimal
    target_weights: dict[str, Decimal]
    holdings: dict[str, int]
    prices: dict[str, Decimal]
    order_prices: dict[str, Decimal]
    planned_orders: tuple[tuple[str, str, int], ...]
    caps: dict[str, Any]
    effective_side: str
    projected_quantities: dict[str, int]
    projected_weights: dict[str, Decimal]
    l1_weight_error: Decimal
    max_leg_weight_error: Decimal
    checks: dict[str, bool]
    reasons: tuple[str, ...]

    SCHEMA_VERSION = "1.0"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "fundable": self.fundable,
            "capital_usd": str(self.capital_usd),
            "investable_usd": str(self.investable_usd),
            "active_target_count": self.active_target_count,
            "funded_target_count": self.funded_target_count,
            "funded_target_ratio": str(self.funded_target_ratio),
            "quote_coverage_ratio": str(self.quote_coverage_ratio),
            "invested_fraction": str(self.invested_fraction),
            "target_weights": {
                symbol: str(weight) for symbol, weight in self.target_weights.items()
            },
            "holdings": dict(self.holdings),
            "prices": {symbol: str(price) for symbol, price in self.prices.items()},
            "order_prices": {
                symbol: str(price) for symbol, price in self.order_prices.items()
            },
            "planned_orders": [
                {"symbol": symbol, "side": side, "qty": qty}
                for symbol, side, qty in self.planned_orders
            ],
            "caps": dict(self.caps),
            "effective_side": self.effective_side,
            "projected_quantities": dict(self.projected_quantities),
            "projected_weights": {
                symbol: str(weight) for symbol, weight in self.projected_weights.items()
            },
            "l1_weight_error": str(self.l1_weight_error),
            "max_leg_weight_error": str(self.max_leg_weight_error),
            "checks": dict(self.checks),
            "reasons": list(self.reasons),
        }


def _cap_amount(capital: Decimal, pct: Decimal) -> Decimal:
    return capital * pct / Decimal("100")


def assess_fundability(
    *,
    target_weights: Mapping[str, Decimal],
    holdings: Mapping[str, int],
    prices: Mapping[str, Decimal],
    order_prices: Mapping[str, Decimal],
    planned_orders: Sequence[tuple[str, str, int]],
    capital_usd: Decimal,
    invested_fraction: Decimal,
    caps: SizingCaps,
    effective_side: str = "both",
) -> FundabilityAssessment:
    """Project the exact planned orders after whole-share and exposure caps."""

    active = {
        str(symbol): Decimal(weight)
        for symbol, weight in target_weights.items()
        if Decimal(weight) > 0
    }
    investable = max(Decimal("0"), capital_usd * invested_fraction)
    projected_all = {
        str(symbol): max(0, int(qty)) for symbol, qty in holdings.items() if int(qty) > 0
    }
    quotes_present = sum(1 for symbol in active if prices.get(symbol, Decimal("0")) > 0)
    quote_ratio = Decimal(quotes_present) / Decimal(len(active)) if active else Decimal("0")
    exposure_symbols = set(active) | {
        str(symbol) for symbol, qty in holdings.items() if int(qty) > 0
    }
    exposure_quotes_complete = all(
        prices.get(symbol, Decimal("0")) > 0 for symbol in exposure_symbols
    )
    cap_compliant = True
    symbol_exposure = {
        symbol: Decimal(qty) * prices.get(symbol, Decimal("0"))
        for symbol, qty in projected_all.items()
    }
    global_exposure = sum(symbol_exposure.values(), Decimal("0"))
    per_trade_cap = _cap_amount(capital_usd, caps.per_trade_pct)
    per_symbol_cap = _cap_amount(capital_usd, caps.per_symbol_pct)
    global_cap = _cap_amount(capital_usd, caps.global_exposure_pct)

    for symbol, side, requested_qty in planned_orders:
        if requested_qty <= 0:
            continue
        if effective_side == "none":
            continue
        if effective_side == "sell" and side == "BUY":
            continue
        if effective_side == "buy" and side == "SELL":
            continue
        price = order_prices.get(symbol)
        if price is None or price <= 0:
            cap_compliant = False
            continue
        cap_qty = int(per_trade_cap // price)
        routed_qty = min(requested_qty, cap_qty)
        if routed_qty < 1:
            cap_compliant = False
            continue
        if side == "SELL":
            sold = min(projected_all.get(symbol, 0), routed_qty)
            projected_all[symbol] = projected_all.get(symbol, 0) - sold
            continue
        if symbol not in active:
            cap_compliant = False
            continue
        notional = Decimal(routed_qty) * price
        proposed_symbol = symbol_exposure.get(symbol, Decimal("0")) + notional
        proposed_global = global_exposure + Decimal(routed_qty) * price
        if proposed_symbol > per_symbol_cap or proposed_global > global_cap:
            cap_compliant = False
            continue
        projected_all[symbol] = projected_all.get(symbol, 0) + routed_qty
        symbol_exposure[symbol] = proposed_symbol
        global_exposure = proposed_global

    projected_weights: dict[str, Decimal] = {}
    errors: list[Decimal] = []
    for symbol, weight in active.items():
        price = prices.get(symbol, Decimal("0"))
        projected_weight = (
            Decimal(projected_all.get(symbol, 0)) * price / capital_usd
            if capital_usd > 0 and price > 0
            else Decimal("0")
        )
        projected_weights[symbol] = projected_weight
        errors.append(abs(projected_weight - weight * invested_fraction))

    projected = {symbol: projected_all.get(symbol, 0) for symbol in active}
    funded_count = sum(1 for symbol in active if projected[symbol] > 0)
    funded_ratio = Decimal(funded_count) / Decimal(len(active)) if active else Decimal("0")
    l1_error = sum(errors, Decimal("0"))
    max_error = max(errors, default=Decimal("0"))
    checks = {
        "capital_positive": capital_usd > 0,
        "invested_fraction_bounded": Decimal("0") < invested_fraction <= Decimal("1"),
        "holdings_long_only": all(int(qty) >= 0 for qty in holdings.values()),
        "active_targets_present": bool(active),
        "target_weights_bounded": bool(
            active and sum(active.values(), Decimal("0")) <= Decimal("1")
        ),
        "quote_coverage": quote_ratio == Decimal("1"),
        "exposure_quote_coverage": exposure_quotes_complete,
        "funded_target_ratio": funded_ratio >= MIN_FUNDED_TARGET_RATIO,
        "l1_weight_error": l1_error <= MAX_L1_WEIGHT_ERROR,
        "max_leg_weight_error": max_error <= MAX_LEG_WEIGHT_ERROR,
        "exposure_caps": cap_compliant,
    }
    reasons = tuple(name for name, passed in checks.items() if not passed)
    serialized_caps = {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in caps.model_dump().items()
    }
    return FundabilityAssessment(
        fundable=not reasons,
        capital_usd=capital_usd,
        investable_usd=investable,
        active_target_count=len(active),
        funded_target_count=funded_count,
        funded_target_ratio=funded_ratio,
        quote_coverage_ratio=quote_ratio,
        invested_fraction=invested_fraction,
        target_weights=dict(active),
        holdings={str(symbol): int(qty) for symbol, qty in holdings.items()},
        prices={str(symbol): Decimal(price) for symbol, price in prices.items()},
        order_prices={str(symbol): Decimal(price) for symbol, price in order_prices.items()},
        planned_orders=tuple(
            (str(symbol), str(side), int(qty)) for symbol, side, qty in planned_orders
        ),
        caps=serialized_caps,
        effective_side=effective_side,
        projected_quantities=projected,
        projected_weights=projected_weights,
        l1_weight_error=l1_error,
        max_leg_weight_error=max_error,
        checks=checks,
        reasons=reasons,
    )


def validate_fundability_evidence(
    evidence: object,
    *,
    expected_capital_usd: Decimal | None = None,
) -> bool:
    """Recheck serialized preview evidence before an upward money decision."""

    if not isinstance(evidence, Mapping) or evidence.get("schema_version") != "1.0":
        return False
    def parse_decimal(value: object) -> Decimal:
        parsed = Decimal(str(value))
        if not parsed.is_finite():
            raise ValueError("decimal must be finite")
        return parsed

    def parse_decimal_map(value: object) -> dict[str, Decimal]:
        if not isinstance(value, Mapping):
            raise ValueError("decimal map required")
        return {str(key): parse_decimal(item) for key, item in value.items()}

    def parse_int_map(value: object) -> dict[str, int]:
        if not isinstance(value, Mapping):
            raise ValueError("integer map required")
        output: dict[str, int] = {}
        for key, item in value.items():
            if isinstance(item, bool) or int(item) != item:
                raise ValueError("integer quantity required")
            output[str(key)] = int(item)
        return output

    try:
        capital = parse_decimal(evidence.get("capital_usd"))
        invested_fraction = parse_decimal(evidence.get("invested_fraction"))
        target_weights = parse_decimal_map(evidence.get("target_weights"))
        holdings = parse_int_map(evidence.get("holdings"))
        prices = parse_decimal_map(evidence.get("prices"))
        order_prices = parse_decimal_map(evidence.get("order_prices"))
        raw_orders = evidence.get("planned_orders")
        if not isinstance(raw_orders, Sequence) or isinstance(raw_orders, (str, bytes)):
            raise ValueError("planned order rows required")
        planned_orders: list[tuple[str, str, int]] = []
        for row in raw_orders:
            if not isinstance(row, Mapping):
                raise ValueError("planned order row mapping required")
            symbol = row.get("symbol")
            side = row.get("side")
            qty = row.get("qty")
            if not isinstance(symbol, str) or not symbol.strip() or side not in {"BUY", "SELL"}:
                raise ValueError("planned order identity required")
            if isinstance(qty, bool) or int(qty) != qty or int(qty) <= 0:
                raise ValueError("planned order quantity required")
            planned_orders.append((symbol, str(side), int(qty)))
        caps_payload = evidence.get("caps")
        if not isinstance(caps_payload, Mapping):
            raise ValueError("caps mapping required")
        caps = SizingCaps.model_validate(dict(caps_payload))
        effective_side = str(evidence.get("effective_side"))
        if effective_side not in {"both", "buy", "sell", "none"}:
            raise ValueError("effective side invalid")
    except (InvalidOperation, TypeError, ValueError):
        return False
    recomputed = assess_fundability(
        target_weights=target_weights,
        holdings=holdings,
        prices=prices,
        order_prices=order_prices,
        planned_orders=planned_orders,
        capital_usd=capital,
        invested_fraction=invested_fraction,
        caps=caps,
        effective_side=effective_side,
    )
    return bool(
        recomputed.fundable
        and (expected_capital_usd is None or capital == expected_capital_usd)
        and recomputed.as_dict() == dict(evidence)
    )


__all__ = [
    "FundabilityAssessment",
    "MAX_L1_WEIGHT_ERROR",
    "MAX_LEG_WEIGHT_ERROR",
    "MIN_FUNDED_TARGET_RATIO",
    "assess_fundability",
    "validate_fundability_evidence",
]
