# Contract — `HistoricalDataSource` Protocol

Internal Python protocol that lets a future spec slot in a yfinance / KIS-historical / IEX-Cloud adapter without re-doing the engine. v1 ships exactly one adapter (`CSVDataSource`).

## Protocol

```python
from typing import Protocol
from datetime import date
from auto_invest.backtest.data_model import OHLCVBar  # see data-model.md

class HistoricalDataSource(Protocol):
    """Read-only adapter over a versioned snapshot of OHLCV data."""

    @property
    def dataset_version(self) -> str:
        """SHA-256 of the manifest. Stable across processes for the same data."""

    def list_symbols(self) -> list[str]:
        """All symbols available in this dataset, uppercase, sorted ASCII."""

    def session_dates(self, symbol: str) -> list[date]:
        """Sorted ascending. Empty list if symbol unknown."""

    def coverage_holes(
        self,
        symbols: list[str],
        date_start: date,
        date_end: date,
    ) -> list[tuple[str, date]]:
        """Return (symbol, date) pairs that are MISSING in [date_start, date_end]
        for any (symbol, schedule_open_date) the exchange calendar says should exist.
        Empty list means full coverage."""

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        """Inclusive bounds. Sorted ascending by session_date. Empty list if no data."""
```

## Invariants every adapter MUST uphold

- `dataset_version` is content-derived and stable. Two adapters initialised against the same on-disk data produce the same `dataset_version`.
- `read_bars` returns `OHLCVBar` instances that ALREADY passed the ingest validation rules in `ohlcv-csv.md` § "Validation rules at ingest". An adapter that reads from an unvalidated source MUST validate at read time.
- `coverage_holes` MUST consult the exchange calendar (`worker/schedule.py:trading_days_between`) to know what dates SHOULD exist; it MUST NOT silently treat exchange holidays as missing.
- Adapters perform NO network I/O during a backtest run. The `ingest-history` job is the only sanctioned network point; an adapter that fetches on demand is a v2 concern.
- Adapters MUST be deterministic and pure given the same dataset version. No side effects (no caching to disk during reads, no remote-cache pulls).

## v1 adapter — `CSVDataSource`

- Reads from `data/history/<dataset_version>/<SYMBOL>.parquet`.
- Constructed with `dataset_version` (default: latest under `data/history/`).
- `coverage_holes` reads parquet metadata (row counts + date ranges) without loading the full files; full read happens only when the engine asks for a specific symbol's bars.

## Future adapters (out of scope for v1)

Sketch for guidance only; not part of this spec's deliverable.

### `YFinanceDataSource` (would be spec 009 or later)

- Wraps `yfinance.download(...)` behind the protocol.
- Sets `dataset_version` to a hash of `(symbol_list, date_start, date_end, yfinance.__version__)` plus a per-symbol content hash captured at first read.
- ToS-grey: requires a separate operator decision.

### `KISHistoricalDataSource` (would be spec 010 or later)

- Uses the existing `broker/client.py` httpx wrapper. Re-uses spec 001's circuit-breaker / retry / rate-limiter.
- Limited overseas-equity history depth (currently ≈2 years for v1 of the KIS overseas endpoint).

### `IEXCloudDataSource`

- Clean licensing. Paid ($10/mo at the time of writing this contract).
- One HTTPS call per (symbol, year) at ingest; cached locally; no fetches during backtest run.

## Why a protocol and not a base class

Python `Protocol` keeps the dependency from `engine → adapter` purely structural. No inheritance, no shared base class, no import dance. A future adapter lives in its own module and just needs to provide the four methods above.

## Why `coverage_holes` exists

Spec 007's hardened canary will refuse to run a synthetic-shock replay if any required (symbol, shock-date) is missing (Edge Case in spec.md). `coverage_holes` is the cheap pre-flight query the canary uses BEFORE asking the engine to load actual bars. Without it, the canary would have to call `read_bars` for everything to discover holes — slow and wasteful.
