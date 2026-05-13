"""Canonical OHLCV row shape and content-hashing primitives.

FR-B06a: every adapter normalises into the same `OhlcvBar` shape so that
two vendors returning equivalent bars for a given (date, symbol) produce
the same `dataset_hash` (FR-B05). Decimals (not floats) on prices because
Sharpe / drawdown reproducibility is bit-sensitive (research R-3).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VendorId = Literal["yfinance", "kis_historical"]


class OhlcvBar(BaseModel):
    """One adjusted daily OHLCV row.

    Sort-stable by `(symbol, date)`. Frozen after construction so adapters
    cannot accidentally mutate cache rows mid-replay.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    date: date
    symbol: str
    open: Decimal = Field(...)
    high: Decimal = Field(...)
    low: Decimal = Field(...)
    close: Decimal = Field(...)
    volume: int
    adjusted: bool
    vendor_id: VendorId


def _bar_to_canonical_dict(bar: OhlcvBar) -> dict[str, object]:
    """Bar -> JSON-serialisable dict in canonical-key order.

    Decimals serialise as strings to avoid binary-float drift across
    platforms. Sort-key is fixed so json.dumps(sort_keys=True) is
    deterministic.
    """
    return {
        "date": bar.date.isoformat(),
        "symbol": bar.symbol,
        "open": str(bar.open),
        "high": str(bar.high),
        "low": str(bar.low),
        "close": str(bar.close),
        "volume": bar.volume,
        "adjusted": bar.adjusted,
        "vendor_id": bar.vendor_id,
    }


def canonical_dump(bars: Sequence[OhlcvBar]) -> str:
    """Render bars to canonical JSON for hashing or comparison.

    Bars are sorted by (symbol, date) before rendering so insertion order
    cannot influence the hash. UTF-8, sort_keys, no whitespace tweaks.
    """
    sorted_bars = sorted(bars, key=lambda b: (b.symbol, b.date))
    payload = [_bar_to_canonical_dict(b) for b in sorted_bars]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(bars: Sequence[OhlcvBar]) -> str:
    """Sha256 hex digest of canonical_dump(bars). 64 chars."""
    return hashlib.sha256(canonical_dump(bars).encode("utf-8")).hexdigest()
