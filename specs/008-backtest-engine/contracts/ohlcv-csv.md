# Contract — OHLCV CSV Ingest Format

This is the operator-facing CSV format consumed by `auto-invest ingest-history`. v1 ships this as the ONLY OHLCV vendor adapter (FR-B16). Later specs add yfinance / KIS-historical / IEX-Cloud adapters; they target the same `HistoricalDataSource` protocol (see `historical-data-source.md`), not this CSV format directly.

## File layout

One CSV per symbol, placed under a single source directory the operator passes to `ingest-history`:

```text
<operator-chosen-dir>/
├── AAPL.csv
├── SPY.csv
└── ...
```

- File name: `<SYMBOL>.csv`. Symbol is uppercase, ASCII letters/digits/dots/hyphens (matches the operator whitelist convention from spec 001).
- File encoding: UTF-8 without BOM.
- Line ending: LF or CRLF (Python's `csv` module handles both).

## Required columns (in this order)

| Column                  | Type         | Required | Notes |
|-------------------------|--------------|----------|-------|
| `session_date`          | `YYYY-MM-DD` | yes      | ISO-8601 date. US session date, not UTC. |
| `open`                  | decimal      | yes      | Up to 6 dp. Positive. |
| `high`                  | decimal      | yes      | Positive. `high ≥ max(open, close, low)`. |
| `low`                   | decimal      | yes      | Positive. `low ≤ min(open, close, high)`. |
| `close`                 | decimal      | yes      | Positive. |
| `volume`                | integer      | yes      | ≥ 0. |
| `session_schedule_tag`  | string       | yes      | One of `regular`, `early_close`, `holiday`, `halted`. |

Header row is REQUIRED and MUST match these column names exactly (lowercase, in this order). Extra columns are rejected at ingest (`UNKNOWN_COLUMN` error) so a typo (`Open`, `Volumn`) cannot silently inject garbage.

## Validation rules at ingest

Listed in the order the ingest job runs them; the first failing rule produces a fatal error and the file is rejected entirely (no partial ingest).

1. `HEADER_MISMATCH` — column names or order do not match the table above.
2. `UNPARSEABLE_ROW` — any row that does not have exactly 7 fields, or whose types fail to parse.
3. `BAD_PRICE_RANGE` — any row where `low > min(open, high, close)` or `high < max(open, low, close)` or any of {open, high, low, close} ≤ 0.
4. `BAD_VOLUME` — `volume < 0`.
5. `UNKNOWN_SCHEDULE_TAG` — `session_schedule_tag` not in the four allowed values.
6. `DUPLICATE_DATE` — two rows with the same `session_date`.
7. `NON_MONOTONIC_DATE` — rows are not sorted by `session_date` ascending.

Non-fatal warnings (recorded in `manifest.json#quality_warnings` and emitted as `DATA_QUALITY_ISSUE` audit rows):

- `ZERO_VOLUME_REGULAR` — `volume == 0` on a `regular` session day.
- `GAP_OVER_7_DAYS` — gap between consecutive `session_date`s exceeds 7 calendar days WITHOUT a documented exchange closure.
- `SCHEDULE_TAG_MISMATCH` — `session_schedule_tag == "regular"` on a known US market holiday, or vice versa. (Cross-checked against `exchange_calendars` via the existing `worker/schedule.py` helper.)

## Example

```csv
session_date,open,high,low,close,volume,session_schedule_tag
2024-01-02,185.640000,188.440000,183.890000,185.640000,82488700,regular
2024-01-03,184.220000,185.880000,183.430000,184.250000,58414500,regular
2024-01-04,182.150000,183.090000,180.880000,181.910000,71983600,regular
2024-01-05,181.990000,182.760000,180.170000,181.180000,62303300,regular
2024-01-08,182.090000,185.600000,181.500000,185.560000,59144500,regular
2024-11-29,236.640000,237.810000,233.150000,237.330000,28481400,early_close
```

## Re-ingest semantics

Re-running `ingest-history` over the same source directory:

- If file contents are byte-identical to a previously ingested version (same `file_sha256`), the existing `dataset_version` directory is reused. No work is done; the operator is told.
- If any file's `file_sha256` differs, a NEW `dataset_version` directory is created. The old one is preserved (never overwritten); the operator can prune manually.
- A backtest run binds to one `dataset_version`. Re-ingesting after a run starts does not affect the run.

## What this contract intentionally does NOT cover

- Intraday bars (sub-daily). v1 is daily-bar only.
- Corporate actions (splits, dividends). Operator is responsible for providing split-adjusted CSVs in v1. Future spec may add an actions sidecar file.
- Currency. v1 is USD only (matches spec 001 whitelist scope).
- Volume in shares vs. dollars. v1 is shares-traded volume.
