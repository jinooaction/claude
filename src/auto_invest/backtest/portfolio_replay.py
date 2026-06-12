"""Portfolio-rebalancing backtest driver (spec 032 slice 1).

Where `backtest/replay.py` replays independent per-rule triggers, this driver
replays a *portfolio*: every ``rebalance_every_n_sessions`` it scores the whole
universe with the spec 025 composite alpha, builds a target-weight vector
(spec 032 ``target_weights``), diffs it against the live holdings, and routes
the resulting BUY **and SELL** orders through the SAME unchanged K1 gate chain
the live router uses (`risk/gates.py`). The equity curve is marked to market at
every session close, so the operator can MEASURE — on the single yardstick of
`backtest/metrics.py` — what the rebalancing engine's return/risk profile is
before any money moves.

Lookahead-free: on a rebalance date only bars with ``session_date <= today`` are
scored. Deterministic Decimal (constitution X.2). MARKET orders fill at the
broker mock's conservative intrabar price (BUY at high, SELL at low). This
driver NEVER touches a live broker (the mock-adapter assertion guards that) and
is invoked only from the backtest CLI — the live worker is unchanged (FR-R07).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path

from auto_invest.backtest.broker_mock import BacktestBroker, assert_backtest_adapter
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.costs import BacktestCostModel
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.data_source import HistoricalDataSource
from auto_invest.backtest.metrics import (
    daily_returns_from_equity,
    max_drawdown_pct,
    sharpe_ratio,
    sortino_ratio,
    total_return_pct,
)
from auto_invest.backtest.replay import (
    DEFAULT_TOTAL_CAPITAL_USD,
    FillRecord,
    GateRejectionRecord,
    OrderRecord,
    _ohlcv_to_pricebar,
    _resolve_backtest_account,
    _run_gate_chain,
    _session_close_utc,
    _utcnow_iso_ms,
)
from auto_invest.broker.models import OrderRequest
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import audit
from auto_invest.persistence.audit import (
    FillPayload,
    OrderIntentPayload,
    OrderRejectedByGatePayload,
    OrderSubmittedPayload,
)
from auto_invest.strategy.factors import composite_scores
from auto_invest.strategy.rebalance import rebalance_plan, target_weights
from auto_invest.strategy.trend import spec_from_filter_config

_ZERO_COST_MODEL = BacktestCostModel.zero()


@dataclass(frozen=True)
class PortfolioReplayResult:
    """Artefacts + single-yardstick metrics from one portfolio backtest."""

    equity_curve: list[tuple[date, Decimal]]
    rebalance_dates: list[date]
    orders: list[OrderRecord]
    fills: list[FillRecord]
    gate_rejections: list[GateRejectionRecord]
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    turnover_ratio: Decimal  # gross traded notional / mean equity
    commission_usd: Decimal
    slippage_cost_usd: Decimal
    final_equity_usd: Decimal
    # Naive equal-weight buy-and-hold of the SAME universe over the SAME window —
    # the scientific control for "did active rebalancing/selection add value?".
    benchmark_total_return_pct: Decimal = Decimal("0")
    benchmark_max_drawdown_pct: Decimal = Decimal("0")
    benchmark_sharpe_ratio: Decimal = Decimal("0")
    excess_return_pct: Decimal = Decimal("0")  # strategy − benchmark


@dataclass
class _Portfolio:
    cash_usd: Decimal
    positions: dict[str, int] = field(default_factory=dict)

    def qty(self, symbol: str) -> int:
        return self.positions.get(symbol, 0)

    def equity(self, prices: dict[str, Decimal]) -> Decimal:
        mv = sum(
            (Decimal(q) * prices[s] for s, q in self.positions.items() if s in prices),
            Decimal("0"),
        )
        return self.cash_usd + mv


def _rebalance_indices(n_dates: int, every: int) -> set[int]:
    """Indices into the trading-date list on which we rebalance (0, every, 2·every…)."""
    return {i for i in range(n_dates) if i % every == 0}


def replay_portfolio(
    *,
    config: PortfolioRebalanceConfig,
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
) -> PortfolioReplayResult:
    """Drive a periodic-rebalance portfolio backtest; return curve + metrics."""
    assert_backtest_adapter(broker.adapter_id)

    # Load full history (from epoch) so the first rebalance has its lookback.
    bars_by_symbol = {
        sym: data_source.read_bars(sym, date.min, date_end)
        for sym in config.universe
    }
    bars_by_symbol_date = {
        (b.symbol, b.session_date): b
        for sym_bars in bars_by_symbol.values()
        for b in sym_bars
    }

    # Trading dates = sessions within [date_start, date_end] across the universe.
    trading_dates = sorted(
        {
            b.session_date
            for sym_bars in bars_by_symbol.values()
            for b in sym_bars
            if date_start <= b.session_date <= date_end
        }
    )
    rebalance_idx = _rebalance_indices(
        len(trading_dates), config.rebalance_every_n_sessions
    )

    portfolio = _Portfolio(cash_usd=total_capital_usd)
    account = _resolve_backtest_account(whitelist)

    orders: list[OrderRecord] = []
    fills: list[FillRecord] = []
    rejections: list[GateRejectionRecord] = []
    equity_curve: list[tuple[date, Decimal]] = []
    rebalance_dates: list[date] = []
    order_seq = 0
    traded_notional = Decimal("0")

    for idx, session_date in enumerate(trading_dates):
        close_ts = _session_close_utc(session_date)
        clock.advance_to(close_ts)
        ts_iso = _utcnow_iso_ms(clock.now())

        prices_today = {
            sym: bar.close
            for sym in config.universe
            if (bar := bars_by_symbol_date.get((sym, session_date))) is not None
        }

        if idx in rebalance_idx:
            rebalance_dates.append(session_date)
            order_seq = _do_rebalance(
                config=config,
                session_date=session_date,
                bars_by_symbol=bars_by_symbol,
                bars_by_symbol_date=bars_by_symbol_date,
                prices_today=prices_today,
                portfolio=portfolio,
                caps=caps,
                whitelist=whitelist,
                halt_path=halt_path,
                account=account,
                broker=broker,
                conn=conn,
                ts_iso=ts_iso,
                clock=clock,
                cost_model=cost_model,
                orders=orders,
                fills=fills,
                rejections=rejections,
                order_seq=order_seq,
            )

        # Mark-to-market equity at session close (uses last known close for any
        # symbol without a bar today — conservative carry-forward).
        marks = _carry(prices_today, portfolio, bars_by_symbol_date, session_date)
        equity_curve.append((session_date, portfolio.equity(marks)))

    # Aggregate cost/turnover from the recorded fills (single source of truth).
    for fr in fills:
        notional = Decimal(fr.qty) * Decimal(fr.fill_price_usd)
        traded_notional += notional
    commission_total = _sum_commission(fills, cost_model)
    # Slippage is already embedded in each recorded effective fill price (used for
    # cash settlement), so it is not double-counted as a separate line here.
    slippage_total = Decimal("0")

    equities = [e for _, e in equity_curve]
    mean_equity = (
        sum(equities, Decimal("0")) / Decimal(len(equities)) if equities else Decimal("1")
    )
    turnover = (
        (traded_notional / mean_equity).quantize(Decimal("0.000001"))
        if mean_equity > 0
        else Decimal("0")
    )
    daily_rets = daily_returns_from_equity(equities) if len(equities) >= 2 else []
    strat_return = total_return_pct(equities)

    # Naive equal-weight buy-and-hold benchmark over the same window (the control).
    bench_curve = _benchmark_equity_curve(
        list(config.universe),
        trading_dates,
        bars_by_symbol_date,
        total_capital_usd,
        config.invested_fraction,
    )
    bench_eq = [e for _, e in bench_curve]
    bench_return = total_return_pct(bench_eq)
    bench_rets = daily_returns_from_equity(bench_eq) if len(bench_eq) >= 2 else []

    return PortfolioReplayResult(
        equity_curve=equity_curve,
        rebalance_dates=rebalance_dates,
        orders=orders,
        fills=fills,
        gate_rejections=rejections,
        total_return_pct=strat_return,
        max_drawdown_pct=max_drawdown_pct(equities) if equities else Decimal("0"),
        sharpe_ratio=sharpe_ratio(daily_rets),
        sortino_ratio=sortino_ratio(daily_rets),
        turnover_ratio=turnover,
        commission_usd=commission_total,
        slippage_cost_usd=slippage_total,
        final_equity_usd=equities[-1] if equities else total_capital_usd,
        benchmark_total_return_pct=bench_return,
        benchmark_max_drawdown_pct=(
            max_drawdown_pct(bench_eq) if bench_eq else Decimal("0")
        ),
        benchmark_sharpe_ratio=sharpe_ratio(bench_rets),
        excess_return_pct=(strat_return - bench_return),
    )


# ----------------------------------------------------------------- internals


def _benchmark_equity_curve(
    universe: list[str],
    trading_dates: list[date],
    bars_by_symbol_date: dict[tuple[str, date], OHLCVBar],
    capital: Decimal,
    invested_fraction: Decimal,
) -> list[tuple[date, Decimal]]:
    """Equal-weight buy-and-hold of the whole universe — the naive control.

    Buys equal-dollar of every symbol priced on the first trading date, holds to
    the end (no rebalance, no costs), marks to market each session. This is the
    yardstick for "did active rebalancing/selection beat just holding the basket?".
    """
    if not trading_dates:
        return []
    first = trading_dates[0]
    first_prices = {
        s: bar.close
        for s in universe
        if (bar := bars_by_symbol_date.get((s, first))) is not None and bar.close > 0
    }
    if not first_prices:
        return [(d, capital) for d in trading_dates]
    per_name = (capital * invested_fraction) / Decimal(len(first_prices))
    qty = {
        s: int((per_name / p).to_integral_value(rounding=ROUND_FLOOR))
        for s, p in first_prices.items()
    }
    spent = sum((Decimal(q) * first_prices[s] for s, q in qty.items()), Decimal("0"))
    cash = capital - spent
    last_price = dict(first_prices)
    curve: list[tuple[date, Decimal]] = []
    for d in trading_dates:
        for s in qty:
            bar = bars_by_symbol_date.get((s, d))
            if bar is not None:
                last_price[s] = bar.close
        mv = sum((Decimal(qty[s]) * last_price[s] for s in qty), Decimal("0"))
        curve.append((d, cash + mv))
    return curve


def _carry(
    prices_today: dict[str, Decimal],
    portfolio: _Portfolio,
    bars_by_symbol_date: dict[tuple[str, date], object],
    session_date: date,
) -> dict[str, Decimal]:
    """Prices for the equity mark: today's close where available, else the most
    recent prior close (so a holding with no bar today is not silently zeroed)."""
    marks = dict(prices_today)
    for sym in portfolio.positions:
        if sym in marks:
            continue
        prior = None
        # walk back a bounded window for the last known close
        for back in range(1, 8):
            bar = bars_by_symbol_date.get((sym, session_date - timedelta(days=back)))
            if bar is not None:
                prior = bar.close  # type: ignore[attr-defined]
                break
        if prior is not None:
            marks[sym] = prior
    return marks


def _do_rebalance(
    *,
    config: PortfolioRebalanceConfig,
    session_date: date,
    bars_by_symbol,
    bars_by_symbol_date,
    prices_today: dict[str, Decimal],
    portfolio: _Portfolio,
    caps: SizingCaps,
    whitelist: Whitelist,
    halt_path: Path,
    account: str,
    broker: BacktestBroker,
    conn: sqlite3.Connection,
    ts_iso: str,
    clock: ReplayClock,
    cost_model: BacktestCostModel,
    orders: list[OrderRecord],
    fills: list[FillRecord],
    rejections: list[GateRejectionRecord],
    order_seq: int,
) -> int:
    """Score → target → diff → route one rebalance. Returns the new order_seq."""
    # Lookahead-free universe bars / closes (session_date 이하만).
    universe_bars = {}
    closes_by_symbol = {}
    for sym in config.universe:
        sym_bars = [b for b in bars_by_symbol.get(sym, []) if b.session_date <= session_date]
        universe_bars[sym] = [_ohlcv_to_pricebar(b) for b in sym_bars]
        closes_by_symbol[sym] = {b.session_date: b.close for b in sym_bars}

    ranked = composite_scores(
        universe_bars,
        weights=config.weights,
        lookback_bars=config.lookback_bars,
        momentum_period=config.momentum_period,
        bb_period=config.bb_period,
        bb_std=config.bb_std,
    )
    tw = target_weights(
        ranked_scores=ranked,
        closes_by_symbol=closes_by_symbol,
        weight_scheme=config.weight_scheme,
        top_n=config.top_n,
        top_pct=config.top_pct,
        lookback_bars=config.lookback_bars,
        # 라이브 리밸런서와 같은 공유 변환(단일 잣대, 헌법 X.2). 과거 이 자리가
        # 단일 속도 TrendSpec 만 만들어 ensemble_windows(스펙 048)를 조용히
        # 무시했다 — 백테스트가 배포된 전략과 다른 전략을 재생하는 버그.
        trend=spec_from_filter_config(config.trend_filter),
    )

    equity = portfolio.equity(prices_today)
    plan = rebalance_plan(
        target_weights=tw,
        holdings=dict(portfolio.positions),
        prices=prices_today,
        capital_usd=equity,
        invested_fraction=config.invested_fraction,
        rebalance_threshold_pct=config.rebalance_threshold_pct,
        min_notional_usd=config.min_notional_usd,
        mode=config.rebalance_mode,
    )

    # 주문 유형: MARKET 이 화이트리스트에 있으면 종전대로 MARKET(byte 동일). 배포
    # 설정(LIMIT 전용 화이트리스트, 라이브는 marketable-limit)에서는 종가 지정가
    # LIMIT 로 낸다 — 과거엔 MARKET 하드코딩이라 whitelist_gate 가 전 주문을 거부해
    # "배포된 TOML 은 백테스트 불가(전부 현금 곡선)"였다(단일 잣대 구멍).
    use_market = OrderType.MARKET in whitelist.order_types
    order_type = OrderType.MARKET if use_market else OrderType.LIMIT

    # Sells first (free cash), then buys; each already symbol-sorted.
    sells = [o for o in plan if o.side == "SELL"]
    buys = [o for o in plan if o.side == "BUY"]
    for planned in sells + buys:
        bar = bars_by_symbol_date.get((planned.symbol, session_date))
        if bar is None:
            continue
        # Clamp DOWN to the per-trade cap so the order passes per_trade_cap_gate,
        # mirroring the live rebalancer (execution/rebalancer.py): a large rebalance
        # converges over successive rebalances instead of being dropped whole. This
        # keeps backtest == live behaviour (single yardstick, constitution X.2).
        cap_value = equity * caps.per_trade_pct / Decimal(100)
        max_qty = (
            int((cap_value / bar.close).to_integral_value(rounding=ROUND_FLOOR))
            if bar.close > 0
            else 0
        )
        qty = min(planned.qty, max_qty)
        if qty < 1:
            continue
        order_seq += 1
        correlation_id = f"bt-port-{config.id}-{order_seq:06d}"
        side = Side.BUY if planned.side == "BUY" else Side.SELL
        # LIMIT 는 계획 가격(그날 종가) 지정가 — 라이브 marketable-limit 채널의
        # 일봉 수준 근사. MARKET 이면 종전대로 가격 미지정(보수적 체결 모델).
        limit_price = None if use_market else bar.close
        limit_price_str = str(limit_price) if limit_price is not None else None
        request = OrderRequest(
            account=account,
            symbol=planned.symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            limit_price_usd=limit_price,
        )

        audit.append(
            conn,
            OrderIntentPayload(
                rule_id=config.id,
                symbol=planned.symbol,
                side=side.value,
                order_type=order_type.value,
                qty=qty,
                limit_price_usd=limit_price_str,
            ),
            rule_id=config.id,
            symbol=planned.symbol,
            correlation_id=correlation_id,
            ts_utc=ts_iso,
        )

        # BUYs run the full K1 chain (caps bind); SELLs reduce exposure so only
        # whitelist + halt apply (mirrors the router's asymmetry).
        deny = _gate_buy(
            request,
            caps=caps,
            whitelist=whitelist,
            halt_path=halt_path,
            equity=equity,
            price=bar.close,
            portfolio=portfolio,
            prices=prices_today,
        ) if side is Side.BUY else _gate_sell(
            request, whitelist=whitelist, halt_path=halt_path
        )
        if deny is not None:
            rejections.append(
                GateRejectionRecord(
                    correlation_id=correlation_id,
                    rule_id=config.id,
                    symbol=planned.symbol,
                    gate=deny[0],
                    reason=deny[1],
                    ts_utc=ts_iso,
                )
            )
            audit.append(
                conn,
                OrderRejectedByGatePayload(gate=deny[0], reason=deny[1], metadata={}),
                rule_id=config.id,
                symbol=planned.symbol,
                correlation_id=correlation_id,
                ts_utc=ts_iso,
            )
            orders.append(
                OrderRecord(
                    correlation_id=correlation_id,
                    rule_id=config.id,
                    symbol=planned.symbol,
                    side=side.value,
                    order_type=order_type.value,
                    qty=qty,
                    limit_price_usd=limit_price_str,
                    state="REJECTED_BY_GATE",
                    ts_utc=ts_iso,
                    kis_order_id=None,
                    gate=deny[0],
                    reason=deny[1],
                )
            )
            continue

        outcome = broker.submit_order(
            request, now=clock.now(), bar=bar, time_in_force="DAY"
        )
        audit.append(
            conn,
            OrderSubmittedPayload(
                kis_order_id=outcome.result.kis_order_id, submitted_at_utc=ts_iso
            ),
            rule_id=config.id,
            symbol=planned.symbol,
            correlation_id=correlation_id,
            ts_utc=ts_iso,
        )
        orders.append(
            OrderRecord(
                correlation_id=correlation_id,
                rule_id=config.id,
                symbol=planned.symbol,
                side=side.value,
                order_type=order_type.value,
                qty=qty,
                limit_price_usd=limit_price_str,
                state="SUBMITTED",
                ts_utc=ts_iso,
                kis_order_id=outcome.result.kis_order_id,
            )
        )
        if outcome.fill is not None:
            f = outcome.fill
            eff_price = cost_model.effective_fill_price(f.side, f.fill_price_usd)
            commission = cost_model.commission_usd(f.qty, eff_price)
            audit.append(
                conn,
                FillPayload(
                    kis_fill_id=f.kis_fill_id,
                    qty=f.qty,
                    price_usd=str(eff_price),
                    executed_at_utc=ts_iso,
                ),
                rule_id=config.id,
                symbol=planned.symbol,
                correlation_id=correlation_id,
                ts_utc=ts_iso,
            )
            fills.append(
                FillRecord(
                    correlation_id=correlation_id,
                    rule_id=config.id,
                    symbol=planned.symbol,
                    side=f.side.value,
                    qty=f.qty,
                    fill_price_usd=str(eff_price),
                    executed_at_utc=ts_iso,
                    kis_fill_id=f.kis_fill_id,
                )
            )
            # Settle cash + position.
            if f.side is Side.BUY:
                portfolio.cash_usd -= Decimal(f.qty) * eff_price + commission
                portfolio.positions[planned.symbol] = portfolio.qty(planned.symbol) + f.qty
            else:
                portfolio.cash_usd += Decimal(f.qty) * eff_price - commission
                portfolio.positions[planned.symbol] = portfolio.qty(planned.symbol) - f.qty
                if portfolio.positions[planned.symbol] <= 0:
                    portfolio.positions.pop(planned.symbol, None)

    # Clear any unfilled DAY orders (rare for liquid MARKET orders).
    broker.expire_day_orders(now=clock.now())
    return order_seq


def _gate_buy(
    request: OrderRequest,
    *,
    caps: SizingCaps,
    whitelist: Whitelist,
    halt_path: Path,
    equity: Decimal,
    price: Decimal,
    portfolio: _Portfolio,
    prices: dict[str, Decimal],
) -> tuple[str, str] | None:
    symbol_exposure = Decimal(portfolio.qty(request.symbol)) * price
    global_exposure = sum(
        (Decimal(q) * prices.get(s, Decimal("0")) for s, q in portfolio.positions.items()),
        Decimal("0"),
    )
    decision = _run_gate_chain(
        request,
        caps=caps,
        whitelist=whitelist,
        halt_path=halt_path,
        total_capital_usd=equity,
        quote_price_usd=price,
        current_symbol_exposure_usd=symbol_exposure,
        current_global_exposure_usd=global_exposure,
    )
    if decision is None:
        return None
    return (decision.gate, decision.reason or "no reason")


def _gate_sell(
    request: OrderRequest, *, whitelist: Whitelist, halt_path: Path
) -> tuple[str, str] | None:
    from auto_invest.risk.gates import halt_gate, whitelist_gate

    for gate_fn, kwargs in (
        (whitelist_gate, {"whitelist": whitelist}),
        (halt_gate, {"halt_path": halt_path}),
    ):
        decision = gate_fn(request, **kwargs)
        if not decision.allow:
            return (decision.gate, decision.reason or "no reason")
    return None


def _sum_commission(
    fills: Sequence[FillRecord], cost_model: BacktestCostModel
) -> Decimal:
    total = Decimal("0")
    for fr in fills:
        total += cost_model.commission_usd(fr.qty, Decimal(fr.fill_price_usd))
    return total


__all__ = [
    "PortfolioReplayResult",
    "replay_portfolio",
]
