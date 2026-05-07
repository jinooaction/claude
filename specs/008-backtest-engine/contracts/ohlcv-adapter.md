# Contract: vendor-agnostic OHLCV adapter Protocol

**Spec**: [../spec.md](../spec.md) (FR-B06, FR-B06a) · **Plan**: [../plan.md](../plan.md) · **Date**: 2026-05-07

The engine is vendor-agnostic. v1 ships two adapters (`yfinance`, `kis_historical`); future vendors plug in by implementing this Protocol.

## Protocol surface

```python
# auto_invest/backtest/ohlcv/adapter.py
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from auto_invest.backtest.ohlcv.canonical import OhlcvBar


class OhlcvAdapter(Protocol):
    vendor_id: str  # e.g. "yfinance", "kis_historical"

    async def fetch_bars(
        self,
        symbol: str,
        start: date,
        end: date,  # inclusive
    ) -> Sequence[OhlcvBar]:
        """
        Return all daily OHLCV bars for `symbol` between `start` and `end`,
        inclusive, sorted ascending by date. Splits and dividends MUST be
        applied before return (`OhlcvBar.adjusted == True` for every row).

        Raises:
            OhlcvDataQualityError - any returned bar would have NaN, zero
                volume on a non-holiday trading day, or unadjusted prices.
            OhlcvVendorError      - transport / auth / rate-limit failure
                that survived the adapter's tenacity retry budget.
            OhlcvWindowError      - the vendor returned no bars at all for
                a window that should not be empty (e.g. listed symbol +
                non-holiday range).
        """
```

## Conformance requirements

Every adapter MUST:

1. **Return `OhlcvBar`** in canonical form (R-3). The canonical model is the only allowed return type.
2. **Adjust for splits and dividends** before returning. Unadjusted bars are a `OhlcvDataQualityError`.
3. **Wrap every external call** in:
   - `tenacity` retry with exponential backoff (constitution VII; mirrors `broker/client.py`).
   - A per-host token-bucket rate limiter sized to the vendor's documented limits.
   - A circuit breaker that opens after `N` consecutive failures (configurable; default `5`) and re-closes after a cooldown.
4. **Never log credentials or response bodies that may contain secret material.** The existing `logging_config.py` redaction filter applies (constitution V).
5. **Emit `OhlcvVendorError` rather than swallow** any error that bypasses retry. The engine treats this as exit code `3` (`BACKTEST_FAILED phase=ingest_ohlcv`).
6. **Cache locally**: every successful fetch writes `(symbol, date)` rows to `data/ohlcv/<vendor_id>/<symbol>.parquet` (or `.csv` if pyarrow is absent). Re-runs against the same range satisfy from cache without a network call. Cache invalidation is content-hash-based: a row is considered stale iff its content hash differs from the live fetch on a forced refresh.
7. **Cache stamp**: the per-symbol file MUST carry a header line / trailer (or sidecar `.json`) containing `vendor_id`, `fetched_at_utc`, `adjusted_flag`. This is what the run manifest's `ohlcv_per_symbol_hash` consults.
8. **Not contact the network during replay**: cache misses MUST be resolved before `BACKTEST_STARTED` is emitted. If a cache miss is detected mid-replay, the engine raises immediately (FR-B09).

## Rate-limit defaults

| Vendor | Default rate-limit |
|--------|-------------------|
| `yfinance` | 2 req/s, burst 5 (Yahoo public endpoints have no published limit; this is conservative). |
| `kis_historical` | Reuse spec 001 R-7 setting (≈ 20 req/s per app key). |

## Vendor adapter v1: `yfinance`

**Module**: `auto_invest.backtest.ohlcv.yfinance_adapter`

**Vendor id**: `"yfinance"`

**Auth**: none.

**Endpoint**: yfinance's `Ticker.history(period, interval)`. v1 uses `interval="1d"` only.

**Adjustment**: `auto_adjust=True`.

**Notes**:
- yfinance is occasionally rate-limited by Yahoo's edge. The adapter MUST treat HTTP 429 and Yahoo's "no data" sentinel responses as transient and retry per (3) above.
- yfinance returns a `pandas.DataFrame`; the adapter normalises to `OhlcvBar` rows. Decimal precision: 4 decimal places on all prices (truncation, not rounding, to match Yahoo's display).

## Vendor adapter v1: `kis_historical`

**Module**: `auto_invest.backtest.ohlcv.kis_historical_adapter`

**Vendor id**: `"kis_historical"`

**Auth**: reuses `auto_invest.broker.auth` for KIS access tokens (constitution V — no new secret category).

**Endpoint**: KIS overseas-equity historical bar endpoint. v1 daily resolution.

**Adjustment**: KIS returns adjusted bars by default for overseas equities; the adapter sets `adjusted=True` accordingly. If KIS returns an explicit "unadjusted" flag for any bar, the adapter raises `OhlcvDataQualityError`.

**Notes**:
- The adapter uses the existing `ResilientClient` with the KIS-specific auth headers; constitution VII compliance is inherited.
- The adapter MUST NOT submit orders in any code path. It uses only price endpoints.

## Adding a third adapter (future-proofing)

The contract is intentionally narrow so a future Polygon / Alpaca / vendor-CSV adapter is a single-file addition:

1. Create `auto_invest/backtest/ohlcv/<vendor>_adapter.py`.
2. Implement `fetch_bars`, `vendor_id`.
3. Wire in `auto_invest.backtest.ohlcv.__init__.ADAPTERS` registry.
4. Add a CLI option `--vendor <name>`.
5. Add tests under `tests/backtest/test_<vendor>_adapter.py` using `respx` to mock the vendor's HTTP surface.

No engine code outside the adapter file changes. This is what FR-B06a's canonical-row contract buys us.
