# Contract: `BACKTEST_*` audit-event payloads

**Spec**: [../spec.md](../spec.md) (FR-B14, FR-B15, FR-B16, FR-B17) · **Plan**: [../plan.md](../plan.md) · **Date**: 2026-05-07

The engine emits three new event types into the existing `audit_log` table (constitution IV, principle K4 of the Kernel). All three follow the existing audit-row shape:

```sql
audit_log (
    seq_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc     TEXT    NOT NULL,        -- ISO 8601 UTC
    event_type TEXT    NOT NULL,        -- one of the three below
    payload    TEXT    NOT NULL         -- JSON, see below
)
```

The event types are append-only by virtue of the table itself (existing K4 invariants).

## `BACKTEST_STARTED`

Emitted exactly once per run, *after* input validation and OHLCV ingest succeed. Emitted *before* any replay work happens.

### Payload schema

```json
{
  "run_id": "<uuidv5>",
  "code_sha": "<40-char hex>" or "<40-char hex>+dirty",
  "dataset_hash": "<64-char hex>",
  "rules_hash": "<64-char hex>",
  "caps_hash": "<64-char hex>",
  "whitelist_hash": "<64-char hex>",
  "seed": <integer>,
  "vendor": "yfinance" | "kis_historical",
  "window_start": "YYYY-MM-DD" | null,
  "window_end":   "YYYY-MM-DD" | null,
  "named_dataset": "synthetic_shock_v1" | null
}
```

### Required-fields invariant

- All hash fields are `^[0-9a-f]{64}$`.
- `code_sha` is `^[0-9a-f]{40}(\+dirty)?$`.
- Exactly one of `(window_start, window_end)` and `named_dataset` is non-null.
- `run_id` is the UUIDv5 derived per R-5; it is the join key for every other artifact.

### Producer

`auto_invest.backtest.engine._emit_started` calls `auto_invest.persistence.audit.append`. The append goes through the existing K4 writer; no parallel path.

## `BACKTEST_COMPLETED`

Emitted exactly once per run that successfully replays through `report` phase. The artifact directory rename happens *after* this row is committed, so any `BACKTEST_COMPLETED` row in the audit log corresponds to a fully-written artifact directory.

### Payload schema

```json
{
  "run_id": "<uuidv5>",
  "total_return_pct": "<Decimal as string>",
  "max_drawdown_pct": "<Decimal as string>",
  "sharpe": "<Decimal as string>" | null,
  "fills_count": <integer ≥ 0>,
  "gate_rejections_count": <integer ≥ 0>,
  "promote_eligible": <boolean>,
  "artifact_dir": "data/backtests/<run_id>"
}
```

### Invariants

- `sharpe` is `null` iff the run hit bankruptcy at any point (R-7).
- `promote_eligible` is `true` iff all three thresholds in `verdict_thresholds` (the v1 frozen baseline or operator override) are satisfied.
- `artifact_dir` is a repo-relative path; absolute paths leak machine-specific layout into the audit log and are forbidden.

### Producer

`auto_invest.backtest.engine._emit_completed` — single call site.

## `BACKTEST_FAILED`

Emitted exactly once per run that started but did not complete successfully. FR-B16 makes this mandatory: every `BACKTEST_STARTED` row is paired with exactly one of `BACKTEST_COMPLETED` or `BACKTEST_FAILED`.

A run that fails *before* `BACKTEST_STARTED` (input validation, dirty-tree refusal, kernel-touch refusal) emits **no** audit row — the engine never started; emitting a started+failed pair would be misleading.

### Payload schema

```json
{
  "run_id": "<uuidv5>",
  "phase": "ingest_ohlcv" | "replay" | "report",
  "reason": "<one-line operator-readable summary, max 256 chars>"
}
```

### Phase semantics

| `phase` | What was happening when failure occurred | Common causes |
|---------|------------------------------------------|---------------|
| `ingest_ohlcv` | Vendor returned an error or a data-quality failure between `BACKTEST_STARTED` and replay loop. | Cache miss requiring network; vendor 5xx; `OhlcvDataQualityError` from a stale cache row. |
| `replay` | The replay loop raised. | Rule TOML referenced an undeclared symbol; gate config invariant violated mid-run; OS-level error (disk full while writing daily.csv). |
| `report` | Replay completed but report assembly raised. | Decimal overflow in Sharpe computation (extreme inputs); permission error on artifact dir creation. |

### `reason` discipline

- Must be a single line.
- Must NOT contain stack traces (operators read this in a daily report; verbose traces go in stderr/logs).
- Must NOT contain secrets, tokens, or response bodies (constitution V).
- 256 char hard limit; longer messages are truncated with a trailing `…`.

### Producer

`auto_invest.backtest.engine._emit_failed` — called from a single try/except wrapping the `BACKTEST_STARTED` → `BACKTEST_COMPLETED` body. The handler:

1. Catches any `Exception` (NOT `BaseException` — KeyboardInterrupt et al. propagate).
2. Maps the exception type to a `phase` value via a small dispatch table.
3. Constructs `reason` from `str(exc)` truncated and redacted.
4. Calls `audit.append(BackfillFailedPayload(...))`.
5. Re-raises the original exception so the CLI caller sees the actual error.

## End-to-end invariants

1. **Per-run cardinality**: ≤ 1 `BACKTEST_STARTED`. ≤ 1 `BACKTEST_COMPLETED`. ≤ 1 `BACKTEST_FAILED`. Exactly one of `{COMPLETED, FAILED}` for any `STARTED`.
2. **Append-only**: no UPDATE / DELETE on `audit_log` is ever issued by the engine.
3. **Determinism floor**: the `BACKTEST_STARTED` payload contains all six hashes from R-5; the canary harness re-runs against any past `BACKTEST_STARTED` row by reading the payload alone.
4. **Index-supported retrieval**: migration `0003_backtest_events.sql` creates a partial index `idx_audit_log_backtest_events` on `(event_type, ts_utc)` filtered to the three event types. SC-B06's "single SQL query for last 30 days" uses this index.
5. **Schema additivity**: this contract adds three event types and one index; it does not add columns to `audit_log`. The append-only invariant is mechanically preserved.
