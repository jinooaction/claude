"""Shared StrEnum types used across the config package.

Kept separate from `caps`/`whitelist`/`rules` so we don't rely on
import order for type identity (e.g. `OrderType` from whitelist matches
`OrderType` referenced from action models).
"""

from __future__ import annotations

from enum import StrEnum


class OrderType(StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class Session(StrEnum):
    REGULAR = "REGULAR"
    EXTENDED = "EXTENDED"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class StrategyStage(StrEnum):
    BACKTEST = "BACKTEST"
    CANARY = "CANARY"
    FULL_LIVE = "FULL_LIVE"
