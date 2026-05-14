"""In-memory broker mock for the backtest engine (T016).

Implements `BacktestBroker` per data-model.md § BacktestBroker, with
pessimistic zero-slippage limit-order fills per research.md R-B3:

    BUY  fills at min(limit, bar.open) iff bar.low  <= limit AND bar.volume >= qty.
    SELL fills at max(limit, bar.open) iff bar.high >= limit AND bar.volume >= qty.

No partial fills in v1. DAY orders that did not fill in their submission
bar are cancelled at session close; GTC orders persist into the next
session and are re-attempted against subsequent bars.

Defense-in-depth boundary (FR-B06): every artefact emitted by this module
carries `adapter_id == "backtest-mock-v1"`. The router calling
`assert_backtest_adapter` with the adapter id of any concrete broker
fails fast if a non-mock leaked into the replay loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from auto_invest.broker.models import OrderRequest, OrderResult
from auto_invest.config.enums import OrderType, Side

from .data_model import OHLCVBar

ADAPTER_ID: Literal["backtest-mock-v1"] = "backtest-mock-v1"

TimeInForce = Literal["DAY", "GTC"]


class BacktestLiveBrokerLeakError(RuntimeError):
    """Raised when a non-mock broker adapter reaches the router during a backtest."""


def assert_backtest_adapter(adapter_id: str) -> None:
    """FR-B06 router-side check. Raises if the adapter is not the mock."""
    if adapter_id != ADAPTER_ID:
        raise BacktestLiveBrokerLeakError(
            f"non-mock broker adapter {adapter_id!r} reached the router during backtest; "
            f"expected {ADAPTER_ID!r}"
        )


@dataclass(frozen=True)
class FillEvent:
    """One fill produced by the mock broker."""

    kis_fill_id: str
    kis_order_id: str
    symbol: str
    side: Side
    qty: int
    fill_price_usd: Decimal
    executed_at_utc: datetime


@dataclass(frozen=True)
class OpenOrder:
    """A working order that has not filled yet."""

    kis_order_id: str
    request: OrderRequest
    submitted_at_utc: datetime
    time_in_force: TimeInForce


@dataclass(frozen=True)
class SubmitOutcome:
    """Result of a `submit_order` call.

    Either a fill happened in the submission bar (`fill is not None` and
    `open_order is None`) or the order is now working (`open_order is not None`,
    `fill is None`). `result` is always populated so the caller has a
    broker-issued id to use in audit rows.
    """

    result: OrderResult
    fill: FillEvent | None
    open_order: OpenOrder | None


def _compute_fill_price(
    request: OrderRequest, bar: OHLCVBar
) -> Decimal | None:
    """Apply R-B3 to (request, bar). Returns fill price or None if untouched.

    MARKET orders fill at the conservative side of the bar (BUY at high,
    SELL at low) iff bar.volume >= qty. v1 LIMIT semantics: BUY fills at
    min(limit, bar.open) iff bar.low <= limit; SELL fills at max(limit,
    bar.open) iff bar.high >= limit. Volume gate applies to both.
    """
    if bar.volume < request.qty:
        return None

    if request.order_type is OrderType.LIMIT:
        limit = request.limit_price_usd
        if limit is None:
            return None
        if request.side is Side.BUY:
            if bar.low > limit:
                return None
            return min(limit, bar.open)
        if bar.high < limit:
            return None
        return max(limit, bar.open)
    # MARKET — defensive worst-case
    return bar.high if request.side is Side.BUY else bar.low


@dataclass
class BacktestBroker:
    """Bar-driven in-memory broker.

    Lifecycle per replay tick (per (session_date, rule)):

      1. `submit_order(req, now=, bar=)` for each newly-routed order.
      2. After all submissions for the bar, the engine calls
         `try_fill_open_orders(bar, now=)` to re-attempt working GTC/DAY
         orders against this bar.
      3. At session close the engine calls `expire_day_orders(now=)`.

    The broker does not depend on the audit log; the engine is responsible
    for emitting the matching ORDER_SUBMITTED/FILL/CANCEL audit rows so
    the audit-log shape is identical to live trading.
    """

    adapter_id: Literal["backtest-mock-v1"] = ADAPTER_ID
    _open_orders: dict[str, OpenOrder] = field(default_factory=dict)
    _fills: list[FillEvent] = field(default_factory=list)
    _order_seq: int = 0
    _fill_seq: int = 0

    def _next_order_id(self) -> str:
        """Deterministic broker order id — required for FR-B15 byte-stability."""
        self._order_seq += 1
        return f"BT-ORD-{self._order_seq:08d}"

    def _next_fill_id(self) -> str:
        self._fill_seq += 1
        return f"BT-FILL-{self._fill_seq:08d}"

    def submit_order(
        self,
        req: OrderRequest,
        *,
        now: datetime,
        bar: OHLCVBar,
        time_in_force: TimeInForce = "DAY",
    ) -> SubmitOutcome:
        if bar.symbol != req.symbol:
            raise ValueError(
                f"bar.symbol {bar.symbol!r} does not match request.symbol {req.symbol!r}"
            )

        kis_order_id = self._next_order_id()
        result = OrderResult(kis_order_id=kis_order_id, accepted_at_utc=now)

        fill_price = _compute_fill_price(req, bar)
        if fill_price is not None:
            fill = FillEvent(
                kis_fill_id=self._next_fill_id(),
                kis_order_id=kis_order_id,
                symbol=req.symbol,
                side=req.side,
                qty=req.qty,
                fill_price_usd=fill_price,
                executed_at_utc=now,
            )
            self._fills.append(fill)
            return SubmitOutcome(result=result, fill=fill, open_order=None)

        open_order = OpenOrder(
            kis_order_id=kis_order_id,
            request=req,
            submitted_at_utc=now,
            time_in_force=time_in_force,
        )
        self._open_orders[kis_order_id] = open_order
        return SubmitOutcome(result=result, fill=None, open_order=open_order)

    def try_fill_open_orders(
        self, bar: OHLCVBar, *, now: datetime
    ) -> list[FillEvent]:
        """Re-attempt every open order whose symbol matches `bar`. Returns fills."""
        filled: list[FillEvent] = []
        for kis_order_id, order in list(self._open_orders.items()):
            if order.request.symbol != bar.symbol:
                continue
            fill_price = _compute_fill_price(order.request, bar)
            if fill_price is None:
                continue
            fill = FillEvent(
                kis_fill_id=self._next_fill_id(),
                kis_order_id=kis_order_id,
                symbol=order.request.symbol,
                side=order.request.side,
                qty=order.request.qty,
                fill_price_usd=fill_price,
                executed_at_utc=now,
            )
            self._fills.append(fill)
            filled.append(fill)
            del self._open_orders[kis_order_id]
        return filled

    def expire_day_orders(self, *, now: datetime) -> list[OpenOrder]:
        """Cancel every DAY order. Returns the cancelled orders for audit emission.

        Called by the engine at the bar's session-close instant. GTC orders
        survive and roll into the next bar.
        """
        expired: list[OpenOrder] = []
        for kis_order_id, order in list(self._open_orders.items()):
            if order.time_in_force == "DAY":
                expired.append(order)
                del self._open_orders[kis_order_id]
        return expired

    def cancel_order(self, kis_order_id: str) -> OpenOrder | None:
        """Operator-initiated cancel. Returns the cancelled order or None."""
        return self._open_orders.pop(kis_order_id, None)

    def list_open_orders(self) -> list[OpenOrder]:
        return list(self._open_orders.values())

    def fills(self) -> list[FillEvent]:
        """All fills produced by this broker, in chronological order."""
        return list(self._fills)


__all__ = [
    "ADAPTER_ID",
    "BacktestBroker",
    "BacktestLiveBrokerLeakError",
    "FillEvent",
    "OpenOrder",
    "SubmitOutcome",
    "TimeInForce",
    "assert_backtest_adapter",
]
