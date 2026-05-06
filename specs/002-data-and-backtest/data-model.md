# Phase 1 Data Model: Multi-Asset Data Infrastructure & Backtest Engine

This document defines the entities introduced by `spec.md`, their fields,
their persistence shape (SQLite where applicable, filesystem where the
artifact is large/immutable), and the state transitions they support.
Append-only constraints from constitution IV are called out explicitly.

All timestamps are UTC ISO-8601 with millisecond precision unless noted.
All monetary fields use `Decimal`. Symbols / venues / asset_class /
kind / vendor / source string fields are lowercased on write
(except symbol, which is uppercased to match spec 001's whitelist).

---

## In-memory entities (config-time, frozen after load)

### `DataSourcesConfig` — `config/data.py`

| field | type | notes |
|-------|------|-------|
| `enabled_adapters` | `tuple[str, ...]` | adapter names to instantiate at startup; deny-by-default (FR-D-003 + constitution II) |
| `default_vendor_per_kind` | `Mapping[str, str]` | for each `(asset_class, kind)`, the vendor whose records are read by the backtest engine when the run config does not pin one |
| `vendor_disagreement_tolerance_bps` | `Decimal` | per-bar OHLC disagreement beyond this threshold flags a `data_quality_event` |

### `BacktestConfig` — `config/backtest.py`

| field | type | notes |
|-------|------|-------|
| `run_id` | `str` | derived from a hash of the resolved config + rule snapshot; not user-editable |
| `rule_path` | `Path` | path to a TOML rule (spec 001) OR a Python module with a programmatic strategy |
| `rule_snapshot_hash` | `str` | sha256 over the canonicalised rule content; pins the rule for promotion |
| `instruments` | `tuple[InstrumentRef, ...]` | each `InstrumentRef` = `(asset_class, venue, symbol)` |
| `window_from` | `datetime` | inclusive UTC start |
| `window_to` | `datetime` | exclusive UTC end |
| `vendor_pins` | `Mapping[str, str]` | per-instrument vendor override; defaults from `DataSourcesConfig` |
| `as_of_ts_pin` | `datetime` | the maximum `as_of_ts` readable during the run (point-in-time barrier — FR-B-002) |
| `cost_model` | `CostModel` | see below |
| `walkforward` | `WalkForwardConfig \| None` | see below |
| `oos_window` | `OOSWindowConfig \| None` | see below |
| `seed` | `int` | RNG seed for any stochastic component (must be set; default 0) |

### `CostModel`

| field | type | notes |
|-------|------|-------|
| `commission_bps` | `Decimal` | applied to notional |
| `commission_min_usd` | `Decimal` | floor per fill |
| `half_spread_bps` | `Decimal` | applied to notional |
| `impact_coeff` | `Decimal` | square-root impact coefficient (R-2 default 0.1) |
| `participation_cap_pct` | `Decimal` | max % of bar volume a single fill consumes (R-2 default 10) |
| `per_symbol_overrides` | `Mapping[str, CostModelOverrides]` | optional per-symbol overrides for any of the above |

### `WalkForwardConfig`

| field | type | notes |
|-------|------|-------|
| `train_window_days` | `int` | rolling train window length |
| `test_window_days` | `int` | rolling test window length |
| `step_days` | `int` | step between folds |
| `min_folds` | `int` | run errors out if the chosen window cannot fit at least this many folds |

### `OOSWindowConfig`

| field | type | notes |
|-------|------|-------|
| `oos_from` | `datetime` | inclusive |
| `oos_to` | `datetime` | exclusive |
| `enforced_at_read_layer` | `bool` | always True; in-sample reads of OOS data raise `LookaheadError` |

### `PromotionThresholds` — `config/promotion.py`

| field | type | notes |
|-------|------|-------|
| `min_oos_sharpe` | `Decimal` | R-4 default 1.0 |
| `max_oos_drawdown_pct` | `Decimal` | R-4 default 15 |
| `min_oos_trade_count` | `int` | R-4 default 30 |
| `min_oos_window_days` | `int` | R-4 default 90 |
| `max_live_vs_backtest_drawdown_divergence_pct` | `Decimal` | R-4 default 5 |
| `divergence_alert_window_days` | `int` | R-4 default 5 |

---

## Persistent entities (SQLite — `data/auto_invest.db`)

All schema additions in 002 are additive. No spec 001 table is modified.

### Table `historical_bars` (append-only with revisions)

Stores OHLCV bars across all asset classes and vendors.

| column | type | notes |
|---|---|---|
| `asset_class` | TEXT NOT NULL | e.g., `equity`, `crypto`, `fx`, `future` |
| `venue` | TEXT NOT NULL | e.g., `nasdaq`, `nyse`, `binance`, `coinbase` |
| `symbol` | TEXT NOT NULL | uppercased ticker / pair (`AAPL`, `BTC-USD`) |
| `kind` | TEXT NOT NULL | `ohlcv_1m`, `ohlcv_1h`, `ohlcv_1d`, `tick` |
| `vendor` | TEXT NOT NULL | which adapter wrote this row |
| `bar_open_ts_utc` | TEXT NOT NULL | content timestamp |
| `as_of_ts_utc` | TEXT NOT NULL | when this row was first observed |
| `open` | TEXT NOT NULL | Decimal-as-string |
| `high` | TEXT NOT NULL | Decimal-as-string |
| `low` | TEXT NOT NULL | Decimal-as-string |
| `close` | TEXT NOT NULL | Decimal-as-string |
| `volume` | TEXT NOT NULL | Decimal-as-string (supports fractional crypto units) |
| `is_adjusted` | INTEGER NOT NULL | 0 = unadjusted, 1 = adjusted-for-corporate-actions |
| `frozen` | INTEGER NOT NULL | always 1; UPDATE/DELETE blocked by trigger |

**Primary key**: `(asset_class, venue, symbol, kind, vendor, bar_open_ts_utc, as_of_ts_utc, is_adjusted)`.
**Indices**: `(asset_class, venue, symbol, kind, bar_open_ts_utc)` for backtest reads; `(as_of_ts_utc)` for revision sweeps.

**Append-only invariants**:
- A trigger blocks UPDATE / DELETE on `historical_bars`.
- A revision of `(symbol, kind, bar_open_ts_utc)` writes a *new* row
  with a fresh `as_of_ts_utc` rather than overwriting.

### Table `event_series` (append-only with revisions)

Generic non-OHLCV time series: corporate actions are NOT here (they
have their own table for query speed); this is fundamentals, news,
sentiment scores, macro indicators, options chains snapshots, etc.

| column | type | notes |
|---|---|---|
| `asset_class` | TEXT NOT NULL | as above; nullable for asset-class-agnostic events (e.g., a macro indicator) |
| `venue` | TEXT | nullable for venue-agnostic events |
| `symbol` | TEXT | nullable for instrument-agnostic events |
| `kind` | TEXT NOT NULL | e.g., `earnings_release`, `news_event`, `macro_cpi`, `sentiment_score` |
| `vendor` | TEXT NOT NULL | |
| `event_ts_utc` | TEXT NOT NULL | content timestamp |
| `as_of_ts_utc` | TEXT NOT NULL | observation timestamp |
| `payload_json` | TEXT NOT NULL | structured payload (validated per kind by Pydantic on read) |
| `frozen` | INTEGER NOT NULL | always 1; UPDATE/DELETE blocked |

**Primary key**: `(kind, vendor, asset_class, venue, symbol, event_ts_utc, as_of_ts_utc)` (NULL-aware).

**Append-only invariants**: same as `historical_bars`.

### Table `corporate_actions` (append-only with revisions)

Splits, dividends, ticker changes, mergers. Promoted out of
`event_series` for fast read-side application during backtest.

| column | type | notes |
|---|---|---|
| `asset_class` | TEXT NOT NULL |
| `venue` | TEXT NOT NULL |
| `symbol` | TEXT NOT NULL | symbol *before* the action (post-action symbol stored in payload for ticker changes) |
| `vendor` | TEXT NOT NULL |
| `action_kind` | TEXT NOT NULL | `split`, `cash_dividend`, `ticker_change`, `merger`, `delisting` |
| `effective_ts_utc` | TEXT NOT NULL | content timestamp (effective date) |
| `as_of_ts_utc` | TEXT NOT NULL | observation timestamp |
| `payload_json` | TEXT NOT NULL | e.g., `{"ratio_num": 2, "ratio_den": 1}` for a 2-for-1 split |
| `frozen` | INTEGER NOT NULL | always 1 |

**Primary key**: `(asset_class, venue, symbol, vendor, action_kind, effective_ts_utc, as_of_ts_utc)`.

**Append-only invariants**: same.

### Table `data_quality_events` (append-only)

| column | type | notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT |
| `event_ts_utc` | TEXT NOT NULL | when the event was detected |
| `asset_class` | TEXT NOT NULL |
| `venue` | TEXT NOT NULL |
| `symbol` | TEXT NOT NULL |
| `kind` | TEXT NOT NULL | e.g., `gap`, `vendor_disagreement`, `retroactive_corporate_action`, `late_arrival` |
| `vendor` | TEXT | NULL for cross-vendor events |
| `payload_json` | TEXT NOT NULL | gap range, disagreeing vendors, etc. |
| `severity` | TEXT NOT NULL | `info` / `warn` / `block` (block prevents affected backtests from running) |

**Indices**: `(asset_class, venue, symbol, event_ts_utc)`, `(severity)`.

### Table `backtest_runs` (append-only)

A pointer table that mirrors the on-disk run directories so the
operator can query "which rules have been backtested over which
windows".

| column | type | notes |
|---|---|---|
| `run_id` | TEXT PRIMARY KEY | matches the directory under `data/backtests/<run_id>/` |
| `created_ts_utc` | TEXT NOT NULL |
| `rule_snapshot_hash` | TEXT NOT NULL |
| `config_hash` | TEXT NOT NULL | hash of `inputs/run.toml` (FR-B-001 reproducibility anchor) |
| `instruments_json` | TEXT NOT NULL | JSON array of `(asset_class, venue, symbol)` |
| `window_from_utc` | TEXT NOT NULL |
| `window_to_utc` | TEXT NOT NULL |
| `as_of_ts_pin_utc` | TEXT NOT NULL |
| `mode` | TEXT NOT NULL | `single` / `walkforward` / `oos` |
| `result_status` | TEXT NOT NULL | `succeeded` / `failed` / `aborted_lookahead` / `aborted_data_quality` |
| `frozen` | INTEGER NOT NULL | always 1 |

**Append-only invariants**: UPDATE / DELETE blocked by trigger.

### Table `promotion_seals` (append-only)

Mirrors the on-disk seal files for query.

| column | type | notes |
|---|---|---|
| `seal_id` | TEXT PRIMARY KEY | matches `data/promotions/<seal_id>.toml` |
| `issued_ts_utc` | TEXT NOT NULL |
| `rule_snapshot_hash` | TEXT NOT NULL |
| `backtest_run_id` | TEXT NOT NULL | foreign key into `backtest_runs(run_id)` |
| `oos_metrics_json` | TEXT NOT NULL |
| `thresholds_json` | TEXT NOT NULL | snapshot of `PromotionThresholds` at issue time |
| `revoked` | INTEGER NOT NULL | 0 / 1 — revocation writes a new row, never mutates |
| `frozen` | INTEGER NOT NULL | always 1 |

**Indices**: `(rule_snapshot_hash)`, `(backtest_run_id)`.

### Table `divergence_events` (append-only)

Live-vs-backtest divergence flags surfaced by the daily reporter
(FR-P-004).

| column | type | notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT |
| `event_ts_utc` | TEXT NOT NULL |
| `seal_id` | TEXT NOT NULL |
| `metric_kind` | TEXT NOT NULL | `drawdown`, `win_rate`, `mean_return_per_trade`, ... |
| `live_value` | TEXT NOT NULL | Decimal-as-string |
| `backtest_value` | TEXT NOT NULL | Decimal-as-string |
| `divergence_pct` | TEXT NOT NULL | Decimal-as-string |
| `breached` | INTEGER NOT NULL | 1 if `divergence_pct >= threshold` for the configured duration |

---

## On-disk artifacts

### `data/backtests/<run_id>/` (immutable after completion)

```
data/backtests/<run_id>/
├── inputs/
│   ├── run.toml                 # canonical config (auto-generated from CLI flags)
│   ├── rule_snapshot.toml       # frozen copy of the rule at run time
│   └── data_pin.json            # `(asset_class, venue, symbol, vendor, as_of_ts_pin)` per instrument
├── audit_log.jsonl              # simulated audit log; same schema as live audit log
├── orders.jsonl                 # cost-itemised orders (commission, half-spread, impact split out)
├── metrics.json                 # all metrics from FR-B-008
├── walkforward/                 # only if WalkForwardConfig set
│   ├── fold_001/                # per-fold subdirectories with their own metrics
│   └── ...
├── oos/                         # only if OOSWindowConfig set
│   └── metrics.json             # OOS-only metrics
└── report.md                    # human-readable summary
```

The `run_id` is `sha256(rule_snapshot_hash || config_hash || data_pin_hash)[:12]`.
Two runs with bit-identical inputs produce the same `run_id`; this
makes determinism (FR-B-001 / SC-002) checkable by directory name.

### `data/promotions/<seal_id>.toml` (immutable after issue; revocation writes a new file)

See `contracts/promotion-seal.md` for the schema.

---

## State transitions

### `BacktestRun` lifecycle

```
PENDING -> RUNNING -> {SUCCEEDED, FAILED, ABORTED_LOOKAHEAD, ABORTED_DATA_QUALITY}
```

- Transitions are recorded by writing a new row to `backtest_runs`
  with the new `result_status`. The pre-completion row is removed
  by the writer (in-flight runs are kept in-memory only).
- A run that has reached a terminal state cannot transition again.
  A re-run produces a *new* `run_id`.

### `PromotionSeal` lifecycle

```
ISSUED -> {ACTIVE (used by the live worker), REVOKED}
```

- `ISSUED` and `REVOKED` are both append-only rows. The "active" set
  is computed by the latest non-revoked seal for each
  `rule_snapshot_hash`.
- Revocation triggers: rule snapshot hash mismatch, threshold
  violation discovered post-issue (e.g., new OOS data invalidates),
  or operator-issued `auto-invest promote --revoke <seal_id>`.

### Live-vs-backtest divergence

```
NOT_FLAGGED -> FLAGGED -> {CLEARED, BREACHED}
```

- `FLAGGED`: divergence in any single day exceeds the threshold.
- `BREACHED`: the flag persists for `divergence_alert_window_days`.
  Reaching `BREACHED` halts new orders for the affected rule (same
  mechanism as the spec 001 halt flag, scoped per rule).
- `CLEARED`: divergence drops below the threshold; the rule resumes.

---

## Append-only enforcement (constitution IV)

Every new SQLite table in 002 carries the `frozen` boolean and a
trigger that blocks UPDATE / DELETE when `frozen = 1`. The pattern
is identical to spec 001's `audit_log` and is verified by an
existing integration test that we extend to cover the new tables.

`backtest_runs` and `promotion_seals` are slightly special: they
mirror filesystem artifacts and we want UPDATE blocked even on
`frozen = 0` rows (which only exist as in-flight markers, written
once and immediately replaced by the terminal-state row). The
trigger is therefore unconditional on these two tables.
