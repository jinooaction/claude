# Contract: IngestionAdapter Interface

This contract documents the Python interface every ingestion adapter
must implement. Implemented in
`src/auto_invest/market_data/adapters/__init__.py`. Concrete
adapters live as siblings of that module and register themselves at
import time.

## Goals

- Adding a new vendor or new asset class is **one new file + one
  config entry**, with no edits to the data store, the backtest
  engine, or any other adapter (FR-D-003 / SC-001).
- Adapters cannot mutate existing rows. They only append, with
  `as_of_ts_utc = now`.
- Adapters share the existing resilience plumbing
  (retry / rate-limit / circuit breaker) from spec 001 (constitution
  VII).

## Python interface

```python
# src/auto_invest/market_data/adapters/__init__.py

from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class InstrumentRef:
    asset_class: str   # "equity" / "crypto" / "fx" / "future" / ...
    venue: str         # "nasdaq" / "binance" / ...
    symbol: str        # "AAPL" / "BTC-USD"


@dataclass(frozen=True)
class BarRecord:
    instrument: InstrumentRef
    kind: str          # "ohlcv_1m" / "ohlcv_1h" / "ohlcv_1d" / "tick"
    bar_open_ts_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_adjusted: bool


@dataclass(frozen=True)
class EventRecord:
    kind: str                  # "earnings_release" / "news_event" / ...
    instrument: InstrumentRef | None
    event_ts_utc: datetime
    payload: dict              # JSON-serialisable; validated per-kind by the store


@dataclass(frozen=True)
class CorporateActionRecord:
    instrument: InstrumentRef
    action_kind: str           # "split" / "cash_dividend" / "ticker_change" / ...
    effective_ts_utc: datetime
    payload: dict              # action-specific


class IngestionAdapter(ABC):
    """A pluggable source of historical / event data."""

    name: str                              # e.g., "kis_us_equity"
    vendor: str                            # e.g., "kis"
    supported_asset_classes: tuple[str, ...]
    supported_kinds: tuple[str, ...]
    needs_auth: bool                       # True if `register_secret()` is required

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
        """Yield events in non-decreasing `event_ts_utc` order. Adapters
        that do not provide events for a given kind raise NotImplementedError."""

    @abstractmethod
    async def fetch_corporate_actions(
        self,
        instrument: InstrumentRef,
        from_utc: datetime,
        to_utc: datetime,
    ) -> AsyncIterable[CorporateActionRecord]:
        """Yield corporate actions in non-decreasing effective date order."""


# Adapter registry: a module-level dict populated by adapter modules
# at import time. The CLI's `--adapter <name>` looks up here.
ADAPTERS: dict[str, type[IngestionAdapter]] = {}


def register_adapter(cls: type[IngestionAdapter]) -> type[IngestionAdapter]:
    """Decorator. Registers the adapter class under `cls.name`."""
    if cls.name in ADAPTERS:
        raise ValueError(f"adapter {cls.name!r} already registered")
    ADAPTERS[cls.name] = cls
    return cls
```

## Required behaviour for adapters

- **Idempotence**: re-running `data ingest` over the same window
  with the same adapter produces zero new rows in `historical_bars`
  for any `(asset_class, venue, symbol, kind, vendor, bar_open_ts_utc)`
  whose latest content matches the adapter's fresh fetch. A
  legitimate revision (e.g., late-arriving adjusted close) writes a
  new row with a fresh `as_of_ts_utc` — but only if the content
  actually differs.
- **Order**: yielded bars / events / actions are non-decreasing by
  their content timestamp. The store's writer is permitted to fail
  if order is violated (catches adapter bugs early).
- **Resilience**: HTTP-backed adapters wrap their calls with the
  shared `tenacity` retry, rate limiter, and circuit breaker
  utilities from `src/auto_invest/broker/`. Adapters MUST NOT roll
  their own retry loop.
- **Secrets**: adapters with `needs_auth=True` resolve credentials
  via the existing `Secrets` dataclass (spec 001 R-9). They MUST
  call `register_secret()` for any token / key string before it
  reaches a logger.
- **Calendar awareness**: adapters return data for the venue's
  trading sessions only. An adapter for an always-open venue (e.g.,
  the public crypto adapter) sets its venue's calendar to the
  always-open implementation; higher layers do not branch on
  asset class.

## Conformance test

A shared `tests/integration/ingestion/test_adapter_conformance.py`
parametrises over `ADAPTERS.values()` and runs:

1. `fetch_bars` over a small recorded window — verifies ordering,
   schema, and idempotent re-run.
2. `fetch_corporate_actions` over a window known to contain at
   least one action.
3. Calendar consistency: bars only fall within session times for
   the venue.
4. Resilience: a synthetic 500-then-200 sequence triggers retry,
   not breaker; ten consecutive 500s open the breaker.

A new adapter's PR cannot merge until its conformance test passes.
