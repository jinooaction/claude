"""Backtest replay engine (T023) — Path B per research.md R-B13.

The replay loop is sequential over (session_date, rule) pairs in
declaration order. For each pair it:

  1. Advances ReplayClock to the bar's session_close instant (DST-aware
     via exchange_calendars.XNYS).
  2. Re-attempts open GTC/DAY orders for the rule's symbol against this bar.
  3. Builds a TriggerContext (now, current_price = bar.close, indicator
     history as PriceBar derived from prior OHLCVBars) and calls
     strategy.triggers.evaluate().
  4. If fired: ORDER_INTENT → gate chain (risk.gates, in router order) →
     ORDER_REJECTED_BY_GATE on first deny, else BacktestBroker.submit_order
     → ORDER_SUBMITTED → optional FILL audit row.
  5. After all rules processed for the date: broker.expire_day_orders()
     → CANCEL rows for DAY expiries.

The async Worker.tick shell from spec 001 is intentionally bypassed —
see research.md R-B13 for the safety-equivalence argument. Gates and
trigger evaluators are imported unmodified from `risk/gates.py` and
`strategy/triggers.py`; the replay reuses the same code paths the live
worker uses to decide on an order.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import exchange_calendars as ec

from auto_invest.backtest.broker_mock import (
    BacktestBroker,
    BacktestLiveBrokerLeakError,
    FillEvent,
    OpenOrder,
    assert_backtest_adapter,
)
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.costs import BacktestCostModel
from auto_invest.backtest.data_model import (
    DataQualityWarning,
    OHLCVBar,
    canonicalise_decimal,
)
from auto_invest.backtest.data_source import HistoricalDataSource
from auto_invest.broker.models import OrderRequest
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType
from auto_invest.config.rules import IndicatorTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import (
    LimitPriceExprError,
    evaluate_limit_price,
)
from auto_invest.market_data.store import PriceBar
from auto_invest.persistence import audit
from auto_invest.persistence.audit import (
    CancelPayload,
    ErrorPayload,
    FillPayload,
    OrderIntentPayload,
    OrderRejectedByGatePayload,
    OrderSubmittedPayload,
)
from auto_invest.risk.gates import (
    GateDecision,
    global_exposure_gate,
    halt_gate,
    per_symbol_cap_gate,
    per_trade_cap_gate,
    whitelist_gate,
)
from auto_invest.strategy.regime import (
    DEFAULT_REGIME_SCALE,
    apply_regime_scale,
)
from auto_invest.strategy.regime import (
    detect as detect_regime,
)
from auto_invest.strategy.sizing import (
    SizingGroupMember,
    build_sizing_groups,
    erc_group_scales,
    group_scale_for,
    realized_volatility,
    sized_quantity,
)
from auto_invest.strategy.triggers import TriggerContext, evaluate

_XNYS = ec.get_calendar("XNYS")

DEFAULT_TOTAL_CAPITAL_USD = Decimal("100000")

# Shared immutable default — avoids a function call in the `replay` default
# argument (ruff B008). Frozen dataclass, so sharing one instance is safe.
_ZERO_COST_MODEL = BacktestCostModel.zero()


# ---------- on-the-wire records consumed by report.py (T024) ----------------


@dataclass(frozen=True)
class OrderRecord:
    correlation_id: str
    rule_id: str
    symbol: str
    side: str
    order_type: str
    qty: int
    limit_price_usd: str | None
    state: str
    ts_utc: str
    kis_order_id: str | None
    gate: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class FillRecord:
    correlation_id: str
    rule_id: str
    symbol: str
    side: str
    qty: int
    fill_price_usd: str
    executed_at_utc: str
    kis_fill_id: str


@dataclass(frozen=True)
class GateRejectionRecord:
    correlation_id: str
    rule_id: str
    symbol: str
    gate: str
    reason: str
    ts_utc: str


@dataclass(frozen=True)
class ReplayResult:
    """The full per-rule artefact set produced by `replay()` for T024."""

    per_rule_orders: dict[str, list[OrderRecord]]
    per_rule_fills: dict[str, list[FillRecord]]
    per_rule_gate_rejections: dict[str, list[GateRejectionRecord]]
    per_rule_equity_curve: dict[str, list[tuple[date, Decimal]]]
    per_rule_symbol: dict[str, str]
    per_rule_notional_traded_usd: dict[str, Decimal]
    data_quality_warnings: list[DataQualityWarning]
    total_orders: int
    total_fills: int
    total_gate_rejections: int
    per_rule_commission_usd: dict[str, Decimal] = field(default_factory=dict)
    per_rule_slippage_cost_usd: dict[str, Decimal] = field(default_factory=dict)
    total_commission_usd: Decimal = Decimal("0")
    total_slippage_cost_usd: Decimal = Decimal("0")


# ---------- helpers --------------------------------------------------------


def _session_close_utc(session_date: date) -> datetime:
    """Bar-close instant per R-B7 — DST + early-close aware via exchange_calendars."""
    close_ts = _XNYS.session_close(session_date.isoformat())
    if hasattr(close_ts, "to_pydatetime"):
        close_ts = close_ts.to_pydatetime()
    if close_ts.tzinfo is None:
        close_ts = close_ts.replace(tzinfo=UTC)
    return close_ts.astimezone(UTC)


def _utcnow_iso_ms(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"


def _ohlcv_to_pricebar(bar: OHLCVBar, *, timeframe: str = "1d") -> PriceBar:
    """Adapt OHLCV → PriceBar shape consumed by `strategy.indicators.*`."""
    return PriceBar(
        symbol=bar.symbol,
        timeframe=timeframe,
        bar_open_utc=bar.session_date.isoformat() + "T00:00:00.000Z",
        open_usd=bar.open,
        high_usd=bar.high,
        low_usd=bar.low,
        close_usd=bar.close,
        volume=bar.volume,
    )


def _signed_qty(side: str, qty: int) -> int:
    return qty if side == "BUY" else -qty


def _resolve_limit_price(
    rule: TradingRule, *, trigger_price: Decimal, last_close: Decimal | None
) -> Decimal | None:
    """Return None for MARKET orders, the resolved Decimal for LIMIT."""
    if rule.action.order_type is OrderType.MARKET:
        return None
    return evaluate_limit_price(
        rule.action.limit_price,
        trigger_price=trigger_price,
        last_close=last_close,
    )


def _run_gate_chain(
    request: OrderRequest,
    *,
    caps: SizingCaps,
    whitelist: Whitelist,
    halt_path: Path,
    total_capital_usd: Decimal,
    quote_price_usd: Decimal,
    current_symbol_exposure_usd: Decimal,
    current_global_exposure_usd: Decimal,
) -> GateDecision | None:
    """Mirror execution/order_router.py:288-317 exactly. Returns first deny or None."""
    chain: tuple[tuple[Any, dict[str, Any]], ...] = (
        (whitelist_gate, {"whitelist": whitelist}),
        (halt_gate, {"halt_path": halt_path}),
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
    )
    for gate_fn, kwargs in chain:
        decision = gate_fn(request, **kwargs)
        if not decision.allow:
            return decision
    return None


# ---------- state ----------------------------------------------------------


@dataclass
class _Position:
    qty: int = 0
    cashflow_usd: Decimal = Decimal("0")  # signed: BUY decreases, SELL increases


@dataclass
class _RuleState:
    """Per-rule mutable bookkeeping accumulated across the replay."""

    last_fired_at_utc: datetime | None = None
    order_seq: int = 0  # monotonic per-rule; feeds deterministic correlation_id (R-B5)
    orders: list[OrderRecord] = field(default_factory=list)
    fills: list[FillRecord] = field(default_factory=list)
    rejections: list[GateRejectionRecord] = field(default_factory=list)
    equity_curve: list[tuple[date, Decimal]] = field(default_factory=list)
    notional_traded_usd: Decimal = Decimal("0")
    commission_paid_usd: Decimal = Decimal("0")
    slippage_cost_usd: Decimal = Decimal("0")
    position: _Position = field(default_factory=_Position)


def _replay_group_scale(
    *,
    rule: TradingRule,
    sizing_groups: dict[str, list[SizingGroupMember]],
    bars_by_symbol: dict[str, list[OHLCVBar]],
    session_date: date,
) -> Decimal:
    """Group weight for ``rule`` at ``session_date`` — inverse_vol or ERC (spec 020).

    Returns 1 when the rule is not a group member (byte-equal to pre-2b).
    """
    sizing = rule.sizing
    if sizing is None or rule.sizing_group is None:
        return Decimal(1)
    members = sizing_groups.get(rule.sizing_group, [])
    if sizing.mode == "inverse_vol":
        strength = sizing.correlation_haircut
        member_vols: dict[str, Decimal | None] = {}
        closes_by_rule: dict[str, dict[date, Decimal]] = {}
        for member in members:
            sym_bars = [
                b
                for b in bars_by_symbol.get(member.symbol, [])
                if b.session_date <= session_date
            ]
            closes = [b.close for b in sym_bars]
            member_vols[member.rule_id] = realized_volatility(
                closes[-(member.lookback_bars + 1) :]
            )
            if strength > 0:
                closes_by_rule[member.rule_id] = {b.session_date: b.close for b in sym_bars}
        return group_scale_for(
            rule.id,
            member_vols=member_vols,
            closes_by_rule=closes_by_rule if strength > 0 else None,
            lookback_bars=sizing.lookback_bars,
            correlation_strength=strength,
        )
    if sizing.mode == "erc":
        closes_by_rule_erc: dict[str, dict[date, Decimal]] = {}
        member_vols_erc: dict[str, Decimal | None] = {}
        for member in members:
            sym_bars = [
                b
                for b in bars_by_symbol.get(member.symbol, [])
                if b.session_date <= session_date
            ]
            closes = [b.close for b in sym_bars]
            closes_by_rule_erc[member.rule_id] = {b.session_date: b.close for b in sym_bars}
            member_vols_erc[member.rule_id] = realized_volatility(
                closes[-(sizing.lookback_bars + 1) :]
            )
        weights = erc_group_scales(
            closes_by_rule_erc,
            lookback_bars=sizing.lookback_bars,
            member_vols=member_vols_erc,
        )
        return weights.get(rule.id, Decimal(1))
    return Decimal(1)


# ---------- main entry point ----------------------------------------------


def replay(
    *,
    rules: Sequence[TradingRule],
    data_source: HistoricalDataSource,
    date_start: date,
    date_end: date,
    caps: SizingCaps,
    whitelist: Whitelist,
    halt_path: Path,
    conn: sqlite3.Connection,
    clock: ReplayClock,
    broker: BacktestBroker,
    run_id: str,
    total_capital_usd: Decimal = DEFAULT_TOTAL_CAPITAL_USD,
    cost_model: BacktestCostModel = _ZERO_COST_MODEL,
) -> ReplayResult:
    """Drive the bar-level replay; emit audit rows; return a ReplayResult.

    Caller is expected to have already written BACKTEST_STARTED and to be
    inside `wall_clock_guard()`. This function emits ORDER_*/FILL/CANCEL
    rows that match the live worker's audit vocabulary verbatim, plus
    ERROR rows on internal failures.
    """
    # Defense-in-depth: confirm the broker we were handed is the mock.
    assert_backtest_adapter(broker.adapter_id)

    rule_state: dict[str, _RuleState] = {r.id: _RuleState() for r in rules}
    allocated_capital_per_rule = (
        total_capital_usd / Decimal(len(rules)) if rules else Decimal("0")
    )

    # Preload bars per symbol once — keeps the per-tick loop cheap and
    # gives us O(1) lookups for indicator history (slice up to current date).
    # Regime index symbols (spec 020) need full history for SMA-200 lookback,
    # so they are loaded from epoch (date.min) rather than date_start.
    regime_index_symbols = {
        r.regime_index_symbol for r in rules if r.regime_index_symbol is not None
    }
    symbols_in_use = sorted({r.symbol for r in rules} | regime_index_symbols)
    bars_by_symbol: dict[str, list[OHLCVBar]] = {
        sym: data_source.read_bars(
            sym,
            date.min if sym in regime_index_symbols else date_start,
            date_end,
        )
        for sym in symbols_in_use
    }
    bars_by_symbol_date: dict[tuple[str, date], OHLCVBar] = {
        (b.symbol, b.session_date): b
        for sym_bars in bars_by_symbol.values()
        for b in sym_bars
    }

    # Spec 017 slice 2b: inverse-vol risk-parity groups, built from the same
    # static rule set the live worker uses (single yardstick).
    sizing_groups = build_sizing_groups(rules)

    # Coverage holes → DataQualityWarnings, NOT a hard fail (the CLI
    # contract handles exit-66 separately at the caller level).
    holes = data_source.coverage_holes(symbols_in_use, date_start, date_end)
    warnings: list[DataQualityWarning] = []
    for sym, d in holes:
        warnings.append(
            DataQualityWarning(
                symbol=sym,
                session_date=d,
                kind="gap_over_7_days",
                note=f"missing bar for {sym} on {d.isoformat()}",
            )
        )

    # Sorted union of all session dates seen across the symbols in scope.
    all_dates = sorted(
        {b.session_date for sym_bars in bars_by_symbol.values() for b in sym_bars}
    )

    for session_date in all_dates:
        close_ts = _session_close_utc(session_date)
        clock.advance_to(close_ts)
        ts_iso = _utcnow_iso_ms(clock.now())

        # Per-rule pass in declaration order (R-B10).
        for rule in rules:
            if not rule.enabled:
                continue
            bar = bars_by_symbol_date.get((rule.symbol, session_date))
            if bar is None:
                continue
            state = rule_state[rule.id]

            # (a) Re-attempt open orders for this rule's symbol against today's bar.
            for fill in broker.try_fill_open_orders(bar, now=clock.now()):
                _record_fill(
                    conn=conn,
                    rule=rule,
                    state=state,
                    fill=fill,
                    ts_iso=ts_iso,
                    cost_model=cost_model,
                )

            # (b) Evaluate trigger with indicator history if needed.
            ctx = _build_context(
                rule=rule,
                bar=bar,
                clock=clock,
                bars_by_symbol=bars_by_symbol,
                state=state,
            )
            if not evaluate(rule.trigger, ctx):
                continue
            state.last_fired_at_utc = clock.now()

            # (c) Resolve limit price (LIMIT only).
            prior_bars = [
                b for b in bars_by_symbol[rule.symbol] if b.session_date < session_date
            ]
            last_close = prior_bars[-1].close if prior_bars else None

            # (c2) Spec 017: volatility-based sizing BEFORE the gate chain.
            #      Scales the declared qty by realized volatility — down by
            #      default, up within max_scale when bidirectional (slice 2), or
            #      by the inverse-vol group weight when mode="inverse_vol" (slice
            #      2b). The K1 caps below run unchanged and reject anything over
            #      the ceiling, so this is the same single yardstick the live
            #      router uses. sized_qty < 1 means sizing suppressed this fire
            #      (FR-S05); a qty=0 order is never built.
            group_scale = _replay_group_scale(
                rule=rule,
                sizing_groups=sizing_groups,
                bars_by_symbol=bars_by_symbol,
                session_date=session_date,
            )
            sized_qty = sized_quantity(
                base_qty=rule.action.qty,
                closes=[
                    b.close
                    for b in bars_by_symbol[rule.symbol]
                    if b.session_date <= session_date
                ],
                sizing=rule.sizing,
                group_scale=group_scale,
            )
            if sized_qty < 1:
                continue

            # Spec 020: regime scale — applied after vol/ERC sizing, mirrors live router.
            if rule.regime_index_symbol is not None:
                index_bars_up_to_now = [
                    b
                    for b in bars_by_symbol.get(rule.regime_index_symbol, [])
                    if b.session_date <= session_date
                ]
                index_price_bars = [
                    _ohlcv_to_pricebar(b)
                    for b in index_bars_up_to_now
                ]
                regime = detect_regime(index_price_bars)
                scale_map = rule.regime_scale or {}
                regime_scale = (
                    
                        Decimal(str(scale_map[regime.value]))
                        if regime.value in scale_map
                        else DEFAULT_REGIME_SCALE[regime]
                    
                )
                sized_qty = apply_regime_scale(sized_qty, regime_scale)
                if sized_qty < 1:
                    continue

            try:
                limit_price = _resolve_limit_price(
                    rule, trigger_price=bar.close, last_close=last_close
                )
            except LimitPriceExprError as exc:
                _emit_router_error(
                    conn=conn,
                    rule=rule,
                    state=state,
                    reason=str(exc),
                    run_id=run_id,
                    ts_iso=ts_iso,
                )
                continue

            request = OrderRequest(
                account=_resolve_backtest_account(whitelist),
                symbol=rule.symbol,
                side=rule.action.side,
                order_type=rule.action.order_type,
                qty=sized_qty,
                limit_price_usd=limit_price,
            )
            state.order_seq += 1
            correlation_id = f"bt-ord-{rule.id}-{state.order_seq:06d}"

            # (d) ORDER_INTENT + per-rule order record.
            audit.append(
                conn,
                OrderIntentPayload(
                    rule_id=rule.id,
                    symbol=rule.symbol,
                    side=rule.action.side.value,
                    order_type=rule.action.order_type.value,
                    qty=sized_qty,
                    limit_price_usd=(
                        str(limit_price) if limit_price is not None else None
                    ),
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=correlation_id,
                ts_utc=ts_iso,
            )

            # (e) Gate chain (router-equivalent).
            rule_symbols = {r.id: r.symbol for r in rules}
            symbol_exposure = _symbol_exposure(
                rule_state, rule_symbols, rule.symbol, bar.close
            )
            global_exposure = _global_exposure(
                rule_state, rule_symbols, bars_by_symbol_date, session_date
            )
            deny = _run_gate_chain(
                request,
                caps=caps,
                whitelist=whitelist,
                halt_path=halt_path,
                total_capital_usd=total_capital_usd,
                quote_price_usd=bar.close,
                current_symbol_exposure_usd=symbol_exposure,
                current_global_exposure_usd=global_exposure,
            )
            if deny is not None:
                _record_rejection(
                    conn=conn,
                    rule=rule,
                    state=state,
                    request=request,
                    correlation_id=correlation_id,
                    decision=deny,
                    ts_iso=ts_iso,
                )
                continue

            # (f) Submit to broker mock.
            try:
                outcome = broker.submit_order(
                    request, now=clock.now(), bar=bar, time_in_force="DAY"
                )
            except BacktestLiveBrokerLeakError:
                # Re-raise; the run.py orchestrator translates this to exit 80.
                raise
            audit.append(
                conn,
                OrderSubmittedPayload(
                    kis_order_id=outcome.result.kis_order_id,
                    submitted_at_utc=ts_iso,
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=correlation_id,
                ts_utc=ts_iso,
            )
            state.orders.append(
                OrderRecord(
                    correlation_id=correlation_id,
                    rule_id=rule.id,
                    symbol=rule.symbol,
                    side=rule.action.side.value,
                    order_type=rule.action.order_type.value,
                    qty=sized_qty,
                    limit_price_usd=(
                        str(limit_price) if limit_price is not None else None
                    ),
                    state="SUBMITTED",
                    ts_utc=ts_iso,
                    kis_order_id=outcome.result.kis_order_id,
                )
            )
            if outcome.fill is not None:
                _record_fill(
                    conn=conn,
                    rule=rule,
                    state=state,
                    fill=outcome.fill,
                    ts_iso=ts_iso,
                    correlation_id=correlation_id,
                    cost_model=cost_model,
                )

        # (g) Mark-to-market equity curve at end of session for every rule
        #     whose symbol has a bar today.
        for rule in rules:
            bar = bars_by_symbol_date.get((rule.symbol, session_date))
            if bar is None:
                continue
            state = rule_state[rule.id]
            position_value = Decimal(state.position.qty) * bar.close
            equity = (
                allocated_capital_per_rule + state.position.cashflow_usd + position_value
            )
            state.equity_curve.append((session_date, equity))

        # (h) End-of-day DAY-order expiry.
        for expired in broker.expire_day_orders(now=clock.now()):
            _emit_cancel(conn=conn, expired=expired, ts_iso=ts_iso)

    return _build_replay_result(rules, rule_state, warnings)


# ---------- record helpers -------------------------------------------------


def _build_context(
    *,
    rule: TradingRule,
    bar: OHLCVBar,
    clock: ReplayClock,
    bars_by_symbol: dict[str, list[OHLCVBar]],
    state: _RuleState,
) -> TriggerContext:
    """Indicator triggers need PriceBar history up to (not including) `bar`."""
    if isinstance(rule.trigger, IndicatorTrigger):
        prior = [
            _ohlcv_to_pricebar(b, timeframe=rule.trigger.timeframe)
            for b in bars_by_symbol[rule.symbol]
            if b.session_date < bar.session_date
        ]
        prior.append(_ohlcv_to_pricebar(bar, timeframe=rule.trigger.timeframe))
        history = tuple(prior)
    else:
        history = ()
    return TriggerContext(
        now=clock.now(),
        current_price_usd=bar.close,
        bars=history,
        last_fired_at_utc=state.last_fired_at_utc,
    )


def _record_fill(
    *,
    conn: sqlite3.Connection,
    rule: TradingRule,
    state: _RuleState,
    fill: FillEvent,
    ts_iso: str,
    cost_model: BacktestCostModel,
    correlation_id: str | None = None,
) -> None:
    """Emit a FILL audit row + update per-rule state (cashflow, position, notional).

    Applies the spec-016 transaction-cost overlay: slippage worsens the
    effective fill price (recorded in the audit row + FillRecord so the
    forensic price is the realistic one), and commission is deducted from
    cash separately. Per-rule commission/slippage totals accumulate for the
    report. With `BacktestCostModel.zero()` the effective price equals the
    broker's nominal price and no costs are charged (regression-preserving).
    """
    raw_price = fill.fill_price_usd
    eff_price = cost_model.effective_fill_price(fill.side, raw_price)
    commission = cost_model.commission_usd(fill.qty, eff_price)
    eff_price_str = canonicalise_decimal(eff_price)

    audit.append(
        conn,
        FillPayload(
            kis_fill_id=fill.kis_fill_id,
            qty=fill.qty,
            price_usd=eff_price_str,
            executed_at_utc=ts_iso,
        ),
        rule_id=rule.id,
        symbol=rule.symbol,
        correlation_id=correlation_id or fill.kis_order_id,
        ts_utc=ts_iso,
    )
    state.fills.append(
        FillRecord(
            correlation_id=correlation_id or fill.kis_order_id,
            rule_id=rule.id,
            symbol=rule.symbol,
            side=fill.side.value,
            qty=fill.qty,
            fill_price_usd=eff_price_str,
            executed_at_utc=ts_iso,
            kis_fill_id=fill.kis_fill_id,
        )
    )
    signed = _signed_qty(fill.side.value, fill.qty)
    state.position.qty += signed
    state.position.cashflow_usd -= Decimal(signed) * eff_price
    state.position.cashflow_usd -= commission
    state.notional_traded_usd += Decimal(fill.qty) * eff_price
    state.commission_paid_usd += commission
    state.slippage_cost_usd += abs(eff_price - raw_price) * Decimal(fill.qty)


def _record_rejection(
    *,
    conn: sqlite3.Connection,
    rule: TradingRule,
    state: _RuleState,
    request: OrderRequest,
    correlation_id: str,
    decision: GateDecision,
    ts_iso: str,
) -> None:
    audit.append(
        conn,
        OrderRejectedByGatePayload(
            gate=decision.gate,
            reason=decision.reason or "no reason",
            metadata=decision.metadata,
        ),
        rule_id=rule.id,
        symbol=rule.symbol,
        correlation_id=correlation_id,
        ts_utc=ts_iso,
    )
    state.orders.append(
        OrderRecord(
            correlation_id=correlation_id,
            rule_id=rule.id,
            symbol=rule.symbol,
            side=request.side.value,
            order_type=request.order_type.value,
            qty=request.qty,
            limit_price_usd=(
                str(request.limit_price_usd)
                if request.limit_price_usd is not None
                else None
            ),
            state="REJECTED_BY_GATE",
            ts_utc=ts_iso,
            kis_order_id=None,
            gate=decision.gate,
            reason=decision.reason,
        )
    )
    state.rejections.append(
        GateRejectionRecord(
            correlation_id=correlation_id,
            rule_id=rule.id,
            symbol=rule.symbol,
            gate=decision.gate,
            reason=decision.reason or "no reason",
            ts_utc=ts_iso,
        )
    )


def _emit_router_error(
    *,
    conn: sqlite3.Connection,
    rule: TradingRule,
    state: _RuleState,
    reason: str,
    run_id: str,
    ts_iso: str,
) -> None:
    audit.append(
        conn,
        ErrorPayload(where="backtest.replay", message=reason),
        rule_id=rule.id,
        symbol=rule.symbol,
        correlation_id=run_id,
        ts_utc=ts_iso,
    )


def _emit_cancel(
    *,
    conn: sqlite3.Connection,
    expired: OpenOrder,
    ts_iso: str,
) -> None:
    audit.append(
        conn,
        CancelPayload(reason="DAY_EXPIRY"),
        rule_id=None,
        symbol=expired.request.symbol,
        correlation_id=expired.kis_order_id,
        ts_utc=ts_iso,
    )


def _resolve_backtest_account(whitelist: Whitelist) -> str:
    """Pick any whitelisted account, or fall back to a placeholder.

    Backtests never reach a real broker so the account string is purely
    audit-trail metadata. We use the first whitelisted account if one
    exists so the whitelist_gate accepts it; if the operator declared
    none, fall back to BACKTEST so whitelist_gate denies (which is the
    correct conservative behaviour — operator should fix their whitelist).
    """
    if whitelist.accounts:
        return sorted(whitelist.accounts)[0]
    return "BACKTEST"


def _symbol_exposure(
    state_by_rule: dict[str, _RuleState],
    rule_symbols: dict[str, str],
    symbol: str,
    mark_price: Decimal,
) -> Decimal:
    """Sum signed position across every rule that targets `symbol`, marked at mark_price."""
    qty = sum(
        s.position.qty
        for rid, s in state_by_rule.items()
        if rule_symbols.get(rid) == symbol
    )
    return Decimal(qty) * mark_price


def _global_exposure(
    state_by_rule: dict[str, _RuleState],
    rule_symbols: dict[str, str],
    bars_by_symbol_date: dict[tuple[str, date], OHLCVBar],
    session_date: date,
) -> Decimal:
    """Sum across rules of position_qty × today's close (or 0 if no bar today)."""
    total = Decimal("0")
    for rid, state in state_by_rule.items():
        sym = rule_symbols.get(rid)
        if not sym:
            continue
        bar = bars_by_symbol_date.get((sym, session_date))
        if bar is None:
            continue
        total += Decimal(state.position.qty) * bar.close
    return total


def _build_replay_result(
    rules: Sequence[TradingRule],
    rule_state: dict[str, _RuleState],
    warnings: list[DataQualityWarning],
) -> ReplayResult:
    per_rule_symbol = {r.id: r.symbol for r in rules}
    per_rule_orders = {rid: list(s.orders) for rid, s in rule_state.items()}
    per_rule_fills = {rid: list(s.fills) for rid, s in rule_state.items()}
    per_rule_rejections = {
        rid: list(s.rejections) for rid, s in rule_state.items()
    }
    per_rule_equity = {rid: list(s.equity_curve) for rid, s in rule_state.items()}
    per_rule_notional = {
        rid: s.notional_traded_usd for rid, s in rule_state.items()
    }
    per_rule_commission = {
        rid: s.commission_paid_usd for rid, s in rule_state.items()
    }
    per_rule_slippage = {
        rid: s.slippage_cost_usd for rid, s in rule_state.items()
    }
    total_orders = sum(len(o) for o in per_rule_orders.values())
    total_fills = sum(len(f) for f in per_rule_fills.values())
    total_rejections = sum(len(r) for r in per_rule_rejections.values())
    total_commission = sum(per_rule_commission.values(), start=Decimal("0"))
    total_slippage = sum(per_rule_slippage.values(), start=Decimal("0"))
    return ReplayResult(
        per_rule_orders=per_rule_orders,
        per_rule_fills=per_rule_fills,
        per_rule_gate_rejections=per_rule_rejections,
        per_rule_equity_curve=per_rule_equity,
        per_rule_symbol=per_rule_symbol,
        per_rule_notional_traded_usd=per_rule_notional,
        data_quality_warnings=warnings,
        total_orders=total_orders,
        total_fills=total_fills,
        total_gate_rejections=total_rejections,
        per_rule_commission_usd=per_rule_commission,
        per_rule_slippage_cost_usd=per_rule_slippage,
        total_commission_usd=total_commission,
        total_slippage_cost_usd=total_slippage,
    )


__all__ = [
    "DEFAULT_TOTAL_CAPITAL_USD",
    "FillRecord",
    "GateRejectionRecord",
    "OrderRecord",
    "ReplayResult",
    "replay",
]
