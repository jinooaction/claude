"""Pluggable ingestion adapters (FR-D-003).

Adding a new vendor or asset class is one new file in this package
plus one entry in the operator's `config/data.toml`. Existing
adapters, the data store, and the backtest engine require no
changes.

Adapters import this module and call `register_adapter` at module
import time. The `ADAPTERS` registry maps adapter `name` to class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class InstrumentRef:
    """Identifies one instrument across the data layer."""
    asset_class: str
    venue: str
    symbol: str

    def __post_init__(self) -> None:
        # Normalise: asset_class/venue lowercased, symbol uppercased,
        # to match the data-store schema and ensure equality across
        # call sites.
        object.__setattr__(self, "asset_class", self.asset_class.lower())
        object.__setattr__(self, "venue", self.venue.lower())
        object.__setattr__(self, "symbol", self.symbol.upper())


@dataclass(frozen=True)
class BarRecord:
    instrument: InstrumentRef
    kind: str  # "ohlcv_1m" / "ohlcv_1h" / "ohlcv_1d" / "tick"
    bar_open_ts_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_adjusted: bool = False


@dataclass(frozen=True)
class EventRecord:
    kind: str
    instrument: InstrumentRef | None
    event_ts_utc: datetime
    payload: dict


@dataclass(frozen=True)
class CorporateActionRecord:
    instrument: InstrumentRef
    action_kind: str
    effective_ts_utc: datetime
    payload: dict


class IngestionAdapter(ABC):
    """A pluggable source of historical / event data."""

    name: str
    vendor: str
    supported_asset_classes: tuple[str, ...]
    supported_kinds: tuple[str, ...]
    needs_auth: bool = False

    @abstractmethod
    async def fetch_bars(
        self,
        instrument: InstrumentRef,
        kind: str,
        from_utc: datetime,
        to_utc: datetime,
    ) -> AsyncIterable[BarRecord]:
        """Yield bars in non-decreasing `bar_open_ts_utc` order."""

    @abstractmethod
    async def fetch_events(
        self,
        instrument: InstrumentRef | None,
        kind: str,
        from_utc: datetime,
        to_utc: datetime,
    ) -> AsyncIterable[EventRecord]:
        """Yield events in non-decreasing `event_ts_utc` order."""

    @abstractmethod
    async def fetch_corporate_actions(
        self,
        instrument: InstrumentRef,
        from_utc: datetime,
        to_utc: datetime,
    ) -> AsyncIterable[CorporateActionRecord]:
        """Yield corporate actions in non-decreasing `effective_ts_utc` order."""


ADAPTERS: dict[str, type[IngestionAdapter]] = {}


def register_adapter(cls: type[IngestionAdapter]) -> type[IngestionAdapter]:
    """Decorator. Registers `cls` under `cls.name` in `ADAPTERS`."""
    if not hasattr(cls, "name") or not isinstance(cls.name, str):
        raise TypeError("adapter must define a string `name` class attribute")
    if cls.name in ADAPTERS:
        raise ValueError(f"adapter {cls.name!r} already registered")
    ADAPTERS[cls.name] = cls
    return cls


def get_adapter(name: str) -> type[IngestionAdapter]:
    if name not in ADAPTERS:
        raise KeyError(
            f"adapter {name!r} not registered (known: {sorted(ADAPTERS.keys())})"
        )
    return ADAPTERS[name]


def list_adapters() -> list[str]:
    return sorted(ADAPTERS.keys())
