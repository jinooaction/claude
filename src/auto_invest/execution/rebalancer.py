"""Live/paper portfolio-rebalance executor (spec 032 slice 2).

Slice 1 built the pure planner + backtest. This slice makes the rebalancing
engine *runnable* against the live (or paper) account — the step that lets the
dormant alpha actually be realized — WITHOUT threading a monthly rebalance into
the 1 Hz worker tick loop (which would be awkward and money-adjacent). Instead
it is a one-shot executor invoked explicitly (CLI `rebalance-once`), defaulting
to **paper**; real orders require an explicit operator choice.

Crucially it places NO orders through a parallel money path: every order is
routed through the SAME `OrderRouter.submit_order` the live worker uses, via a
filter-free synthetic `TradingRule`. That reuses the K1 gate chain, the audit
trail, and the paper/live branch verbatim — so this module adds zero new
trading-safety surface (Kernel touch 0).

Two K1 interactions are handled deterministically:
  * `per_symbol_cap_gate` / `global_exposure_gate` already short-circuit SELLs
    (exposure-reducing), so exits pass them.
  * `per_trade_cap_gate` checks notional regardless of side, so a large exit (or
    a large initial buy) would be rejected. We therefore CLAMP each order's qty
    down to the per-trade-cap ceiling before routing — never up — so every order
    passes per_trade and a large rebalance simply converges over repeated
    invocations (the same "small steps" discipline the existing qty=1 rules use).
    The clamp can only REDUCE size, so it cannot lift exposure past the boundary.

Orders are LIMIT with a marketable price (BUY at ask / SELL at bid, falling back
to last ± a small buffer) so they fill promptly while respecting the
constitution's "limit orders only" default. Deterministic: symbols processed in
sorted order, SELLs before BUYs (free cash first).
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_FLOOR, Decimal

from auto_invest.broker.models import Quote
from auto_invest.broker.overseas import order_exchange_for_quote_market
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import (
    Action,
    PortfolioRebalanceConfig,
    PriceTrigger,
    TradingRule,
)
from auto_invest.execution.order_router import OrderOutcome, OrderRouter
from auto_invest.market_data.store import get_bars
from auto_invest.persistence import positions as positions_mod
from auto_invest.strategy.factors import composite_scores
from auto_invest.strategy.rebalance import (
    PlannedOrder,
    macro_target_weights,
    rebalance_plan,
    target_weights,
)
from auto_invest.strategy.trend import (
    TrendEnsembleSpec,
    TrendSpec,
    spec_from_filter_config,
)

logger = logging.getLogger(__name__)

QuoteProvider = Callable[[str], Awaitable[Quote]]


def _trend_spec(
    config: PortfolioRebalanceConfig,
) -> TrendSpec | TrendEnsembleSpec | None:
    """config 의 옵트인 추세 필터를 스펙으로(없으면 None).

    스펙 048: trend_filter.ensemble_windows 가 있으면 다중 속도 앙상블(분수 노출)을,
    없으면 스펙 036 단일 속도(이진)를 만든다. 변환 자체는 strategy.trend 의 공유
    헬퍼 — 백테스트 리플레이와 *같은* 변환(단일 잣대, 헌법 X.2).
    """
    return spec_from_filter_config(config.trend_filter)


_CENT = Decimal("0.01")
# Marketable-limit buffer when bid/ask is unavailable: cross by 20 bps so the
# order is aggressive enough to fill but slippage stays bounded.
_MARKETABLE_BUFFER = Decimal("0.002")


@dataclass(frozen=True)
class RebalanceOrderResult:
    """Outcome of routing one planned order through the live/paper router."""

    symbol: str
    side: str
    requested_qty: int
    routed_qty: int
    limit_price_usd: Decimal
    state: str
    correlation_id: str
    reason: str | None = None


@dataclass(frozen=True)
class RebalanceWithheldOrder:
    """A planned order intentionally withheld before router submission."""

    symbol: str
    side: str
    requested_qty: int
    reason: str


@dataclass(frozen=True)
class RebalanceOutcome:
    """Everything one rebalance produced — for the CLI report and tests."""

    portfolio_id: str
    target_weights: dict[str, Decimal]
    planned: list[PlannedOrder]
    results: list[RebalanceOrderResult]
    account_wide: bool = False
    requested_side: str = "both"
    effective_side: str = "both"
    purchasable_cash_usd: Decimal | None = None
    required_cash_usd: Decimal | None = None
    planned_buy_notional_usd: Decimal = Decimal("0")
    planned_sell_notional_usd: Decimal = Decimal("0")
    withheld: list[RebalanceWithheldOrder] = field(default_factory=list)
    signal_target_weights: dict[str, Decimal] = field(default_factory=dict)
    execution_symbol_map: dict[str, str] = field(default_factory=dict)


def _marketable_limit(side: Side, quote: Quote) -> Decimal:
    """Aggressive limit near the touch: BUY at ask, SELL at bid (buffer fallback)."""
    if side is Side.BUY:
        ref = (
            quote.ask_usd
            if quote.ask_usd is not None
            else (quote.last_price_usd * (Decimal(1) + _MARKETABLE_BUFFER))
        )
    else:
        ref = (
            quote.bid_usd
            if quote.bid_usd is not None
            else (quote.last_price_usd * (Decimal(1) - _MARKETABLE_BUFFER))
        )
    return ref.quantize(_CENT)


def _per_trade_cap_qty(total_capital_usd: Decimal, caps: SizingCaps, price: Decimal) -> int:
    """Largest qty whose notional stays within the per-trade cap (floor)."""
    if price <= 0:
        return 0
    cap_value = total_capital_usd * caps.per_trade_pct / Decimal(100)
    return int((cap_value / price).to_integral_value(rounding=ROUND_FLOOR))


def _synthetic_rule(
    portfolio_id: str, symbol: str, side: Side, qty: int, *, stage: StrategyStage
) -> TradingRule:
    """A filter-free rule so the router applies ONLY the gate chain + paper/live
    branch (no per-rule sizing/ranking/quality/composite/judgment re-runs — the
    portfolio decision was already made by the planner)."""
    return TradingRule(
        id=f"rebalance:{portfolio_id}:{symbol}",
        symbol=symbol,
        stage=stage,
        priority=0,
        trigger=PriceTrigger(direction=">=", threshold=Decimal("0.01"), cooldown_seconds=0),
        action=Action(side=side, order_type=OrderType.LIMIT, qty=qty, limit_price="0"),
    )


def _closes_by_symbol(conn, universe, timeframe):
    """date -> close map per symbol from the stored daily bars (for risk schemes)."""
    out: dict[str, dict[date, Decimal]] = {}
    for sym in universe:
        bars = get_bars(conn, symbol=sym, timeframe=timeframe)
        series: dict[date, Decimal] = {}
        for b in bars:
            try:
                series[date.fromisoformat(b.bar_open_utc[:10])] = b.close_usd
            except ValueError:
                continue
        out[sym] = series
    return out


def _normalized_side(side: str) -> str:
    normalized = side.lower().strip()
    if normalized not in {"both", "sell", "buy"}:
        raise ValueError(f"execution_side must be one of both, sell, buy; got {side!r}")
    return normalized


def _cash_required(notional: Decimal, buffer_pct: Decimal) -> Decimal:
    if notional <= 0:
        return Decimal("0.00")
    return (notional * (Decimal("1") + buffer_pct)).quantize(_CENT)


def _router_reserves_open_orders(router: object) -> bool:
    return bool(getattr(router, "reserves_open_buy_orders", False)) and not bool(
        getattr(router, "paper_mode", False)
    )


def _paper_holdings_from_audit(conn: sqlite3.Connection) -> dict[str, int] | None:
    """Rebuild virtual paper holdings from append-only paper fill events."""
    from auto_invest.performance.engine import read_fills, reconstruct

    fills = read_fills(
        conn,
        mode="paper",
        since=datetime(1970, 1, 1, tzinfo=UTC),
        until=datetime(9999, 12, 31, tzinfo=UTC),
    )
    if not fills:
        return None
    positions, _, _, _ = reconstruct(fills)
    return {symbol: position.qty for symbol, position in positions.items() if position.qty > 0}


def _cached_holdings(conn: sqlite3.Connection) -> dict[str, int]:
    return {p.symbol: p.qty for p in positions_mod.get_all_positions(conn) if p.qty}


def _rebalance_holdings(conn: sqlite3.Connection, *, paper_mode: bool) -> dict[str, int]:
    if paper_mode:
        paper_holdings = _paper_holdings_from_audit(conn)
        if paper_holdings is not None:
            return paper_holdings
    return _cached_holdings(conn)


async def execute_rebalance(
    *,
    config: PortfolioRebalanceConfig,
    router: OrderRouter,
    conn: sqlite3.Connection,
    quote_provider: QuoteProvider,
    total_capital_usd: Decimal,
    caps: SizingCaps,
    timeframe: str = "1d",
    stage: StrategyStage = StrategyStage.CANARY,
    dry_run: bool = False,
    account_holdings: Mapping[str, int] | None = None,
    liquidation_only_symbols: frozenset[str] | None = None,
    execution_side: str = "both",
    purchasable_cash_usd: Decimal | None = None,
    cash_buffer_pct: Decimal = Decimal("0.01"),
    execution_symbol_map: Mapping[str, str] | None = None,
    lot_rounding: str = "floor",
    macro_snapshot: Mapping[str, object] | None = None,
    treasury_snapshot: Mapping[str, object] | None = None,
) -> RebalanceOutcome:
    """Compute the target portfolio and route the rebalance via the live/paper router.

    Reads bars/positions from ``conn``, prices from ``quote_provider`` (live KIS
    or a paper/test stub), and routes each planned order through
    ``router.submit_order``. In paper mode the router simulates the fill; in live
    mode it submits real orders. Returns a full per-order outcome record.

    With ``dry_run=True`` the full plan is computed (scores → weights → diff →
    per-trade clamp) but NO order is routed: each result carries state
    ``"DRY_RUN"`` so the operator can preview exactly what a live run would place
    before committing real money. The router is never called.
    """
    # 1. Score the universe (lookahead-free by construction — only stored bars).
    universe_bars = {
        sym: get_bars(conn, symbol=sym, timeframe=timeframe) for sym in config.universe
    }
    ranked = composite_scores(
        universe_bars,
        weights=config.weights,
        lookback_bars=config.lookback_bars,
        momentum_period=config.momentum_period,
        bb_period=config.bb_period,
        bb_std=config.bb_std,
    )
    signal_tw = target_weights(
        ranked_scores=ranked,
        closes_by_symbol=_closes_by_symbol(conn, config.universe, timeframe),
        weight_scheme=config.weight_scheme,
        top_n=config.top_n,
        top_pct=config.top_pct,
        lookback_bars=config.lookback_bars,
        trend=_trend_spec(config),
    )
    if config.macro_policy is not None:
        if macro_snapshot is None:
            raise ValueError("macro policy requires fresh macro evidence")
        signal_tw = macro_target_weights(
            base_weights=signal_tw,
            policy=config.macro_policy,
            snapshot=macro_snapshot,
        )
    if config.treasury_carry_policy is not None:
        if treasury_snapshot is None:
            raise ValueError("Treasury carry policy requires fresh Treasury evidence")
        from auto_invest.strategy.rebalance import treasury_target_weights

        signal_tw = treasury_target_weights(
            policy=config.treasury_carry_policy,
            snapshot=treasury_snapshot,
        )

    symbol_map = {
        str(signal).upper(): str(execution).upper()
        for signal, execution in (execution_symbol_map or {}).items()
    }
    if symbol_map:
        universe = set(config.universe)
        if set(symbol_map) != universe:
            missing = sorted(universe - set(symbol_map))
            extra = sorted(set(symbol_map) - universe)
            raise ValueError(
                "execution symbol map must exactly cover signal universe; "
                f"missing={missing}, extra={extra}"
            )
        if len(set(symbol_map.values())) != len(symbol_map):
            raise ValueError("execution symbol map values must be one-to-one")
        tw = {symbol_map[symbol]: weight for symbol, weight in signal_tw.items()}
    else:
        tw = dict(signal_tw)

    requested_side = _normalized_side(execution_side)
    liquidation_only = liquidation_only_symbols or frozenset()
    overlap = set(tw) & set(liquidation_only)
    if overlap:
        raise ValueError(
            "liquidation-only symbols cannot be target buys: " + ", ".join(sorted(overlap))
        )

    # 2. Current holdings (long-only; ignore zero rows). In account-wide mode
    # the broker snapshot is the live planning source, but unmanaged holdings
    # are deliberately kept out of the planner so they cannot be sold by default.
    account_wide = account_holdings is not None
    raw_holdings = (
        dict(account_holdings)
        if account_holdings is not None
        else _rebalance_holdings(conn, paper_mode=bool(getattr(router, "paper_mode", False)))
    )
    holdings: dict[str, int] = {}
    withheld: list[RebalanceWithheldOrder] = []
    for symbol, qty in sorted(raw_holdings.items()):
        if qty <= 0:
            continue
        if not account_wide or symbol in tw or symbol in liquidation_only:
            holdings[symbol] = qty
            continue
        withheld.append(
            RebalanceWithheldOrder(
                symbol=symbol,
                side="SELL",
                requested_qty=qty,
                reason="unmanaged_holding",
            )
        )

    # 3. Quotes for every symbol we might trade (targets + current holdings).
    needed = sorted(set(tw) | set(holdings))
    quotes: dict[str, Quote] = {}
    prices: dict[str, Decimal] = {}
    for sym in needed:
        try:
            q = await quote_provider(sym)
        except Exception:  # noqa: BLE001 — a quote failure just drops that symbol this round.
            logger.warning("rebalance: quote fetch failed for %s", sym, exc_info=True)
            continue
        quotes[sym] = q
        prices[sym] = q.last_price_usd

    # 4. Plan the rebalance against live prices + holdings.
    plan = rebalance_plan(
        target_weights=tw,
        holdings=holdings,
        prices=prices,
        capital_usd=total_capital_usd,
        invested_fraction=config.invested_fraction,
        rebalance_threshold_pct=config.rebalance_threshold_pct,
        min_notional_usd=config.min_notional_usd,
        mode=config.rebalance_mode,
        lot_rounding=lot_rounding,
    )

    # 5. Exposure snapshot (consistent for the whole rebalance; sells reduce later).
    symbol_exposure = {
        sym: Decimal(qty) * prices[sym] for sym, qty in holdings.items() if sym in prices
    }
    global_exposure = sum(symbol_exposure.values(), Decimal("0"))
    local_symbol_reservations = dict(symbol_exposure)
    local_global_reservation = global_exposure
    router_handles_reservations = _router_reserves_open_orders(router)

    # 6. Route SELLs first (free cash), then BUYs; each already symbol-sorted.
    for planned in plan:
        if planned.side == "BUY" and planned.symbol in liquidation_only:
            raise ValueError(f"liquidation-only symbol cannot be bought: {planned.symbol}")

    sells = [o for o in plan if o.side == "SELL"]
    buys = [o for o in plan if o.side == "BUY"]
    planned_buy_notional = Decimal("0")
    planned_sell_notional = Decimal("0")
    for planned in sells + buys:
        quote = quotes.get(planned.symbol)
        if quote is None:
            continue
        side = Side.BUY if planned.side == "BUY" else Side.SELL
        limit_price = _marketable_limit(side, quote)
        cap_qty = _per_trade_cap_qty(total_capital_usd, caps, limit_price)
        routed_qty = min(planned.qty, cap_qty)
        if routed_qty < 1:
            continue
        notional = Decimal(routed_qty) * limit_price
        if planned.side == "BUY":
            planned_buy_notional += notional
        else:
            planned_sell_notional += notional
    planned_buy_notional = planned_buy_notional.quantize(_CENT)
    planned_sell_notional = planned_sell_notional.quantize(_CENT)
    required_cash = _cash_required(planned_buy_notional, cash_buffer_pct)

    effective_side = requested_side
    cash_shortfall = (
        purchasable_cash_usd is not None
        and planned_buy_notional > 0
        and purchasable_cash_usd < required_cash
    )
    if cash_shortfall:
        effective_side = "sell" if sells else "none"

    results: list[RebalanceOrderResult] = []
    for planned in sells + buys:
        if effective_side == "none":
            withheld.append(
                RebalanceWithheldOrder(
                    symbol=planned.symbol,
                    side=planned.side,
                    requested_qty=planned.qty,
                    reason="insufficient_purchasable_cash",
                )
            )
            continue
        if effective_side == "sell" and planned.side == "BUY":
            withheld.append(
                RebalanceWithheldOrder(
                    symbol=planned.symbol,
                    side=planned.side,
                    requested_qty=planned.qty,
                    reason=(
                        "cash_shortfall_sell_first" if cash_shortfall else "side_filtered_sell_only"
                    ),
                )
            )
            continue
        if effective_side == "buy" and planned.side == "SELL":
            withheld.append(
                RebalanceWithheldOrder(
                    symbol=planned.symbol,
                    side=planned.side,
                    requested_qty=planned.qty,
                    reason="side_filtered_buy_only",
                )
            )
            continue
        quote = quotes.get(planned.symbol)
        if quote is None:
            continue  # no price this round
        side = Side.BUY if planned.side == "BUY" else Side.SELL
        limit_price = _marketable_limit(side, quote)
        # Clamp DOWN to the per-trade cap so the order passes per_trade_cap_gate;
        # a large rebalance converges over repeated invocations.
        cap_qty = _per_trade_cap_qty(total_capital_usd, caps, limit_price)
        routed_qty = min(planned.qty, cap_qty)
        if routed_qty < 1:
            results.append(
                RebalanceOrderResult(
                    symbol=planned.symbol,
                    side=planned.side,
                    requested_qty=planned.qty,
                    routed_qty=0,
                    limit_price_usd=limit_price,
                    state="SKIPPED_PER_TRADE_CAP",
                    correlation_id="",
                    reason="per_trade_cap_below_one_share",
                )
            )
            continue

        if dry_run:
            # Preview only — compute what WOULD be placed, route nothing.
            results.append(
                RebalanceOrderResult(
                    symbol=planned.symbol,
                    side=planned.side,
                    requested_qty=planned.qty,
                    routed_qty=routed_qty,
                    limit_price_usd=limit_price,
                    state="DRY_RUN",
                    correlation_id="",
                    reason=None,
                )
            )
            continue

        rule = _synthetic_rule(config.id, planned.symbol, side, routed_qty, stage=stage)
        # Override the synthetic rule's placeholder limit with our marketable price
        # by passing it as a literal expression the router evaluates verbatim.
        rule = rule.model_copy(
            update={"action": rule.action.model_copy(update={"limit_price": str(limit_price)})}
        )
        # 시세 해석기가 알아낸 *실제 상장 거래소*(quote.resolved_market)를 주문 거래소
        # (OVRS_EXCG_CD)로 옮긴다 — SPY·GLD(AMS→AMEX)·IEF(NAS→NASD). 매핑에 없으면 None →
        # 라우터가 설정된 기본 거래소로 폴백(회귀 0). 검증된 멀티에셋 유니버스의 라이브 주문이
        # 종목별로 올바른 거래소로 가게 하는 마지막 고리.
        order_exchange = order_exchange_for_quote_market(quote.resolved_market)
        current_symbol_exposure_usd = (
            symbol_exposure.get(planned.symbol, Decimal("0"))
            if router_handles_reservations
            else local_symbol_reservations.get(planned.symbol, Decimal("0"))
        )
        current_global_exposure_usd = (
            global_exposure if router_handles_reservations else local_global_reservation
        )
        outcome: OrderOutcome = await router.submit_order(
            rule=rule,
            quote_price_usd=quote.last_price_usd,
            quote_ask_usd=quote.ask_usd,
            quote_bid_usd=quote.bid_usd,
            total_capital_usd=total_capital_usd,
            current_symbol_exposure_usd=current_symbol_exposure_usd,
            current_global_exposure_usd=current_global_exposure_usd,
            order_exchange=order_exchange,
        )
        if (
            planned.side == "BUY"
            and not router_handles_reservations
            and outcome.state in {"PAPER_FILLED", "SUBMITTED", "SUBMISSION_UNKNOWN"}
        ):
            local_symbol_reservations[planned.symbol] = (
                local_symbol_reservations.get(planned.symbol, Decimal("0")) + notional
            )
            local_global_reservation += notional
        results.append(
            RebalanceOrderResult(
                symbol=planned.symbol,
                side=planned.side,
                requested_qty=planned.qty,
                routed_qty=routed_qty,
                limit_price_usd=limit_price,
                state=outcome.state,
                correlation_id=outcome.correlation_id,
                reason=outcome.reason,
            )
        )

    logger.info(
        "rebalance %s: %d planned, %d routed",
        config.id,
        len(plan),
        sum(1 for r in results if r.routed_qty > 0),
    )
    return RebalanceOutcome(
        portfolio_id=config.id,
        target_weights=tw,
        planned=plan,
        results=results,
        account_wide=account_wide,
        requested_side=requested_side,
        effective_side=effective_side,
        purchasable_cash_usd=purchasable_cash_usd,
        required_cash_usd=required_cash,
        planned_buy_notional_usd=planned_buy_notional,
        planned_sell_notional_usd=planned_sell_notional,
        withheld=withheld,
        signal_target_weights=dict(signal_tw),
        execution_symbol_map=symbol_map,
    )


__all__ = [
    "QuoteProvider",
    "RebalanceOrderResult",
    "RebalanceOutcome",
    "RebalanceWithheldOrder",
    "execute_rebalance",
]
