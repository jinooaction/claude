"""Event-driven backtest replay loop (T025).

The engine streams bars via `revisions.iter_bars(..., as_of_ts_pin)`,
evaluates the rule's trigger via `strategy/triggers.py`, runs the
gate chain via `risk/chain.py`, simulates fills via
`execution/backtest_broker.py`, and updates a `Portfolio`.

A `BacktestResult` dataclass carries everything `report.py` needs to
emit `metrics.json` + `report.md` + `audit_log.jsonl` + `orders.jsonl`.

Phase 3 simplifications (Phase 4 will replace):
  * Single-instrument runs only.
  * No LookaheadError barrier (added in T032).
  * No corporate-action application (added in T037).
  * No participation cap / market impact (added in T035).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from auto_invest.backtest.cost_model import quote_cost
from auto_invest.backtest.metrics import BacktestMetrics, compute_metrics
from auto_invest.backtest.portfolio import Portfolio
from auto_invest.broker.models import OrderRequest
from auto_invest.config.backtest import BacktestConfig
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.backtest_broker import BacktestBroker, SimulatedFill
from auto_invest.market_data.adapters import InstrumentRef
from auto_invest.market_data.revisions import HistoricalBar, iter_bars
from auto_invest.market_data.store import PriceBar
from auto_invest.risk.chain import build_gate_chain, evaluate_chain
from auto_invest.strategy.triggers import TriggerContext, evaluate


@dataclass
class SimulatedAuditEntry:
    ts_utc: str
    event_type: str
    rule_id: str
    symbol: str
    payload: dict[str, Any]


@dataclass
class CostItemisedOrder:
    ts_utc: str
    rule_id: str
    symbol: str
    side: str
    order_type: str
    requested_qty: int
    fill_qty: int
    fill_price_usd: str
    commission_usd: str
    half_spread_usd: str
    impact_usd: str
    total_cost_usd: str


@dataclass
class BacktestResult:
    config: BacktestConfig
    metrics: BacktestMetrics
    audit_log: list[SimulatedAuditEntry]
    orders: list[CostItemisedOrder]
    equity_curve: list[tuple[str, Decimal]]
    starting_capital: Decimal
    final_equity: Decimal
    bar_count: int
    fill_count: int
    rejected_by_gate: int
    expired_or_cancelled: int


@dataclass
class EngineInputs:
    rule: TradingRule
    rule_snapshot_hash: str
    config: BacktestConfig
    whitelist: Whitelist
    caps: SizingCaps
    starting_capital_usd: Decimal


def _to_price_bar(bar: HistoricalBar) -> PriceBar:
    """Adapter so spec 001's trigger evaluator can consume HistoricalBar."""
    return PriceBar(
        symbol=bar.symbol,
        timeframe=_kind_to_timeframe(bar.kind),
        bar_open_utc=bar.bar_open_ts_utc,
        open_usd=bar.open,
        high_usd=bar.high,
        low_usd=bar.low,
        close_usd=bar.close,
        volume=int(bar.volume) if bar.volume == bar.volume.to_integral_value() else int(bar.volume),
    )


def _kind_to_timeframe(kind: str) -> str:
    return {
        "ohlcv_1m": "1m",
        "ohlcv_1h": "1h",
        "ohlcv_1d": "1d",
    }.get(kind, kind)


def _bars_per_year_for(kind: str) -> int:
    return {
        "ohlcv_1d": 252,
        "ohlcv_1h": 252 * 7,
        "ohlcv_1m": 252 * 6 * 60,
    }.get(kind, 252)


def _resolve_limit_price(
    expr: str,
    *,
    trigger_price: Decimal,
    last_close: Decimal | None,
) -> Decimal | None:
    """Trim wrapper around the spec 001 expression evaluator."""
    from auto_invest.execution.order_router import (
        LimitPriceExprError,
        evaluate_limit_price,
    )
    try:
        return evaluate_limit_price(expr, trigger_price=trigger_price, last_close=last_close)
    except LimitPriceExprError:
        return None


def run_backtest(
    *,
    conn: sqlite3.Connection,
    inputs: EngineInputs,
    instrument_idx: int = 0,
    account: str = "BACKTEST",
) -> BacktestResult:
    """Execute the backtest end-to-end and return a populated `BacktestResult`."""
    cfg = inputs.config
    rule = inputs.rule
    instrument = cfg.instruments[instrument_idx]
    iref = InstrumentRef(instrument.asset_class, instrument.venue, instrument.symbol)
    vendor = instrument.vendor
    if vendor is None:
        raise ValueError("instrument.vendor must be resolved before entering the engine")

    timeframe = getattr(rule.trigger, "timeframe", _kind_to_timeframe("ohlcv_1d"))
    kind = {
        "1m": "ohlcv_1m",
        "1h": "ohlcv_1h",
        "1d": "ohlcv_1d",
    }.get(timeframe, "ohlcv_1d")

    portfolio = Portfolio(starting_cash_usd=inputs.starting_capital_usd)
    broker = BacktestBroker(cost_model=cfg.cost_model)

    audit: list[SimulatedAuditEntry] = []
    orders: list[CostItemisedOrder] = []
    equity_curve: list[tuple[str, Decimal]] = []
    last_fired_at: datetime | None = None
    bars_window: list[PriceBar] = []
    fill_count = 0
    rejected_by_gate = 0
    expired_or_cancelled = 0
    days_invested = 0

    bar_count = 0
    first_ts: str | None = None
    last_ts: str | None = None

    for bar in iter_bars(
        conn,
        asset_class=iref.asset_class,
        venue=iref.venue,
        symbol=iref.symbol,
        kind=kind,
        vendor=vendor,
        from_utc=cfg.window.from_utc,
        to_utc=cfg.window.to_utc,
        as_of_ts_pin=cfg.window.as_of_ts_pin_utc,
    ):
        bar_count += 1
        first_ts = first_ts or bar.bar_open_ts_utc
        last_ts = bar.bar_open_ts_utc
        pb = _to_price_bar(bar)
        bars_window.append(pb)
        # Keep only the indicator-window worth of bars (cap at 1000 to bound mem).
        if len(bars_window) > 1000:
            bars_window = bars_window[-1000:]

        # Mark-to-market equity at this bar.
        marks = {iref.symbol: bar.close}
        eq = portfolio.equity_usd(marks)
        equity_curve.append((bar.bar_open_ts_utc, eq))
        if portfolio.position_qty(iref.symbol) > 0:
            days_invested += 1

        # Trigger evaluation.
        ts_utc = bar.bar_open_ts_utc
        decision_dt = _parse_iso(ts_utc)
        ctx = TriggerContext(
            now=decision_dt,
            current_price_usd=bar.close,
            bars=tuple(bars_window),
            last_fired_at_utc=last_fired_at,
        )

        if not rule.enabled:
            continue
        if rule.symbol != iref.symbol:
            continue

        try:
            should_fire = evaluate(rule.trigger, ctx)
        except Exception:  # noqa: BLE001
            should_fire = False

        if not should_fire:
            continue

        last_fired_at = decision_dt

        # Build order request (resolve limit-price expression).
        limit_price: Decimal | None = None
        if rule.action.order_type is OrderType.LIMIT:
            limit_price = _resolve_limit_price(
                rule.action.limit_price,
                trigger_price=bar.close,
                last_close=bar.close,
            )
            if limit_price is None:
                expired_or_cancelled += 1
                continue

        request = OrderRequest(
            account=account,
            symbol=rule.symbol,
            side=rule.action.side,
            order_type=rule.action.order_type,
            qty=rule.action.qty,
            limit_price_usd=limit_price,
        )

        # Risk-gate chain (single source of truth — SC-005).
        position = portfolio.positions.get(iref.symbol)
        symbol_exposure = (Decimal(position.qty) * bar.close) if position else Decimal("0")
        global_exposure = portfolio.equity_usd(marks) - portfolio.cash_usd
        chain = build_gate_chain(
            whitelist=inputs.whitelist,
            halt_path=None,  # backtest has no operator halt flag
            caps=inputs.caps,
            total_capital_usd=inputs.starting_capital_usd,
            quote_price_usd=bar.close,
            current_symbol_exposure_usd=symbol_exposure,
            current_global_exposure_usd=global_exposure,
        )
        decision = evaluate_chain(request, chain)
        if not decision.allow:
            rejected_by_gate += 1
            audit.append(
                SimulatedAuditEntry(
                    ts_utc=ts_utc,
                    event_type="ORDER_REJECTED_BY_GATE",
                    rule_id=rule.id,
                    symbol=rule.symbol,
                    payload={"gate": decision.gate, "reason": decision.reason or ""},
                )
            )
            continue

        # Simulate fill.
        fill: SimulatedFill | None = broker.simulate_fill(request, bar)
        if fill is None:
            expired_or_cancelled += 1
            audit.append(
                SimulatedAuditEntry(
                    ts_utc=ts_utc,
                    event_type="ORDER_EXPIRED",
                    rule_id=rule.id,
                    symbol=rule.symbol,
                    payload={"reason": "limit out of bar range or halt"},
                )
            )
            continue

        portfolio.apply_fill(symbol=rule.symbol, side=rule.action.side, fill=fill)
        fill_count += 1
        audit.append(
            SimulatedAuditEntry(
                ts_utc=ts_utc,
                event_type="ORDER_FILLED",
                rule_id=rule.id,
                symbol=rule.symbol,
                payload={
                    "qty": fill.qty,
                    "price_usd": str(fill.price_usd),
                    "side": rule.action.side.value,
                },
            )
        )
        orders.append(
            CostItemisedOrder(
                ts_utc=ts_utc,
                rule_id=rule.id,
                symbol=rule.symbol,
                side=rule.action.side.value,
                order_type=rule.action.order_type.value,
                requested_qty=rule.action.qty,
                fill_qty=fill.qty,
                fill_price_usd=str(fill.price_usd),
                commission_usd=str(fill.commission_usd),
                half_spread_usd=str(fill.half_spread_usd),
                impact_usd=str(fill.impact_usd),
                total_cost_usd=str(fill.total_cost_usd),
            )
        )

    # Compute metrics.
    notional_traded = sum(
        (Decimal(o.fill_qty) * Decimal(o.fill_price_usd) for o in orders),
        start=Decimal("0"),
    )
    if first_ts and last_ts:
        days_total = max(1, (_parse_iso(last_ts) - _parse_iso(first_ts)).days + 1)
    else:
        days_total = 0
    metrics = compute_metrics(
        equity_curve=[v for _, v in equity_curve],
        starting_capital=inputs.starting_capital_usd,
        trades=portfolio.trades,
        notional_traded_usd=notional_traded,
        gross_cost_usd=portfolio.total_cost_usd,
        days_invested=days_invested,
        days_total=days_total,
        bars_per_year=_bars_per_year_for(kind),
    )
    final_equity = equity_curve[-1][1] if equity_curve else inputs.starting_capital_usd
    return BacktestResult(
        config=cfg,
        metrics=metrics,
        audit_log=audit,
        orders=orders,
        equity_curve=equity_curve,
        starting_capital=inputs.starting_capital_usd,
        final_equity=final_equity,
        bar_count=bar_count,
        fill_count=fill_count,
        rejected_by_gate=rejected_by_gate,
        expired_or_cancelled=expired_or_cancelled,
    )


def _parse_iso(text: str) -> datetime:
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)
