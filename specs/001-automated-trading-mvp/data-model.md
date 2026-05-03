# Phase 1 Data Model: Automated US-Equity Trading MVP

This document defines the entities introduced by `spec.md`, their fields,
their persistence shape (where applicable), and the state transitions
they support. Append-only constraints from constitution IV are called out
explicitly per table.

All timestamps are UTC ISO-8601 with millisecond precision unless noted.
All monetary fields are USD with `Decimal` semantics (not float).

---

## In-memory entities (config-time, frozen after load)

### `SizingCaps` — `config/caps.py`

| field | type | notes |
|-------|------|-------|
| `per_trade_pct` | `Decimal` | 0 < value ≤ 100 |
| `per_symbol_pct` | `Decimal` | 0 < value ≤ 100 |
| `global_exposure_pct` | `Decimal` | 0 < value ≤ 100 |
| `canary_capital_pct` | `Decimal` | 0 < value ≤ `per_symbol_pct` |
| `canary_min_duration_days` | `int` | ≥ 1 |
| `canary_acceptance_drawdown_pct` | `Decimal` | 0 < value ≤ 100 |

Validation: enforced by pydantic; gate code asserts `per_trade_pct ≤ per_symbol_pct ≤ global_exposure_pct` at load time.

### `Whitelist` — `config/whitelist.py`

| field | type | notes |
|-------|------|-------|
| `symbols` | `frozenset[str]` | uppercased tickers |
| `accounts` | `frozenset[str]` | KIS account numbers |
| `order_types` | `frozenset[OrderType]` | enum: `LIMIT` (default), `MARKET` (opt-in) |
| `sessions` | `frozenset[Session]` | enum: `REGULAR` (default), `EXTENDED` |

### `TradingRule` — `config/rules.py`

| field | type | notes |
|-------|------|-------|
| `id` | `str` | operator-assigned unique identifier |
| `symbol` | `str` | MUST appear in `Whitelist.symbols` |
| `stage` | `StrategyStage` | enum: `BACKTEST` / `CANARY` / `FULL_LIVE` |
| `trigger` | `Trigger` | discriminated union; see below |
| `action` | `Action` | side (`BUY`/`SELL`), order type, quantity, limit price formula |
| `priority` | `int` | tie-breaker when caps would be exceeded |
| `enabled` | `bool` | operator switch |

### `Trigger` (discriminated union)

- `TimeTrigger`: `at_time` (HH:MM in venue timezone), optional `weekdays`.
- `PriceTrigger`: `direction` (`<=`/`>=`), `threshold` (Decimal USD).
- `IndicatorTrigger`: `indicator` (e.g., `EMA_CROSS`, `RSI_BELOW`), `params` (dict), `timeframe` (e.g., `1m`, `5m`, `1h`, `1d`).

All three carry `cooldown_seconds` to prevent rapid re-fires.

---

## Persistent entities (SQLite)

> Database file: `data/auto_invest.db`, WAL mode. Migrations live in
> `persistence/db.py`. Append-only tables enforce the invariant by
> code review (no `UPDATE`/`DELETE` reachable from production code) and
> by an integration test that scans for forbidden statements.

### `audit_log` — append-only

The single audit log used by every domain event. Specific event types
fan out via the `event_type` discriminator.

| column | type | notes |
|--------|------|-------|
| `seq` | INTEGER PRIMARY KEY AUTOINCREMENT | monotonic |
| `ts_utc` | TEXT | ISO-8601 ms |
| `event_type` | TEXT | `RULE_LOAD`, `ORDER_INTENT`, `ORDER_SUBMITTED`, `ORDER_REJECTED_BY_GATE`, `FILL`, `CANCEL`, `ERROR`, `RECONCILIATION_OK`, `RECONCILIATION_MISMATCH`, `HALT_SET`, `HALT_CLEARED`, `STRATEGY_PAUSED`, `DATA_QUALITY_ISSUE`, `SECRETS_LOADED`, `WORKER_STARTED`, `WORKER_STOPPED` |
| `rule_id` | TEXT NULL | links event to rule when applicable |
| `symbol` | TEXT NULL | links event to symbol when applicable |
| `payload_json` | TEXT | event-specific structured payload |
| `correlation_id` | TEXT NULL | groups multi-step events (e.g., `ORDER_INTENT` → `ORDER_SUBMITTED` → `FILL`) |

Indexes: `(ts_utc)`, `(event_type, ts_utc)`, `(rule_id, ts_utc)`, `(correlation_id)`.

### `orders` — append-only ledger

| column | type | notes |
|--------|------|-------|
| `seq` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `correlation_id` | TEXT UNIQUE | matches the row in `audit_log` |
| `rule_id` | TEXT | |
| `symbol` | TEXT | |
| `side` | TEXT | `BUY` / `SELL` |
| `order_type` | TEXT | `LIMIT` / `MARKET` |
| `qty` | INTEGER | |
| `limit_price_usd` | TEXT NULL | Decimal serialized |
| `state` | TEXT | `INTENT` / `SUBMITTED` / `REJECTED_BY_GATE` / `REJECTED_BY_BROKER` / `OPEN` / `PARTIALLY_FILLED` / `FILLED` / `CANCELED` |
| `kis_order_id` | TEXT NULL | populated after broker accepts |
| `submitted_at_utc` | TEXT NULL | |
| `final_state_at_utc` | TEXT NULL | |

State is updated on this row by INSERTing a new audit log entry plus
a state-transition row in `order_state_history` (next table). The
`orders.state` column is treated as a cache of the latest history row;
audit truth lives in `order_state_history`.

### `order_state_history` — append-only

| column | type |
|--------|------|
| `seq` | INTEGER PK AUTOINCREMENT |
| `order_correlation_id` | TEXT |
| `from_state` | TEXT NULL |
| `to_state` | TEXT |
| `ts_utc` | TEXT |
| `reason` | TEXT NULL |

Allowed transitions (any other transition is a bug):

```
                ┌─> REJECTED_BY_GATE
INTENT ─────────┤
                ├─> SUBMITTED ─┬─> REJECTED_BY_BROKER
                │              ├─> OPEN ──┬─> PARTIALLY_FILLED ──┬─> FILLED
                │              │          │                       └─> CANCELED
                │              │          └─> FILLED
                │              │          └─> CANCELED
```

### `fills` — append-only

| column | type |
|--------|------|
| `seq` | INTEGER PK AUTOINCREMENT |
| `order_correlation_id` | TEXT |
| `kis_fill_id` | TEXT UNIQUE |
| `qty` | INTEGER |
| `price_usd` | TEXT (Decimal) |
| `executed_at_utc` | TEXT |
| `commission_usd` | TEXT (Decimal) NULL |

### `price_bars` — append-only (FR-016)

| column | type |
|--------|------|
| `symbol` | TEXT |
| `timeframe` | TEXT |
| `bar_open_utc` | TEXT |
| `o`/`h`/`l`/`c` | TEXT (Decimal) |
| `volume` | INTEGER |
| `ingested_at_utc` | TEXT |

PK: `(symbol, timeframe, bar_open_utc)`. Late-arriving corrections are
modeled by inserting a new row with the same PK only when a strict
revision policy applies; default is "first write wins, log discrepancy."

### `current_positions` — derived cache

| column | type |
|--------|------|
| `symbol` | TEXT PK |
| `qty` | INTEGER |
| `avg_cost_usd` | TEXT (Decimal) |
| `last_updated_utc` | TEXT |

Reproducible from `fills`. Reconciled daily against KIS (FR-007). The
cache exists for sub-second reads inside risk gates; the source of
truth remains `fills`.

### `reconciliation_runs` — append-only

| column | type |
|--------|------|
| `seq` | INTEGER PK AUTOINCREMENT |
| `started_at_utc` | TEXT |
| `finished_at_utc` | TEXT NULL |
| `result` | TEXT | `OK` / `MISMATCH` / `INCONCLUSIVE` |
| `mismatch_payload_json` | TEXT NULL | side-by-side diff when `MISMATCH` |

### `strategy_stage_history` — append-only

| column | type |
|--------|------|
| `seq` | INTEGER PK AUTOINCREMENT |
| `rule_id` | TEXT |
| `from_stage` | TEXT NULL |
| `to_stage` | TEXT |
| `reason` | TEXT |
| `ts_utc` | TEXT |

Captures promotion (canary → full-live), demotion (full-live → canary
on autopause), and pause events.

---

## Validation rules summary

| Rule | Source | Enforced by |
|------|--------|-------------|
| Symbol must be on whitelist | FR-002 | `risk/gates.py` (`whitelist_gate`) |
| Order qty × price ≤ per-trade cap | constitution I, FR-004 | `risk/gates.py` (`per_trade_cap_gate`) |
| Symbol exposure after fill ≤ per-symbol cap | constitution I, FR-004 | `risk/gates.py` (`per_symbol_cap_gate`) |
| Total exposure after fill ≤ global cap | constitution I, FR-004 | `risk/gates.py` (`global_exposure_gate`) |
| Halt flag absent | FR-013 | `risk/gates.py` (`halt_gate`) |
| Indicator rule has ≥ N bars before arming | FR-016 | `strategy/triggers.py` |
| Data feed not stale | FR-017 | `market_data/quality.py` |
| One stage per (rule_id, symbol) at any time | FR-012 | `execution/order_router.py` startup check |
| Required secrets present | FR-011 | `config/loader.py` startup check |

---

## Open structural choices (carried forward to /tasks)

- Whether `current_positions` is rebuilt on every worker start (cold cache) or warm-loaded with a self-check against `fills` is a `/tasks` decision; both are correct, the cold path is simpler.
- Whether `audit_log.payload_json` is enforced by JSON Schema or by pydantic models per event type. Recommend pydantic for code-side ergonomics; defer the choice to /tasks.
