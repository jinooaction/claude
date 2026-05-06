# Phase 1 Data Model: LLM Token Telemetry

All timestamps are UTC ISO-8601 with millisecond precision. All monetary
fields are USD with `Decimal` semantics serialized as text (matching the
v1 convention in 001's data-model).

---

## Persistent entity (SQLite)

### `token_usage` — append-only

| column | type | notes |
|--------|------|-------|
| `seq` | INTEGER PRIMARY KEY AUTOINCREMENT | monotonic |
| `ts_utc` | TEXT NOT NULL | ISO-8601 ms |
| `model` | TEXT NOT NULL | e.g., `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` |
| `decision_class` | TEXT NULL | operator label; NULL means "(unclassified)" |
| `input_tokens` | INTEGER NOT NULL DEFAULT 0 | uncached input tokens |
| `output_tokens` | INTEGER NOT NULL DEFAULT 0 | output tokens |
| `cache_read_tokens` | INTEGER NOT NULL DEFAULT 0 | tokens served from prompt cache |
| `cache_write_tokens` | INTEGER NOT NULL DEFAULT 0 | tokens written to prompt cache |
| `cost_usd` | TEXT NULL | Decimal serialized; NULL if model not in price table |
| `latency_ms` | INTEGER NOT NULL DEFAULT 0 | clamped to ≥ 0 |
| `error_class` | TEXT NULL | exception class name when the call raised; NULL on success |
| `correlation_id` | TEXT NOT NULL | links to `audit_log.correlation_id` |

Indexes: `(ts_utc)`, `(decision_class, ts_utc)`, `(model, ts_utc)`, `(correlation_id)`.

Append-only invariant enforced by SQLite triggers `token_usage_no_update` and `token_usage_no_delete`, mirroring the pattern in migration 0001.

### `audit_log` — extension

The existing `audit_log` table gains one new value in the `event_type` discriminator: `LLM_CALL`. The payload schema (validated by pydantic in `persistence/audit.py`) carries only:

| field | type |
|-------|------|
| `event_type` | Literal["LLM_CALL"] |
| `model` | str |
| `decision_class` | str \| None |
| `tokens_total` | int |
| `cost_usd` | str \| None |
| `latency_ms` | int |
| `error_class` | str \| None |

Per FR-T11, no prompt/response content is ever placed in this payload.

---

## In-memory entities

### `TokenUsage` — `telemetry/store.py`

| field | type | notes |
|-------|------|-------|
| `model` | str | |
| `decision_class` | str \| None | |
| `input_tokens` | int | ≥ 0 |
| `output_tokens` | int | ≥ 0 |
| `cache_read_tokens` | int | ≥ 0 |
| `cache_write_tokens` | int | ≥ 0 |
| `latency_ms` | int | ≥ 0 |
| `error_class` | str \| None | |
| `correlation_id` | str | |
| `ts_utc` | str | ISO-8601 ms |

Computed fields (not persisted as separate columns):
- `tokens_total = input_tokens + output_tokens + cache_read_tokens + cache_write_tokens`
- `cost_usd = price_table.compute_cost(model, …)`; NULL if model unknown.

### `KPI` — `telemetry/kpi.py`

| field | type | notes |
|-------|------|-------|
| `name` | str | one of `cache_hit_rate`, `tokens_per_decision_p95`, `tokens_per_decision_mean`, `usd_per_decision_mean`, `latency_p50_ms`, `latency_p95_ms`, `call_volume` |
| `value` | Decimal \| int \| float | |
| `tier` | Literal["A","B","C","N/A"] | |
| `direction` | Literal["higher_is_better","lower_is_better"] | classifier hint |
| `threshold_used` | dict | the bands that drove the classification |

### `EfficiencySnapshot` — `telemetry/kpi.py`

Container returned by `compute_snapshot(conn, window_start, window_end)`:

| field | type |
|-------|------|
| `window_start_utc` | str |
| `window_end_utc` | str |
| `call_count` | int |
| `kpis` | list[KPI] |
| `per_decision_class` | dict[str, dict[str, Any]] | sub-aggregates: count, tokens_total, cost_usd, p95_tokens |
| `top_n_calls` | list[dict] | the N most expensive single calls (default N=5) |

### `PriceTable` — `telemetry/prices.py`

Loaded from `config/llm_prices.toml`. Pydantic-validated. Supports `compute_cost(model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens) -> Decimal | None`.

### `TierTable` — `telemetry/thresholds.py`

Loaded from `config/llm_kpi_thresholds.toml`. Pydantic-validated. Supports `classify(kpi_name, value, direction) -> Literal["A","B","C","N/A"]`.

---

## Validation rules summary

| Rule | Source | Enforced by |
|------|--------|-------------|
| `token_usage` is append-only | FR-T04, constitution IV | SQLite triggers (migration 0002) |
| Every metered call writes both a `token_usage` row and an `LLM_CALL` audit row with the same `correlation_id` | FR-T03 | `telemetry/meter.py` (`__aexit__`) |
| Unknown model → `cost_usd` NULL + `DATA_QUALITY_ISSUE` | FR-T08, edge case | `telemetry/prices.py` |
| Unknown KPI in threshold file → load-time pydantic error | FR-T06 | `telemetry/thresholds.py` |
| Required price file present | FR-T10 | `cli.py` startup gate |
| No prompt/response content in any persisted column | FR-T11, constitution V | `telemetry/meter.py` signature (no `prompt: str` parameter) |
| Latency ≥ 0 | edge case | `telemetry/meter.py` (`max(0, end - start)`) |
| Integrity: every `LLM_CALL` audit row has a matching `token_usage` row | FR-T12 | `telemetry/store.py` `integrity_check()` called from `cli.run` startup |

---

## Open structural choices

- Whether `token_usage` should also carry `prompt_cache_id` once Anthropic exposes one — defer to a future field addition; not blocking v2.
- Whether `cost_usd` should be re-computable post-hoc (price-table changes after the fact). Current design says "no — first write wins"; a future spec can add a `recompute_cost_usd` view that reads the latest price table without mutating history.
