# Phase 1 — Data Model: Backtest Engine

This is the implementation-side complement to `spec.md § Key Entities`.
It specifies field-level shapes, audit-log payloads, on-disk layout,
and the invariants the implementation MUST uphold.

## In-memory entities

### `BacktestRun`

```python
class BacktestRun(BaseModel):
    run_id: str                        # UUIDv7 hex (sortable, monotonic)
    invoker: Literal["cli", "canary"]  # who started the run
    ruleset_path: Path                 # absolute path the operator passed
    ruleset_sha256: str                # SHA-256 of the ruleset file bytes
    dataset_version: str               # SHA-256 (R-B12), refers to data/history/<dataset_version>
    date_start: date                   # inclusive (US session date)
    date_end: date                     # inclusive
    replay_seed: int                   # 0 by default; reserved for future stochastic strategies
    fill_model: Literal["pessimistic_zero_slip"]  # locked in v1 (FR-B07)
    judgment_mode: Literal["stub"]                # locked in v1 (FR-B08)
    synthetic_shock: bool              # True iff invoked with --synthetic-shock
    start_ts: datetime                 # wall-clock instant the run began; volatile (R-B5)
    end_ts: datetime | None            # set at BACKTEST_COMPLETED
    status: Literal["running", "completed", "failed"]
    summary: BacktestSummary | None    # populated at completion
```

Invariants:

- `run_id` MUST be unique across the audit log. A run that tries to reuse one fails fast (User Story 1 acceptance #3).
- `ruleset_sha256` is computed once at start and recorded in `BACKTEST_STARTED`. Spec 007's canary replay verifier hashes against this to ensure rule-content equality, not path equality.
- `dataset_version` MUST exist on disk under `data/history/<dataset_version>/` with a valid `manifest.json` at start time. The version is captured at start; concurrent ingest does not affect the run (R-B12 + Edge Case).
- `fill_model` and `judgment_mode` are `Literal[...]` to make any future widening a deliberate spec amendment.

### `RuleBacktestResult`

```python
class RuleBacktestResult(BaseModel):
    rule_id: str
    symbol: str
    total_return_pct: Decimal       # gross; 0% RFR
    max_drawdown_pct: Decimal       # absolute value, positive
    sharpe_ratio: Decimal           # annualised, sqrt(252), RFR=0 (R-B4)
    order_count: int
    fill_count: int                 # ≤ order_count
    gate_rejection_count_by_gate: dict[str, int]  # e.g., {"per_trade_cap": 3, "global_exposure": 1}
    notional_traded_usd: Decimal
    slippage_assumption: Literal["zero"]  # locked in v1
```

Invariants:

- `fill_count ≤ order_count`. Difference equals open + expired orders.
- `gate_rejection_count_by_gate` keys are members of the existing `risk/gates.py` gate set (no new keys invented for backtest).
- All Decimals are serialised as canonical strings ("123.456000"), trailing zeros preserved to 6 dp, to keep the determinism contract (FR-B15) byte-stable across machines.

### `BacktestSummary`

```python
class BacktestSummary(BaseModel):
    aggregate_return_pct: Decimal       # rule-weighted; equal weight in v1
    aggregate_max_drawdown_pct: Decimal
    aggregate_sharpe: Decimal
    per_rule: list[RuleBacktestResult]
    total_orders: int
    total_fills: int
    total_gate_rejections: int
    data_quality_warnings: list[DataQualityWarning]
```

### `OHLCVBar` (read-only, ingested)

```python
class OHLCVBar(BaseModel):
    symbol: str
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    session_schedule_tag: Literal["regular", "early_close", "holiday", "halted"]
```

Invariants enforced at ingest (FR-B13):

- `low ≤ open ≤ high`, `low ≤ close ≤ high`. Violation → `DATA_QUALITY_ISSUE` and ingest abort.
- `open, high, low, close > 0`. Negative or zero prices → abort.
- `volume ≥ 0`. Zero volume during `regular` → warning (not abort); zero volume during `halted` → expected.
- One row per `(symbol, session_date)`. Duplicates → abort.
- `session_date` is strictly increasing per symbol. Gaps > 7 calendar days WITHOUT a documented exchange closure → warning.

### `HistoricalDataset` (on-disk artefact)

```text
data/history/<dataset_version>/
├── manifest.json                  # see schema below
└── bars.sqlite                    # one indexed table ohlcv_bars(symbol, session_date, ...)
                                   # (Parquet was the original design; we use SQLite so v1
                                   #  ships with zero new dependencies — see contracts/historical-data-source.md.)
```

`manifest.json` schema:

```json
{
  "dataset_version": "<hex64>",
  "ingested_at_utc": "<ISO-8601>",
  "source_csv_paths": ["history/csv/AAPL.csv", "..."],
  "files": [
    {"symbol": "AAPL", "rows": 252, "file_sha256": "<hex64>", "session_date_min": "2024-01-02", "session_date_max": "2024-12-31"},
    ...
  ],
  "quality_warnings": [
    {"symbol": "AAPL", "session_date": "2024-04-15", "kind": "zero_volume_regular", "note": "..."},
    ...
  ]
}
```

Invariants:

- `dataset_version` recomputed at load and compared to the directory name; mismatch → engine refuses to start (defends against manual file tampering).
- Manifest is immutable after creation; re-ingest creates a new version directory.

### `ReplayClock`

```python
class ReplayClock:
    def __init__(self, bar_times: Iterable[datetime]) -> None: ...
    def advance_to(self, ts: datetime) -> None: ...
    def now(self) -> datetime: ...
    def utcnow_iso_ms(self) -> str: ...
```

Invariants:

- `now()` MUST be monotonically non-decreasing across a run.
- `utcnow_iso_ms()` MUST agree with `now()` formatted as ISO-8601 millisecond UTC; mismatch is a bug.
- ReplayClock is the ONLY clock the engine uses; any system-clock read inside the guarded scope raises `WallClockLeakError` (R-B2).

### `BacktestBroker` (in-memory)

```python
class BacktestBroker:
    adapter_id: Literal["backtest-mock-v1"]  # appears in every ORDER_SUBMITTED payload

    def submit_order(self, req: OrderRequest, *, now: datetime, bar: OHLCVBar) -> OrderResult: ...
    def cancel_order(self, kis_order_id: str) -> None: ...
    def list_open_orders(self) -> list[OpenOrder]: ...
```

Invariants:

- The router's adapter equality check (`adapter_id == "backtest-mock-v1"`) is the defense-in-depth boundary (FR-B06). A live broker reaching the router during a backtest is detected here and fails the run.
- Fill semantics follow R-B3 (pessimistic with zero slippage).

### `JudgmentStub`

```python
class JudgmentStub:
    def decide(self, *, decision_class: str, inputs: dict) -> dict: ...
```

Invariants:

- Every call emits `LLM_CALL_STUBBED` to the audit log.
- The returned dict MUST be the rule-declared "safe default" branch for that `decision_class`.
- Spec 004 (future) MUST honour `BACKTEST_MODE=1` env var and switch to the stub; an `AnthropicClient` constructed under `BACKTEST_MODE=1` is a `BACKTEST_JUDGMENT_LEAK` `ERROR`.

### `SyntheticShockDay`

```python
class SyntheticShockDay(BaseModel):
    name: str                              # human label, e.g., "covid_circuit_breaker_2020_03_12"
    session_date: date
    expected_gate_trip: str | None         # e.g., "global_exposure" or None for sanity-only days
```

v1 ships four entries (FR-B09); list is configurable in `config/synthetic_shocks.toml` (a NEW non-Kernel file). Adding a date is operator-only because it expands the safety surface (spec 007 promotion criteria).

### `DataQualityWarning`

```python
class DataQualityWarning(BaseModel):
    symbol: str
    session_date: date | None              # None for cross-day issues like gaps
    kind: Literal[
        "zero_volume_regular",
        "gap_over_7_days",
        "delisted_after",
        "pre_listing",
        "schedule_tag_mismatch",
    ]
    note: str
```

## Audit-log payloads (the K4 one-time touch)

Three new `EventType` literals appended to `src/auto_invest/persistence/audit.py`. No table-schema change. No SQL migration.

### `BACKTEST_STARTED`

```python
class BacktestStartedPayload(BaseModel):
    event_type: Literal["BACKTEST_STARTED"] = "BACKTEST_STARTED"
    run_id: str
    invoker: Literal["cli", "canary"]
    ruleset_sha256: str
    dataset_version: str
    date_start: str                    # ISO date
    date_end: str
    replay_seed: int
    fill_model: Literal["pessimistic_zero_slip"]
    judgment_mode: Literal["stub"]
    synthetic_shock: bool
    correlation_id: str                # ALWAYS equal to run_id (R-B5)
```

### `BACKTEST_COMPLETED`

```python
class BacktestCompletedPayload(BaseModel):
    event_type: Literal["BACKTEST_COMPLETED"] = "BACKTEST_COMPLETED"
    run_id: str
    outcome: Literal["completed", "failed"]
    failure_reason: str | None         # set iff outcome == "failed"
    aggregate_return_pct: str          # Decimal serialised canonical
    aggregate_max_drawdown_pct: str
    aggregate_sharpe: str
    total_orders: int
    total_fills: int
    total_gate_rejections: int
    correlation_id: str                # == run_id
```

### `LLM_CALL_STUBBED`

```python
class LLMCallStubbedPayload(BaseModel):
    event_type: Literal["LLM_CALL_STUBBED"] = "LLM_CALL_STUBBED"
    run_id: str
    decision_class: str
    input_sha256: str                  # over canonical-JSON of `inputs`
    stubbed_branch: str                # name of the rule's safe-default branch
    correlation_id: str                # == run_id
```

### Reused (NO new event types created for these)

| Condition | Reuses event type | Payload note |
|-----------|-------------------|--------------|
| Wall-clock leak | `ERROR` | `reason="WALL_CLOCK_LEAK"`, `where=<module:line>`, `run_id`, `correlation_id=run_id` |
| Real-LLM-call attempt during backtest | `ERROR` | `reason="BACKTEST_JUDGMENT_LEAK"`, `decision_class`, `run_id` |
| Kernel-touched working tree at backtest start | `ERROR` | `reason="BACKTEST_BLOCKED_KERNEL_TOUCH"`, `touched_paths`, `run_id` |
| Live-broker adapter reaches router during backtest | `ERROR` | `reason="BACKTEST_LIVE_BROKER_LEAK"`, `adapter_id_seen`, `run_id` |
| OHLCV data quality issue at ingest | existing `DATA_QUALITY_ISSUE` | reuses fields from spec 001 |

This keeps the K4 surface to literally three additions.

## On-disk per-run layout

```text
data/backtest/<run_id>/
├── backtest-run.json                 # BacktestRun + BacktestSummary, JSON
├── summary.md                        # human-readable (User Story 3)
├── metrics.csv                       # one row per rule + aggregate row
├── per-rule/
│   └── <rule_id>/
│       ├── orders.json               # [{ts, side, qty, limit, status, ...}]
│       ├── fills.json                # [{ts, side, qty, fill_price, ...}]
│       └── gate-rejections.json      # [{ts, gate, observed, limit, ...}]
└── _meta/
    └── kernel-guard-report.json      # snapshot of kernel_diff_check() at run start
```

Invariants:

- Directory is created at `BACKTEST_STARTED` and made read-only (`chmod -w`) at `BACKTEST_COMPLETED`. v1 enforces this with a `chmod` call on POSIX; on Windows the runtime check is best-effort.
- `metrics.csv` column order: `rule_id, symbol, total_return_pct, max_drawdown_pct, sharpe, order_count, fill_count, total_gate_rejections, notional_usd`. Aggregate row has `rule_id="_aggregate"`. Decimals canonicalised to 6 dp.
- Sort orders within each per-rule JSON: by `ts` ascending, then by stable insertion order for ties. Determinism (FR-B15) depends on this.

## Filtering invariants for live observability

Spec 001's `auto-invest report` and `auto-invest status` CLIs query `audit_log`. They MUST filter out the three new event types so backtest activity does not pollute live PnL or live position state. The query change is one line in `reports/daily.py` and one in `cli.py` (live-status path), and is part of this spec's task list.

## Invariants reaffirmed (cross-reference to spec)

- FR-B01 — no edits to K6 (`worker/schedule.py`); confirmed by import-only usage of `is_session_open(now)`.
- FR-B06 — `BacktestBroker.adapter_id == "backtest-mock-v1"` is the boundary.
- FR-B08 — `LLM_CALL_STUBBED` is emitted; `BACKTEST_JUDGMENT_LEAK` `ERROR` blocks real calls.
- FR-B11 — directory layout above matches the spec verbatim.
- FR-B15 — Decimal canonicalisation + stable sort + volatile-field exclusion list (`run_id`, `start_ts`, `end_ts`) is sufficient and necessary.
- FR-B16 — `HistoricalDataSource` protocol is defined in `contracts/historical-data-source.md`; v1 ships exactly one adapter (`CSVDataSource`).
