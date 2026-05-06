"""Market-calendar abstraction (FR-D-006, T013).

Two implementations:

  * `DiscreteSessionCalendar` — wraps `exchange_calendars` for venues
    with discrete trading sessions (NYSE, NASDAQ, KRX, LSE, ...).
  * `AlwaysOpenCalendar` — for venues without session boundaries
    (crypto exchanges that operate 24/7/365).

Higher layers (engine, ingestion, quality checks) consume the
`MarketCalendar` ABC and never branch on asset class.

Spec 001's `worker/schedule.py` re-exports the same NYSE-bound API on
top of this module so existing call sites are unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache

import exchange_calendars as ec
import pandas as pd


class MarketCalendar(ABC):
    """Per-venue trading-session abstraction."""

    venue: str

    @abstractmethod
    def is_open_at(self, when: datetime) -> bool: ...

    @abstractmethod
    def next_open(self, when: datetime) -> datetime: ...

    @abstractmethod
    def next_close(self, when: datetime) -> datetime: ...

    @abstractmethod
    def is_holiday(self, d: date) -> bool:
        """Return True for non-session weekdays (weekends return False)."""

    @abstractmethod
    def is_session(self, d: date) -> bool:
        """Return True if `d` is a trading session day."""


class DiscreteSessionCalendar(MarketCalendar):
    """Wraps `exchange_calendars` for a single venue."""

    def __init__(self, *, venue: str, code: str) -> None:
        self.venue = venue
        self._code = code

    @property
    def _cal(self) -> ec.ExchangeCalendar:
        return _get_exchange_calendar(self._code)

    @staticmethod
    def _to_aware_utc(dt: datetime) -> pd.Timestamp:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return pd.Timestamp(dt.astimezone(UTC))

    @staticmethod
    def _to_py_utc(ts: pd.Timestamp) -> datetime:
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        return ts.to_pydatetime().astimezone(UTC)

    def is_open_at(self, when: datetime) -> bool:
        return bool(self._cal.is_open_at_time(self._to_aware_utc(when)))

    def next_open(self, when: datetime) -> datetime:
        return self._to_py_utc(self._cal.next_open(self._to_aware_utc(when)))

    def next_close(self, when: datetime) -> datetime:
        return self._to_py_utc(self._cal.next_close(self._to_aware_utc(when)))

    def is_holiday(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        return not self._cal.is_session(pd.Timestamp(d))

    def is_session(self, d: date) -> bool:
        return bool(self._cal.is_session(pd.Timestamp(d)))


class AlwaysOpenCalendar(MarketCalendar):
    """Crypto-style 24/7 venue. Every instant is a session."""

    def __init__(self, *, venue: str) -> None:
        self.venue = venue

    def is_open_at(self, when: datetime) -> bool:
        return True

    def next_open(self, when: datetime) -> datetime:
        # Always-open venues are always open; "next open" is `when` itself.
        return when if when.tzinfo else when.replace(tzinfo=UTC)

    def next_close(self, when: datetime) -> datetime:
        # Conventionally a far-future timestamp; callers that need a
        # "session boundary" should branch on calendar type.
        # We still return *some* finite future to keep the contract
        # well-formed; the caller is expected to know it is using
        # an always-open venue.
        base = when if when.tzinfo else when.replace(tzinfo=UTC)
        return base + timedelta(days=365 * 100)

    def is_holiday(self, d: date) -> bool:
        return False

    def is_session(self, d: date) -> bool:
        return True


@lru_cache(maxsize=8)
def _get_exchange_calendar(code: str) -> ec.ExchangeCalendar:
    return ec.get_calendar(code)


# Venue → calendar instance registry. Adding a new venue is one entry.
_VENUE_REGISTRY: dict[str, MarketCalendar] = {
    "nasdaq": DiscreteSessionCalendar(venue="nasdaq", code="XNYS"),
    "nyse": DiscreteSessionCalendar(venue="nyse", code="XNYS"),
    "amex": DiscreteSessionCalendar(venue="amex", code="XNYS"),
    "binance": AlwaysOpenCalendar(venue="binance"),
    "coinbase": AlwaysOpenCalendar(venue="coinbase"),
}


def get_calendar(venue: str) -> MarketCalendar:
    """Resolve a venue string (lowercased) to its calendar instance."""
    key = venue.lower()
    if key not in _VENUE_REGISTRY:
        raise KeyError(f"no calendar registered for venue {venue!r}")
    return _VENUE_REGISTRY[key]


def register_calendar(calendar: MarketCalendar) -> None:
    """Register or replace a calendar for a venue (used by adapters)."""
    _VENUE_REGISTRY[calendar.venue.lower()] = calendar
