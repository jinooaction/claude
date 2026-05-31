"""Order router (T042) — the gate-and-broker pipeline for one trigger.

For each fired trigger the router:

  1. Resolves the limit-price expression (`evaluate_limit_price`).
  2. Builds an `OrderRequest` and writes the ORDER_INTENT audit row.
  3. Inserts a row into `orders` (state=INTENT) and a matching
     `order_state_history` row.
  4. Runs the gates from `risk/gates.py` in declared order; the first
     Deny short-circuits with an ORDER_REJECTED_BY_GATE audit row and
     the order's state moves to REJECTED_BY_GATE.
  5. Submits to the broker via `broker/overseas.place_order`.
     Broker errors transition the order to REJECTED_BY_BROKER and
     surface an OrderRejectedByBroker audit row.
  6. On success, writes ORDER_SUBMITTED and stores the broker id.

The router also exposes `verify_stage_uniqueness` for the worker to
call at startup against the rules-being-loaded plus the audit log's
last known stage per (rule_id, symbol).
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.models import OrderRequest
from auto_invest.broker.overseas import place_order
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.lifecycle import marketable_limit_price
from auto_invest.judgment.points.news_screen import should_block_buy
from auto_invest.judgment.points.volatility import apply_volatility_advisory
from auto_invest.judgment.schemas import NewsAdvisory, VolatilityAdvisory
from auto_invest.market_data.store import get_bars, get_latest_bar
from auto_invest.persistence import audit
from auto_invest.persistence.audit import (
    JudgmentAdvisoryAppliedPayload,
    OrderIntentPayload,
    OrderPaperFilledPayload,
    OrderRejectedByBrokerPayload,
    OrderRejectedByGatePayload,
    OrderSubmittedPayload,
)
from auto_invest.risk.gates import (
    GateDecision,
    global_exposure_gate,
    halt_gate,
    per_symbol_cap_gate,
    per_trade_cap_gate,
    stage_uniqueness_gate,
    whitelist_gate,
)
from auto_invest.strategy.factors import composite_scores
from auto_invest.strategy.quality import quality_ranked
from auto_invest.strategy.ranking import cross_sectional_momentum
from auto_invest.strategy.regime import (
    DEFAULT_REGIME_SCALE,
    apply_regime_scale,
)
from auto_invest.strategy.regime import (
    detect as detect_regime,
)
from auto_invest.strategy.sizing import (
    SizingGroupMember,
    erc_group_scales,
    group_scale_for,
    max_sharpe_group_scales,
    min_variance_group_scales,
    realized_volatility,
    sized_quantity_with_result,
)


@dataclass(frozen=True)
class OrderOutcome:
    state: str
    correlation_id: str
    kis_order_id: str | None = None
    gate: str | None = None
    reason: str | None = None


def _choose_paper_fill_price(
    *,
    side: Side,
    quote_price_usd: Decimal,
    quote_ask_usd: Decimal | None,
    quote_bid_usd: Decimal | None,
) -> tuple[Decimal, str]:
    """Spec 009 FR-007 — 매수 ask / 매도 bid / 폴백 last.

    아무 quote 필드도 양수가 아니면 quote_price_usd(last)를 그대로 폴백한다.
    이 함수는 paper 분기에서만 호출되며 live 코드 패스에는 영향이 없다.
    """
    if side is Side.BUY and quote_ask_usd is not None and quote_ask_usd > 0:
        return quote_ask_usd, "ask"
    if side is Side.SELL and quote_bid_usd is not None and quote_bid_usd > 0:
        return quote_bid_usd, "bid"
    return quote_price_usd, "last"


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# ----------------------------------------------------------- limit-price expr


_TRIGGER_OFFSET_RE = re.compile(r"^trigger\s*([+\-])\s*([\d.]+)$")
_LAST_CLOSE_FACTOR_RE = re.compile(r"^last_close\s*\*\s*([\d.]+)$")


class LimitPriceExprError(ValueError):
    """Raised when a limit_price expression cannot be evaluated."""


def evaluate_limit_price(
    expr: str,
    *,
    trigger_price: Decimal,
    last_close: Decimal | None,
) -> Decimal:
    """Resolve `expr` to a Decimal using the supported v1 grammar.

    Supported forms:
        "180.00"               -> literal Decimal
        "trigger - 0.10"       -> trigger price plus or minus a constant
        "trigger + 0.05"
        "last_close * 1.001"   -> latest close times a factor
    """
    text = expr.strip()
    try:
        return Decimal(text)
    except InvalidOperation:
        pass
    match = _TRIGGER_OFFSET_RE.match(text)
    if match:
        op, n = match.group(1), Decimal(match.group(2))
        return trigger_price + n if op == "+" else trigger_price - n
    match = _LAST_CLOSE_FACTOR_RE.match(text)
    if match:
        if last_close is None:
            raise LimitPriceExprError(
                f"limit_price expression {expr!r} requires last_close but none is available"
            )
        return last_close * Decimal(match.group(1))
    raise LimitPriceExprError(f"unsupported limit_price expression: {expr!r}")


# ----------------------------------------------------------- orders helpers


def _insert_intent(
    conn: sqlite3.Connection,
    *,
    correlation_id: str,
    rule_id: str,
    request: OrderRequest,
) -> None:
    conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty,
             limit_price_usd, state)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'INTENT')
        """,
        (
            correlation_id,
            rule_id,
            request.symbol,
            request.side.value,
            request.order_type.value,
            request.qty,
            (str(request.limit_price_usd) if request.limit_price_usd is not None else None),
        ),
    )
    _record_transition(conn, correlation_id, None, "INTENT", None)


def _record_transition(
    conn: sqlite3.Connection,
    correlation_id: str,
    from_state: str | None,
    to_state: str,
    reason: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO order_state_history
            (order_correlation_id, from_state, to_state, ts_utc, reason)
        VALUES (?, ?, ?, ?, ?)
        """,
        (correlation_id, from_state, to_state, _utcnow_iso_ms(), reason),
    )
    conn.execute(
        "UPDATE orders SET state = ?, final_state_at_utc = ? WHERE correlation_id = ?",
        (to_state, _utcnow_iso_ms(), correlation_id),
    )


def _set_kis_order_id(
    conn: sqlite3.Connection,
    correlation_id: str,
    kis_order_id: str,
    submitted_at_utc: str,
) -> None:
    conn.execute(
        """
        UPDATE orders SET kis_order_id = ?, submitted_at_utc = ?
        WHERE correlation_id = ?
        """,
        (kis_order_id, submitted_at_utc, correlation_id),
    )


# ----------------------------------------------------------- stage uniqueness


def verify_stage_uniqueness(rules: list[TradingRule]) -> list[GateDecision]:
    """Run `stage_uniqueness_gate` for every rule against the current set.

    Returns one GateDecision per rule, in the same order. Callers
    typically refuse to start the worker if any decision denies.
    """
    active_by_symbol: dict[str, dict[str, StrategyStage]] = {}
    for rule in rules:
        active_by_symbol.setdefault(rule.symbol, {})[rule.id] = rule.stage

    decisions: list[GateDecision] = []
    for rule in rules:
        decision = stage_uniqueness_gate(
            rule_id=rule.id,
            symbol=rule.symbol,
            proposed_stage=rule.stage,
            active_stages_for_symbol=active_by_symbol[rule.symbol],
        )
        decisions.append(decision)
    return decisions


# ----------------------------------------------------------- main router


@dataclass
class OrderRouter:
    """Stateless-ish router: holds configuration handles, no per-call state.

    spec 009: `paper_mode=True`로 만들면 broker 주문 호출(line 347 부근의
    `place_order(self.broker, ...)`) 직전에 단일 차단 지점에서 시뮬 체결로
    분기한다. 게이트 체인은 live와 동일 코드로 평가되며, paper 모드는
    `orders`/`order_transitions` 테이블에 row를 추가하지 않아 SC-006을
    만족한다.
    """

    conn: sqlite3.Connection
    broker: ResilientClient
    access_token: str
    app_key: str
    app_secret: str
    account_no: str
    whitelist: Whitelist
    caps: SizingCaps
    halt_path: Path
    market: str = "NASD"
    quote_market: str = "NAS"
    paper_mode: bool = False
    paper_session_id: int | None = None
    # Spec 017 slice 2b: inverse-vol risk-parity group membership, built by the
    # worker from the static rule set (build_sizing_groups). None/empty -> no
    # grouping -> sizing is byte-equal to slices 1/2.
    sizing_groups: Mapping[str, Sequence[SizingGroupMember]] | None = None

    def _group_scale(self, rule: TradingRule) -> Decimal:
        """Down-only group weight for ``rule`` — inverse_vol (slice 2b) or ERC (spec 020).

        Returns 1 when the rule has no group sizing — byte-equal to slices 1/2.
        """
        sizing = rule.sizing
        if sizing is None or rule.sizing_group is None:
            return Decimal(1)
        if sizing.mode == "inverse_vol":
            members = (self.sizing_groups or {}).get(rule.sizing_group, ())
            strength = sizing.correlation_haircut
            member_vols: dict[str, Decimal | None] = {}
            closes_by_rule: dict[str, dict[date, Decimal]] = {}
            for member in members:
                bars = get_bars(self.conn, symbol=member.symbol, timeframe=member.timeframe)
                closes = [b.close_usd for b in bars]
                member_vols[member.rule_id] = realized_volatility(
                    closes[-(member.lookback_bars + 1) :]
                )
                if strength > 0:
                    closes_by_rule[member.rule_id] = {
                        date.fromisoformat(b.bar_open_utc[:10]): b.close_usd for b in bars
                    }
            return group_scale_for(
                rule.id,
                member_vols=member_vols,
                closes_by_rule=closes_by_rule if strength > 0 else None,
                lookback_bars=sizing.lookback_bars,
                correlation_strength=strength,
            )
        if sizing.mode in ("erc", "min_variance", "max_sharpe"):
            members = (self.sizing_groups or {}).get(rule.sizing_group, ())
            closes_by_rule_mv: dict[str, dict[date, Decimal]] = {}
            member_vols_mv: dict[str, Decimal | None] = {}
            for member in members:
                bars = get_bars(self.conn, symbol=member.symbol, timeframe=member.timeframe)
                closes = [b.close_usd for b in bars]
                closes_by_rule_mv[member.rule_id] = {
                    date.fromisoformat(b.bar_open_utc[:10]): b.close_usd for b in bars
                }
                member_vols_mv[member.rule_id] = realized_volatility(
                    closes[-(member.lookback_bars + 1) :]
                )
            if sizing.mode == "max_sharpe":
                scale_fn = max_sharpe_group_scales
            elif sizing.mode == "min_variance":
                scale_fn = min_variance_group_scales
            else:
                scale_fn = erc_group_scales
            weights = scale_fn(
                closes_by_rule_mv,
                lookback_bars=sizing.lookback_bars,
                member_vols=member_vols_mv,
            )
            return weights.get(rule.id, Decimal(1))
        return Decimal(1)

    # kept as alias so any external callers (tests) don't break immediately
    def _inverse_vol_group_scale(self, rule: TradingRule) -> Decimal:
        return self._group_scale(rule)

    async def submit_order(
        self,
        *,
        rule: TradingRule,
        quote_price_usd: Decimal,
        total_capital_usd: Decimal,
        current_symbol_exposure_usd: Decimal,
        current_global_exposure_usd: Decimal,
        quote_ask_usd: Decimal | None = None,
        quote_bid_usd: Decimal | None = None,
        volatility_advisory: VolatilityAdvisory | None = None,
        news_advisory: NewsAdvisory | None = None,
        judgment_correlation_id: str | None = None,
        news_correlation_id: str | None = None,
    ) -> OrderOutcome:
        correlation_id = f"ord-{uuid.uuid4().hex[:12]}"

        # Spec 017: deterministic volatility-based sizing BEFORE advisories and
        # the gate chain. The sizer scales the rule's declared qty by realized
        # volatility — down by default, or up within the operator's max_scale when
        # bidirectional targeting is on (slice 2). Either way the K1 caps
        # (risk/gates.py) run unchanged below and REJECT anything over the
        # per-trade / per-symbol / global ceiling, so sizing can never lift
        # exposure above the safety ceiling — K1 is the true cap. A sized base of
        # < 1 means the throttle fully suppressed this order (FR-S05); no qty=0
        # order is ever built. fixed/None sizing returns the declared qty (v1).
        base_qty = rule.action.qty
        if rule.sizing is not None and rule.sizing.mode != "fixed":
            sizing_timeframe = getattr(rule.trigger, "timeframe", "1d")
            recent_bars = get_bars(
                self.conn, symbol=rule.symbol, timeframe=sizing_timeframe
            )
            _group_scale = self._group_scale(rule)
            sizing_result = sized_quantity_with_result(
                base_qty=rule.action.qty,
                closes=[b.close_usd for b in recent_bars],
                sizing=rule.sizing,
                group_scale=_group_scale,
            )
            audit.append(
                self.conn,
                audit.SizingDecisionPayload(
                    sizing_mode=sizing_result.sizing_mode,
                    base_qty=sizing_result.base_qty,
                    final_qty=sizing_result.final_qty,
                    realized_vol_pct=(
                        str(sizing_result.realized_vol_pct)
                        if sizing_result.realized_vol_pct is not None
                        else None
                    ),
                    vol_scale=(
                        str(sizing_result.vol_scale)
                        if sizing_result.vol_scale is not None
                        else None
                    ),
                    group_scale=str(sizing_result.group_scale),
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=correlation_id,
            )
            base_qty = sizing_result.final_qty
            if base_qty < 1:
                return OrderOutcome(
                    state="SKIPPED_BY_SIZING",
                    correlation_id=correlation_id,
                    reason="volatility_throttle",
                )

        # Spec 020: regime scale — applied after vol/ERC sizing, before judgment.
        if rule.regime_index_symbol is not None:
            sizing_timeframe_for_regime = getattr(rule.trigger, "timeframe", "1d")
            index_bars = get_bars(
                self.conn,
                symbol=rule.regime_index_symbol,
                timeframe=sizing_timeframe_for_regime,
            )
            regime = detect_regime(index_bars)
            scale_map = rule.regime_scale or {}
            regime_scale = (
                Decimal(str(scale_map[regime.value]))
                if regime.value in scale_map
                else DEFAULT_REGIME_SCALE[regime]
            )
            base_qty = apply_regime_scale(base_qty, regime_scale)
            if base_qty < 1:
                return OrderOutcome(
                    state="SKIPPED_BY_SIZING",
                    correlation_id=correlation_id,
                    reason="regime_zero",
                )

        # Spec 021: cross-sectional ranking filter — applied after regime scale,
        # before judgment. Fetches bars for the full universe, ranks by N-period
        # momentum, and skips this symbol when it falls outside the top-N / top-pct
        # threshold. Opt-in: ranking_filter=None leaves the path byte-identical.
        if rule.ranking_filter is not None:
            rf = rule.ranking_filter
            sizing_tf = getattr(rule.trigger, "timeframe", "1d")
            universe_bars = {
                sym: get_bars(self.conn, symbol=sym, timeframe=sizing_tf)
                for sym in rf.universe
            }
            ranked = cross_sectional_momentum(universe_bars, rf.period)
            if not rf.qualifies(rule.symbol, ranked):
                return OrderOutcome(
                    state="SKIPPED_BY_RANKING",
                    correlation_id=correlation_id,
                    reason="not_in_top",
                )

        # Spec 023: quality factor filter — applied after ranking filter.
        # Opts-in: quality_filter=None leaves the path byte-identical.
        if rule.quality_filter is not None:
            qf = rule.quality_filter
            sizing_tf = getattr(rule.trigger, "timeframe", "1d")
            universe_pricebars = {
                sym: get_bars(self.conn, symbol=sym, timeframe=sizing_tf)
                for sym in qf.universe
            }
            ranked_quality = quality_ranked(universe_pricebars, lookback_bars=qf.lookback_bars)
            if not qf.qualifies(rule.symbol, ranked_quality):
                return OrderOutcome(
                    state="SKIPPED_BY_QUALITY",
                    correlation_id=correlation_id,
                    reason="not_in_top_quality",
                )

        # Spec 025: multi-factor composite filter — applied after quality filter.
        # Ranks the universe by a weighted, cross-sectionally z-scored blend of
        # factors and skips this symbol when it falls outside the top-N / top-pct
        # threshold. Opt-in: composite_filter=None leaves the path byte-identical.
        if rule.composite_filter is not None:
            cf = rule.composite_filter
            sizing_tf = getattr(rule.trigger, "timeframe", "1d")
            universe_composite = {
                sym: get_bars(self.conn, symbol=sym, timeframe=sizing_tf)
                for sym in cf.universe
            }
            ranked_composite = composite_scores(
                universe_composite,
                weights=cf.weights,
                lookback_bars=cf.lookback_bars,
                momentum_period=cf.momentum_period,
                bb_period=cf.bb_period,
                bb_std=cf.bb_std,
            )
            if not cf.qualifies(rule.symbol, ranked_composite):
                return OrderOutcome(
                    state="SKIPPED_BY_COMPOSITE",
                    correlation_id=correlation_id,
                    reason="not_in_top_composite",
                )

        # Spec 004: consume judgment advisories BEFORE the gate chain. Advisories
        # can only shrink, block, or skip the order — never enlarge it — so K1
        # position caps (risk/gates.py) still bind unchanged below. Only canary-
        # stage rules consume advisories (constitution VI); full-live rules behave
        # as v1 until the judgment point is promoted.
        effective_qty = base_qty
        canary_cohort = rule.stage is StrategyStage.CANARY
        _judgment_on = (
            rule.judgment is not None and rule.judgment.enabled and canary_cohort
        )

        # news_screen: bear+고신뢰면 당일 신규 매수 보류(가장 보수적 — 전체 skip).
        if _judgment_on and news_advisory is not None:
            block = should_block_buy(
                news_advisory,
                side=rule.action.side,
                block_min_confidence=rule.judgment.block_min_confidence,
                block_buy_stance=rule.judgment.block_buy_stance,
            )
            audit.append(
                self.conn,
                JudgmentAdvisoryAppliedPayload(
                    decision_class="news_screen",
                    advisory=f"{news_advisory.stance}@{news_advisory.confidence:.2f}",
                    applied_decision="block_buy" if block else "no_effect",
                    canary_cohort=canary_cohort,
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=news_correlation_id or correlation_id,
            )
            if block:
                return OrderOutcome(
                    state="SKIPPED_BY_JUDGMENT",
                    correlation_id=correlation_id,
                    reason="news_block_buy",
                )

        if volatility_advisory is not None and _judgment_on:
            decision = apply_volatility_advisory(
                volatility_advisory,
                qty=base_qty,
                halt_min_confidence=rule.judgment.halt_min_confidence,
                size_down_factor=rule.judgment.size_down_factor,
            )
            audit.append(
                self.conn,
                JudgmentAdvisoryAppliedPayload(
                    decision_class="volatility_assessment",
                    advisory=decision.advisory_summary,
                    applied_decision=decision.applied_decision,
                    canary_cohort=canary_cohort,
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=judgment_correlation_id or correlation_id,
            )
            if decision.skip:
                return OrderOutcome(
                    state="SKIPPED_BY_JUDGMENT",
                    correlation_id=correlation_id,
                    reason=decision.applied_decision,
                )
            effective_qty = decision.effective_qty

        # Resolve the limit price for LIMIT orders.
        limit_price: Decimal | None = None
        if rule.action.order_type is OrderType.LIMIT:
            # Spec 030 G3: marketable-limit — 룰이 marketable_limit_bps 를 켜면 시장가에
            # 가까운 공격적 지정가(매수=ask 위 / 매도=bid 아래)로 빠른 체결과 슬리피지
            # 상한을 동시에 얻는다. 필요한 호가가 없으면 None 이라 아래 표현식으로 자연
            # 폴백한다. marketable_limit_bps 가 None(기본)이면 이 블록을 건너뛰어 기존
            # limit_price 표현식 경로가 byte 동일하게 실행된다(FR-030-08).
            if (
                rule.lifecycle is not None
                and rule.lifecycle.marketable_limit_bps is not None
            ):
                limit_price = marketable_limit_price(
                    rule.action.side,
                    bid=quote_bid_usd,
                    ask=quote_ask_usd,
                    buffer_bps=rule.lifecycle.marketable_limit_bps,
                )
            if limit_price is None:
                timeframe = getattr(rule.trigger, "timeframe", "1d")
                latest = get_latest_bar(
                    self.conn, symbol=rule.symbol, timeframe=timeframe
                )
                try:
                    limit_price = evaluate_limit_price(
                        rule.action.limit_price,
                        trigger_price=quote_price_usd,
                        last_close=(latest.close_usd if latest else None),
                    )
                except LimitPriceExprError as exc:
                    return self._record_router_error(
                        correlation_id=correlation_id,
                        rule=rule,
                        reason=str(exc),
                    )

        request = OrderRequest(
            account=self.account_no,
            symbol=rule.symbol,
            side=rule.action.side,
            order_type=rule.action.order_type,
            qty=effective_qty,
            limit_price_usd=limit_price,
        )

        # Audit ORDER_INTENT and persist the orders row.
        # spec 028: 결정 순간의 시세(arrival price)와 호가를 함께 기록한다 — 체결 품질
        # (구현격차) 측정의 기준가. 주문 경로는 그 외 한 바이트도 바뀌지 않는다(측정 전용).
        audit.append(
            self.conn,
            OrderIntentPayload(
                rule_id=rule.id,
                symbol=rule.symbol,
                side=rule.action.side.value,
                order_type=rule.action.order_type.value,
                qty=effective_qty,
                limit_price_usd=str(limit_price) if limit_price is not None else None,
                decision_price_usd=str(quote_price_usd),
                decision_bid_usd=(str(quote_bid_usd) if quote_bid_usd is not None else None),
                decision_ask_usd=(str(quote_ask_usd) if quote_ask_usd is not None else None),
            ),
            rule_id=rule.id,
            symbol=rule.symbol,
            correlation_id=correlation_id,
        )
        # paper-mode는 orders/order_transitions 테이블을 건드리지 않아 SC-006을
        # 만족한다. 모든 paper 사실은 audit_log에만 누적된다.
        if not self.paper_mode:
            _insert_intent(
                self.conn,
                correlation_id=correlation_id,
                rule_id=rule.id,
                request=request,
            )

        # Run gate chain.
        gate_chain: tuple[tuple[Any, dict[str, Any]], ...] = (
            (whitelist_gate, {"whitelist": self.whitelist}),
            (halt_gate, {"halt_path": self.halt_path}),
            (
                per_trade_cap_gate,
                {
                    "caps": self.caps,
                    "total_capital_usd": total_capital_usd,
                    "quote_price_usd": quote_price_usd,
                },
            ),
            (
                per_symbol_cap_gate,
                {
                    "caps": self.caps,
                    "total_capital_usd": total_capital_usd,
                    "quote_price_usd": quote_price_usd,
                    "current_symbol_exposure_usd": current_symbol_exposure_usd,
                },
            ),
            (
                global_exposure_gate,
                {
                    "caps": self.caps,
                    "total_capital_usd": total_capital_usd,
                    "quote_price_usd": quote_price_usd,
                    "current_global_exposure_usd": current_global_exposure_usd,
                },
            ),
        )
        for gate_fn, kwargs in gate_chain:
            decision = gate_fn(request, **kwargs)
            if not decision.allow:
                audit.append(
                    self.conn,
                    OrderRejectedByGatePayload(
                        gate=decision.gate,
                        reason=decision.reason or "no reason",
                        metadata=decision.metadata,
                    ),
                    rule_id=rule.id,
                    symbol=rule.symbol,
                    correlation_id=correlation_id,
                )
                if not self.paper_mode:
                    _record_transition(
                        self.conn,
                        correlation_id,
                        "INTENT",
                        "REJECTED_BY_GATE",
                        decision.reason,
                    )
                return OrderOutcome(
                    state="REJECTED_BY_GATE",
                    correlation_id=correlation_id,
                    gate=decision.gate,
                    reason=decision.reason,
                )

        # spec 009 단일 차단 지점: paper-mode면 broker 호출 대신 시뮬 체결.
        # 이 위치(line 347 부근, 게이트 체인 통과 직후·broker 호출 직전)가
        # FR-004의 "단일 차단 지점"이다. 다른 경로로는 broker.order_*()가
        # 호출되지 않는다 (tests/integration/test_paper_order_router.py의
        # test_paper_mode_never_calls_broker가 monkeypatch RuntimeError로
        # 회귀를 가드한다).
        if self.paper_mode:
            fill_price, quote_source = _choose_paper_fill_price(
                side=rule.action.side,
                quote_price_usd=quote_price_usd,
                quote_ask_usd=quote_ask_usd,
                quote_bid_usd=quote_bid_usd,
            )
            audit.append(
                self.conn,
                OrderPaperFilledPayload(
                    rule_id=rule.id,
                    symbol=rule.symbol,
                    side=rule.action.side.value,
                    qty=effective_qty,
                    simulated_fill_price_usd=str(fill_price),
                    quote_source=quote_source,
                    correlation_id=correlation_id,
                    paper_session_id=self.paper_session_id or 0,
                    reference_price_usd=str(quote_price_usd),
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=correlation_id,
            )
            return OrderOutcome(
                state="PAPER_FILLED",
                correlation_id=correlation_id,
            )

        # Submit to broker.
        try:
            result = await place_order(
                self.broker,
                access_token=self.access_token,
                app_key=self.app_key,
                app_secret=self.app_secret,
                request=request,
                market=self.market,
            )
        except Exception as exc:  # noqa: BLE001 — translate to audit row
            audit.append(
                self.conn,
                OrderRejectedByBrokerPayload(
                    broker_code=type(exc).__name__,
                    broker_message=str(exc),
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=correlation_id,
            )
            _record_transition(
                self.conn,
                correlation_id,
                "INTENT",
                "REJECTED_BY_BROKER",
                str(exc),
            )
            return OrderOutcome(
                state="REJECTED_BY_BROKER",
                correlation_id=correlation_id,
                reason=str(exc),
            )

        # Success: audit + state transition + remember broker id.
        submitted_at = result.accepted_at_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        audit.append(
            self.conn,
            OrderSubmittedPayload(
                kis_order_id=result.kis_order_id,
                submitted_at_utc=submitted_at,
            ),
            rule_id=rule.id,
            symbol=rule.symbol,
            correlation_id=correlation_id,
        )
        _record_transition(self.conn, correlation_id, "INTENT", "SUBMITTED", None)
        _set_kis_order_id(self.conn, correlation_id, result.kis_order_id, submitted_at)
        return OrderOutcome(
            state="SUBMITTED",
            correlation_id=correlation_id,
            kis_order_id=result.kis_order_id,
        )

    def _record_router_error(
        self,
        *,
        correlation_id: str,
        rule: TradingRule,
        reason: str,
    ) -> OrderOutcome:
        from auto_invest.persistence.audit import ErrorPayload

        audit.append(
            self.conn,
            ErrorPayload(where="order_router", message=reason),
            rule_id=rule.id,
            symbol=rule.symbol,
            correlation_id=correlation_id,
        )
        return OrderOutcome(state="ERROR", correlation_id=correlation_id, reason=reason)
