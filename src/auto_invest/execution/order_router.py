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
from dataclasses import dataclass
from datetime import UTC, datetime
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
from auto_invest.market_data.store import get_latest_bar
from auto_invest.persistence import audit
from auto_invest.persistence.audit import (
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
    ) -> OrderOutcome:
        correlation_id = f"ord-{uuid.uuid4().hex[:12]}"

        # Resolve the limit-price expression for LIMIT orders.
        limit_price: Decimal | None = None
        if rule.action.order_type is OrderType.LIMIT:
            timeframe = getattr(rule.trigger, "timeframe", "1d")
            latest = get_latest_bar(self.conn, symbol=rule.symbol, timeframe=timeframe)
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
            qty=rule.action.qty,
            limit_price_usd=limit_price,
        )

        # Audit ORDER_INTENT and persist the orders row.
        audit.append(
            self.conn,
            OrderIntentPayload(
                rule_id=rule.id,
                symbol=rule.symbol,
                side=rule.action.side.value,
                order_type=rule.action.order_type.value,
                qty=rule.action.qty,
                limit_price_usd=str(limit_price) if limit_price is not None else None,
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
                    qty=rule.action.qty,
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
