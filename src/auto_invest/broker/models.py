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
