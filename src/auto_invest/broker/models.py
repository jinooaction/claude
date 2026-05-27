"""Broker domain models — auto-invest's internal abstraction over KIS.

Each KIS endpoint wrapper in `broker/overseas.py` translates between
these pydantic models and KIS's literal JSON shapes. Strategy and
execution code consumes only these models so a future broker swap
would only require a new adapter.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from auto_invest.config.enums import OrderType, Side


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account: str
    symbol: str
    side: Side
    order_type: OrderType
    qty: int = Field(..., gt=0)
    limit_price_usd: Decimal | None = None
    # `limit_price_usd` is required for LIMIT and ignored for MARKET.
    # The order router validates this before constructing the request.


class OrderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kis_order_id: str
    accepted_at_utc: datetime


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    symbol: str
    last_price_usd: Decimal
    bid_usd: Decimal | None = None
    ask_usd: Decimal | None = None
    quoted_at_utc: datetime


class PositionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    symbol: str
    qty: int
    avg_cost_usd: Decimal


class BalanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account: str
    cash_usd: Decimal
    total_value_usd: Decimal
    fetched_at_utc: datetime


class BrokerExecution(BaseModel):
    """브로커가 보고한 한 주문의 체결 상태(정규화). spec 015.

    `filled_qty`는 **누적** 체결량이다(부분 체결이 여러 번이면 합계).
    `avg_fill_price_usd`는 그 누적 체결의 평균 체결가. `terminal`은 브로커가
    해당 주문을 더 이상 열려 있지 않다(취소/만료/거부)고 명시적으로 보고할 때만
    True — 모르면 False(보수적: 추측으로 종료 전이하지 않음)."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    kis_order_id: str
    symbol: str
    filled_qty: int = Field(..., ge=0)
    avg_fill_price_usd: Decimal
    unfilled_qty: int | None = None
    side: Side | None = None
    terminal: bool = False
