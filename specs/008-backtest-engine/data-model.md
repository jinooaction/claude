# Phase 1 Data Model: Backtest Engine

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md) · **Date**: 2026-05-07

This document captures the data structures the engine produces and consumes. Three layers:

1. **In-memory pydantic models** — what `auto_invest.backtest` passes around at runtime.
2. **On-disk artifact schema** — what lives under `data/backtests/<run_id>/` and `data/ohlcv/`.
3. **SQLite schema** — the migration `0003_backtest_events.sql` against the existing `audit_log` table.

All models are immutable once constructed (frozen pydantic). All on-disk JSON is sorted-keys, indent=2, trailing-newline, UTF-8 — these properties are part of the FR-B12 byte-identity contract.

---

## 1. In-memory models

### `BacktestConfig` (input)

The single input dataclass passed to `run_backtest`. Validated at the entry point.

| Field | Type | Notes / validation |
|-------|------|--------------------|
| `rule_set_path` | `Path` | Absolute path to the rules TOML. Must exist and parse as the live rule schema. |
| `vendor` | `Literal["yfinance", "kis_historical"]` | FR-B06. Adapter selected from this. |
| `window` | `BacktestWindow` | One of: `Window(start: date, end: date)` (contiguous) or `NamedDataset(name: str)` (e.g. `synthetic_shock_v1`). Discriminated union. |
| `symbols` | `frozenset[str] \| None` | If `None`, derived from rules. Otherwise filtered intersect with rule symbols. |
| `seed` | `int` | Default `0`. Recorded in manifest. |
| `opening_cash_usd` | `Decimal` | Default `Decimal("100000.00")`. FR-B10. |
| `slippage_bps_market` | `int` | Default `5`. FR-B07 market-fill slippage in basis points. |
| `risk_free_rate_annual` | `Decimal` | Default `Decimal("0")`. R-7. |
| `warmup_bars` | `int` | Default `50`. R-8. Required prior-bar count for indicator priming. |
| `verdict_thresholds` | `VerdictThresholds` | Default = v1 baseline (R/B/Q5). FR-B21. |
| `output_root` | `Path` | Default `data/backtests/`. The artifact directory `<output_root>/<run_id>/` is created on success. |
| `allow_dirty` | `bool` | Default `False`. If `True`, dirty git tree is permitted; `code_sha` becomes `<sha>+dirty` and `manifest.dirty = True`. R-5. |

### `VerdictThresholds`

| Field | Type | v1 default (frozen, FR-B21) |
|-------|------|------------------------------|
| `total_return_pct_min` | `Decimal` | `Decimal("0")` |
| `max_drawdown_pct_max` | `Decimal` | `Decimal("10")` |
| `sharpe_min` | `Decimal` | `Decimal("0.5")` |

### `BacktestWindow` (sealed union)

```text
Window:
  start: date
  end:   date           # inclusive; must be ≥ start
  kind:  Literal["window"]

NamedDataset:
  name:  str            # must match a manifest at data/ohlcv/datasets/<name>.json
  kind:  Literal["named_dataset"]
```

### `OhlcvBar` (R-3)

| Field | Type | Notes |
|-------|------|-------|
| `date` | `date` | Trading date (UTC). |
| `symbol` | `str` | Uppercased ticker. |
| `open` | `Decimal` | 4-decimal-place USD. |
| `high` | `Decimal` | "" |
| `low` | `Decimal` | "" |
| `close` | `Decimal` | "" |
| `volume` | `int` | Shares. |
| `adjusted` | `bool` | `True` iff splits/dividends applied. The engine refuses to run if `False`. |
| `vendor_id` | `str` | Adapter identifier (`yfinance`, `kis_historical`). |

Sort key: `(symbol, date)`.

### `BacktestRun` (transient runtime state)

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | `str` | UUIDv4, derived from `(seed, code_sha, dataset_hash, rules_hash)` via UUIDv5 in the `dns` namespace, so reruns of identical inputs produce the same `run_id`. |
| `code_sha` | `str` | git HEAD; or `<sha>+dirty` if `allow_dirty`. |
| `dataset_hash` | `str` | sha256 of canonicalised OHLCV JSON. |
| `rules_hash` | `str` | sha256 of canonicalised rules TOML. |
| `caps_hash` | `str` | sha256 of `config/caps.py` constants. |
| `whitelist_hash` | `str` | sha256 of `config/whitelist.py` symbols. |
| `seed` | `int` | From input config. |
| `start_ts_utc` | `datetime` | When `run_backtest` is called. Excluded from FR-B12 byte-identity. |
| `end_ts_utc` | `datetime` | Set on completion. Excluded from FR-B12. |
| `verdict` | `Verdict` | Filled at the end. |

### `Verdict`

| Field | Type | Notes |
|-------|------|-------|
| `promote_eligible` | `bool` | True iff all three thresholds are met. |
| `reasons` | `list[str]` | Per-threshold pass/fail rationale, deterministic order. |

### `SimulatedFill`

Append-only ledger row, persisted under `data/backtests/<run_id>/fills.csv`.

| Field | Type | Notes |
|-------|------|-------|
| `seq` | `int` | Monotonic per run. |
| `bar_date` | `date` | Trigger bar's date. |
| `symbol` | `str` | Uppercased. |
| `rule_id` | `str` | Rule that fired. |
| `side` | `Literal["BUY", "SELL"]` | |
| `order_type` | `Literal["LIMIT", "MARKET"]` | Mirrors live order_type from the rule. |
| `requested_qty` | `int` | Pre-gate quantity. |
| `gate_decision` | `Literal["allow", "reject"]` | From `risk/gates.py`. |
| `gate_reason` | `str \| None` | Populated iff `gate_decision == "reject"`. |
| `fill_qty` | `int` | 0 if rejected or not-straddled; else `requested_qty`. |
| `fill_price_usd` | `Decimal` | The deterministic FR-B07 price. |
| `fill_model_branch` | `Literal["limit_range_aware", "market_next_open", "no_fill"]` | FR-B07a. |
| `slippage_bps_applied` | `int` | 0 for limit; default 5 for market unless overridden. |
| `cash_usd_after` | `Decimal` | Portfolio cash after this fill. |
| `position_qty_after` | `int` | Per-symbol position after this fill. |

### `DailyState`

Per-day snapshot, persisted to `daily.csv`.

| Field | Type | Notes |
|-------|------|-------|
| `date` | `date` | |
| `cash_usd` | `Decimal` | End-of-day. |
| `equity_usd` | `Decimal` | cash + sum(per-symbol qty × close). |
| `daily_return_pct` | `Decimal` | (equity_today − equity_yesterday) / equity_yesterday × 100. Day 0 = 0. |
| `cumulative_return_pct` | `Decimal` | (equity_today − opening_cash) / opening_cash × 100. |
| `drawdown_pct` | `Decimal` | (peak_equity_so_far − equity_today) / peak_equity_so_far × 100. |
| `gate_rejections` | `int` | Count of rejected orders this day. |
| `fills_count` | `int` | Count of executed fills this day. |
| `per_symbol_exposure_pct_json` | `str` | JSON object `{symbol: exposure_pct}`. Serialised here for CSV-friendliness. |

### `BacktestReport` (FR-B11 headline)

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | `str` | |
| `total_return_pct` | `Decimal` | Final cumulative return. |
| `max_drawdown_pct` | `Decimal` | Maximum drawdown over the window. |
| `sharpe_annualised` | `Decimal \| None` | R-7. `None` on bankruptcy. |
| `risk_free_rate_annual` | `Decimal` | The rf used. |
| `fills_count_total` | `int` | |
| `gate_rejections_total` | `int` | |
| `per_rule_pnl_usd` | `dict[str, Decimal]` | Rule id → realised P&L. |
| `per_rule_fills_count` | `dict[str, int]` | Rule id → fill count. |
| `bankruptcy_at` | `date \| None` | Set iff equity hit zero. |
| `verdict` | `Verdict` | |

---

## 2. On-disk artifact schema (`data/backtests/<run_id>/`)

Five files. All written atomically (temp-file + rename) so partial writes are not visible.

### `manifest.json`

```text
{
  "schema_version": 1,
  "run_id":         "<uuidv5>",
  "code_sha":       "<sha>" or "<sha>+dirty",
  "dataset_hash":   "<sha256>",
  "rules_hash":     "<sha256>",
  "caps_hash":      "<sha256>",
  "whitelist_hash": "<sha256>",
  "seed":           <int>,
  "vendor":         "yfinance" | "kis_historical",
  "window":         {"kind":"window", "start":"YYYY-MM-DD", "end":"YYYY-MM-DD"}
                   |{"kind":"named_dataset", "name":"synthetic_shock_v1"},
  "symbols":        ["AAPL","MSFT", ...],
  "opening_cash_usd": "100000.00",
  "slippage_bps_market": 5,
  "risk_free_rate_annual": "0",
  "warmup_bars": 50,
  "verdict_thresholds": {
    "total_return_pct_min": "0",
    "max_drawdown_pct_max": "10",
    "sharpe_min":           "0.5"
  },
  "ohlcv_bars_consumed": <int>,
  "ohlcv_per_symbol_hash": {
    "AAPL": "<sha256>", ...
  },
  "start_ts_utc": "2026-05-07T18:46:43Z",
  "end_ts_utc":   "2026-05-07T18:46:51Z",
  "dirty":        false
}
```

`schema_version: 1` is the v1 floor. Bumping it is a breaking change for the canary harness (spec 007 SC-C04) and is itself a one-step amendment that goes through human review.

`start_ts_utc`, `end_ts_utc`, `dirty` (the `+dirty` suffix on `code_sha`), and the `ohlcv_per_symbol_hash` ordering are excluded / canonicalised so two reruns on identical inputs produce a byte-identical manifest *except* for those three timestamp/dirty fields.

### `report.json`

```text
{
  "schema_version": 1,
  "run_id": "<uuidv5>",
  "total_return_pct":     "12.34",
  "max_drawdown_pct":     "4.21",
  "sharpe_annualised":    "0.83" | null,
  "risk_free_rate_annual": "0",
  "fills_count_total":    127,
  "gate_rejections_total": 3,
  "per_rule_pnl_usd":     {"rule_a": "1234.56", ...},
  "per_rule_fills_count": {"rule_a": 47, ...},
  "bankruptcy_at":        null | "YYYY-MM-DD",
  "verdict": {
    "promote_eligible": true,
    "reasons": [
      "total_return_pct 12.34 ≥ 0",
      "max_drawdown_pct 4.21 ≤ 10",
      "sharpe_annualised 0.83 ≥ 0.5"
    ]
  }
}
```

### `daily.csv`

Header row is canonical; rows sorted ascending by `date`.

```text
date,cash_usd,equity_usd,daily_return_pct,cumulative_return_pct,drawdown_pct,gate_rejections,fills_count,per_symbol_exposure_pct_json
2024-01-02,100000.00,100000.00,0,0,0,0,0,{}
2024-01-03,99876.12,100412.45,0.41,0.41,0.00,0,1,"{""AAPL"":0.54}"
...
```

CSV quoting follows RFC 4180. The JSON column is double-quoted with embedded `"` escaped by doubling, so column readers (`csv.DictReader`) parse it correctly.

### `fills.csv`

Same conventions as `daily.csv`; one row per `SimulatedFill`. Columns mirror the in-memory model field names.

### `audit-events.json`

The subset of `audit_log` rows whose payload `run_id` matches this run's `run_id`. Format matches the existing `audit_log` row shape exported as JSON.

```text
[
  {"seq_id": 12891, "ts_utc": "2026-05-07T18:46:43Z",
   "event_type": "BACKTEST_STARTED",
   "payload":  {"run_id":"...", "code_sha":"...", ...}},
  {"seq_id": 12892, "ts_utc": "2026-05-07T18:46:51Z",
   "event_type": "BACKTEST_COMPLETED",
   "payload":  {"run_id":"...", "total_return_pct":"12.34", ...}}
]
```

---

## 3. Named-dataset schema (`data/ohlcv/datasets/<name>.json`)

```text
{
  "schema_version": 1,
  "name": "synthetic_shock_v1",
  "frozen_at_utc": "2026-05-07T00:00:00Z",
  "dates": ["2020-03-12", "2020-04-20", "2024-08-05", "2026-03-20"],
  "rationale": {
    "2020-03-12": "COVID circuit breakers",
    "2020-04-20": "Negative oil futures (limit-order-only sanity check)",
    "2024-08-05": "Yen-carry unwind",
    "2026-03-20": "Most recent quarterly OPEX at freeze time (third Friday March 2026)"
  },
  "constitutional_tier": "L4",
  "mutation_policy": "Operator-only. Subsequent OPEX days do NOT auto-roll. Adding/removing a date is L4 per spec 005."
}
```

Modifying this file is L4 (constitution IX, spec 005). The deploy guard checks the diff against this path.

---

## 4. SQLite schema additions (`migrations/0003_backtest_events.sql`)

Existing `audit_log` schema (from spec 001's `0001_initial.sql`):

```sql
CREATE TABLE audit_log (
    seq_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc     TEXT    NOT NULL,
    event_type TEXT    NOT NULL,
    payload    TEXT    NOT NULL  -- JSON
);
```

Migration `0003_backtest_events.sql` adds **no columns**. It adds one partial index optimised for SC-B06:

```sql
-- 0003_backtest_events.sql
-- Optimise SC-B06: "show me every backtest run in the last 30 days".
-- Audit-log invariants are unchanged; no UPDATE / DELETE is permitted.

CREATE INDEX IF NOT EXISTS idx_audit_log_backtest_events
    ON audit_log (event_type, ts_utc)
    WHERE event_type IN ('BACKTEST_STARTED', 'BACKTEST_COMPLETED', 'BACKTEST_FAILED');
```

This file is added to `kernel.toml` group K4 in the same change set, per the FR-B17 / Q3 clarification.

### `BACKTEST_STARTED` payload

```json
{
  "run_id":         "<uuidv5>",
  "code_sha":       "<sha>" or "<sha>+dirty",
  "dataset_hash":   "<sha256>",
  "rules_hash":     "<sha256>",
  "caps_hash":      "<sha256>",
  "whitelist_hash": "<sha256>",
  "seed":           <int>,
  "vendor":         "yfinance" | "kis_historical",
  "window_start":   "YYYY-MM-DD" | null,
  "window_end":     "YYYY-MM-DD" | null,
  "named_dataset":  "synthetic_shock_v1" | null
}
```

Exactly one of `(window_start, window_end)` and `named_dataset` is non-null.

### `BACKTEST_COMPLETED` payload

```json
{
  "run_id":               "<uuidv5>",
  "total_return_pct":     "12.34",
  "max_drawdown_pct":     "4.21",
  "sharpe":               "0.83" | null,
  "fills_count":          127,
  "gate_rejections_count": 3,
  "promote_eligible":     true,
  "artifact_dir":         "data/backtests/<run_id>"
}
```

### `BACKTEST_FAILED` payload

```json
{
  "run_id": "<uuidv5>",
  "phase":  "validate_inputs" | "ingest_ohlcv" | "replay" | "report",
  "reason": "<one-line summary>"
}
```

The engine MUST emit exactly one of `BACKTEST_COMPLETED` or `BACKTEST_FAILED` for every `BACKTEST_STARTED` (FR-B16).

---

## 5. State transitions

```text
                           +----------------------+
   run_backtest(config) -> | validate_inputs      |
                           +----------------------+
                                   | ok
                                   v
                           +----------------------+    fail
                           | resolve git/code_sha |---------+
                           +----------------------+         |
                                   | ok                     |
                                   v                        |
                           +----------------------+   fail   |
                           | hash {rules,caps,    |--------->|
                           |  whitelist}          |          |
                           +----------------------+          |
                                   | ok                      |
                                   v                         |
                           +----------------------+   fail   |
                           | ingest_ohlcv (cached |--------->|
                           |  + content_hash)     |          |
                           +----------------------+          |
                                   | ok                      |
                                   v                         |
                           +----------------------+          |
                           | EMIT BACKTEST_STARTED|          |
                           +----------------------+          |
                                   | ok                      |
                                   v                         |
                           +----------------------+   fail   |
                           | warmup_indicators    |--------->|
                           |  (silent N bars)     |          |
                           +----------------------+          |
                                   | ok                      |
                                   v                         |
                           +----------------------+   fail   |
                           | replay loop          |--------->|
                           |  (Worker.tick × N)   |          |
                           +----------------------+          |
                                   | ok                      |
                                   v                         |
                           +----------------------+   fail   |
                           | compute report +     |--------->|
                           |  verdict             |          |
                           +----------------------+          |
                                   | ok                      |
                                   v                         v
                           +----------------------+  +----------------------+
                           | EMIT                 |  | EMIT BACKTEST_FAILED |
                           | BACKTEST_COMPLETED   |  +----------------------+
                           +----------------------+
                                   |
                                   v
                           +----------------------+
                           | write artifact dir   |
                           |  (atomic; tmp+rename)|
                           +----------------------+
                                   |
                                   v
                                 return BacktestResult
```

Two invariants enforce FR-B16:

1. The engine wraps the entire post-`BACKTEST_STARTED` body in a try/except whose handler emits `BACKTEST_FAILED` and re-raises. No silent exit path exists.
2. The artifact dir is written *after* `BACKTEST_COMPLETED` is in the audit_log, so a partial artifact dir cannot exist for a "completed" run.

---

## 6. Validation summary

- All entities are derived from FRs in spec 008: `OhlcvBar` (FR-B05/B06a), `SimulatedFill` (FR-B07a/B10), `DailyState` (FR-B11), `BacktestReport` (FR-B11), `Verdict` (FR-B21), `BacktestRun` (FR-B12 reproducibility inputs), payload schemas (FR-B14..B17).
- Append-only invariant (constitution IV) is preserved: no UPDATE / DELETE on `audit_log`; the migration adds only an index.
- No Kernel files are modified by the in-memory or on-disk schemas. The migration file's addition to `kernel.toml` K4 (the one-time K-meta event documented in the Q3 clarification) is the only Kernel touch and is itself constitutional under IX.C.
- Determinism floor (R-5) is captured in the manifest via six hashes; FR-B12's byte-identity is checkable by diffing manifest/report/daily/fills minus `run_id`/`*_ts_utc`/`dirty`.
