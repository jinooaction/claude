# Phase 1 Data Model — Hardened Canary

**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Research**: [research.md](./research.md)
**Date**: 2026-05-14

## Entities

### `CanaryRun` (pydantic model, lives in `auto_invest.canary.data_model`)

| Field | Type | Notes |
|-------|------|-------|
| `canary_run_id` | `uuid.UUID` | UUID4, generated at `CANARY_ENTERED` emission. |
| `candidate_rev` | `str` | Resolved git SHA-40, NOT a ref. |
| `baseline_rev` | `str` | Resolved git SHA-40 (per R-C1). |
| `tier` | `Literal["L2", "L3"]` | L1 is rejected at CLI parse. |
| `window_trading_days` | `int` | From `config/canary_bands.toml` `[L<tier>].trading_days`. |
| `window_start_date` | `date` | First trading day in the historical replay window. |
| `window_end_date` | `date` | Last trading day; inclusive. |
| `started_at` | `datetime` | UTC, ISO 8601 with ms. |
| `finished_at` | `datetime \| None` | None until terminal event. |
| `outcome` | `Literal["passed", "failed", "in_progress"]` | Default `in_progress`. |
| `failing_metrics` | `list[str]` | Empty on pass; subset of the 5 metric ids on fail. |
| `kernel_touches` | `list[KernelTouch]` | Empty if no kernel-path intersection. |
| `metrics` | `CanaryMetrics` | Filled progressively as sub-stages complete. |
| `seed_bundle` | `SeedBundle` | Captures Hypothesis seed + window-replay nonces for SC-C04. |

### `KernelTouch`

| Field | Type | Notes |
|-------|------|-------|
| `group` | `Literal["K1", "K2", "K3", "K4", "K5", "K6", "K_meta"]` | From `kernel.toml` table key. |
| `files` | `list[str]` | Touched paths in this group. |

### `CanaryMetrics`

| Field | Type | Notes |
|-------|------|-------|
| `pnl_drawdown_pct` | `MetricResult` | Observed max-drawdown delta candidate vs baseline. |
| `risk_gate_violations` | `MetricResult` | Count of new `ORDER_REJECTED_BY_GATE` rows under candidate replay. |
| `audit_integrity_failures` | `MetricResult` | Count of `DATA_QUALITY_ISSUE` rows above baseline-mean threshold. |
| `latency_p95_regression_pct` | `MetricResult` | `(candidate_p95 - baseline_p95) / baseline_p95`. |
| `llm_cost_regression_pct` | `MetricResult` | `(candidate_usd_per_decision - baseline_usd_per_decision) / baseline_usd_per_decision`. |

### `MetricResult`

| Field | Type | Notes |
|-------|------|-------|
| `observed_value` | `float` | The actual measurement. |
| `band_upper` | `float \| None` | Configured band upper bound; None if metric is "must equal 0". |
| `band_must_equal` | `int \| None` | 0 for the two count metrics (gate-violations, audit-integrity). |
| `inside_band` | `bool` | Computed at decision time. |
| `source` | `Literal["window_replay", "synthetic_shock", "telemetry_unused"]` | Provenance. |

### `FuzzCounterexample`

| Field | Type | Notes |
|-------|------|-------|
| `seed` | `int` | Hypothesis seed that produced it. |
| `shrunk_input` | `dict[str, Any]` | The minimised counterexample (Hypothesis-shrunk). |
| `assertion_failed` | `str` | Which post-condition broke (`per_trade<=per_symbol`, `per_symbol<=global`, etc.). |
| `gate_decision` | `dict[str, Any]` | Serialised `GateDecision` returned by the gate under test. |

### `SeedBundle`

| Field | Type | Notes |
|-------|------|-------|
| `hypothesis_database_seed` | `int` | Top-level seed for the fuzz pass. |
| `hypothesis_iterations` | `int` | ≥ 10_000 per FR-C04. |
| `synthetic_shock_dates` | `list[date]` | Resolved at run start; recorded for reproducibility. |
| `quarterly_opex_resolved_for` | `date` | The `most_recent_quarterly_opex` result on `started_at.date()`. |

---

## Audit-event payloads (K4 additive touch)

Four new event types appended to `EventType` Literal in `src/auto_invest/persistence/audit.py`. Each has a corresponding pydantic payload model. All payloads are frozen and reject extra fields.

### `CANARY_ENTERED`

```python
class CanaryEnteredPayload(AuditPayload):
    event_type: Literal["CANARY_ENTERED"] = "CANARY_ENTERED"
    canary_run_id: str             # UUID4 stringified
    candidate_rev: str             # SHA-40
    baseline_rev: str              # SHA-40
    tier: Literal["L2", "L3"]
    window_trading_days: int
    window_start_date: str         # YYYY-MM-DD
    window_end_date: str           # YYYY-MM-DD
    bands_snapshot: dict[str, Any] # subset of config/canary_bands.toml [<tier>]
```

### `CANARY_KERNEL_TOUCH_DETECTED`

```python
class CanaryKernelTouchDetectedPayload(AuditPayload):
    event_type: Literal["CANARY_KERNEL_TOUCH_DETECTED"] = "CANARY_KERNEL_TOUCH_DETECTED"
    canary_run_id: str
    candidate_rev: str
    touched_groups: list[str]      # e.g. ["K1", "K4"]
    touched_files: list[str]       # full path list
```

### `CANARY_PASSED`

```python
class CanaryPassedPayload(AuditPayload):
    event_type: Literal["CANARY_PASSED"] = "CANARY_PASSED"
    canary_run_id: str
    candidate_rev: str
    baseline_rev: str
    tier: Literal["L2", "L3"]
    finished_at: str               # ISO 8601 UTC ms
    artefact_path: str             # data/canary/<canary_run_id>/canary-run.json
```

### `CANARY_FAILED`

```python
class CanaryFailedPayload(AuditPayload):
    event_type: Literal["CANARY_FAILED"] = "CANARY_FAILED"
    canary_run_id: str
    candidate_rev: str
    baseline_rev: str
    tier: Literal["L2", "L3"]
    finished_at: str
    failing_metrics: list[str]     # e.g. ["pnl_drawdown_pct", "llm_cost_regression_pct"]
    artefact_path: str
```

`audit_log` correlation: every event in a canary run uses `correlation_id = canary_run_id` so `read_by_correlation(conn, canary_run_id)` retrieves the full sequence.

---

## State machine — `CanaryRun.outcome`

```
                          ┌─────────────┐
                          │ in_progress │  (set at CANARY_ENTERED)
                          └──────┬──────┘
                                 │
              ┌──────────────────┴─────────────────────┐
              │ all 5 metrics inside-band              │ any metric outside band
              │ + zero gate-violations in shock        │ OR ≥1 fuzz counterexample
              │ + zero audit-integrity failures        │ OR ≥1 gate-violation in shock
              │ + zero fuzz counterexamples            │
              ▼                                        ▼
       ┌──────────────┐                          ┌──────────────┐
       │   passed     │  → CANARY_PASSED emit    │   failed     │  → CANARY_FAILED emit
       │  (terminal)  │                          │  (terminal)  │
       └──────────────┘                          └──────────────┘
```

`in_progress` is never persisted in audit (only `canary-run.json` carries it). If the harness crashes mid-run, the on-disk `canary-run.json` remains `in_progress` and no terminal audit row is emitted; the next canary run for the same `(candidate_rev, baseline_rev)` is allowed to start (it gets a fresh `canary_run_id`).

---

## On-disk layout — `data/canary/<canary_run_id>/`

```text
data/canary/<canary_run_id>/
├── canary-run.json                  # the CanaryRun model serialised; the canonical artefact
├── metrics.csv                      # one row per metric: id, observed_value, band, inside_band, source
├── shock-replay/
│   ├── 2020-03-12/
│   │   ├── audit_log.json           # ordered list of audit rows emitted during the shock replay
│   │   └── backtest-run.json        # copy of the per-day spec-008 artefact
│   ├── 2020-04-20/...
│   ├── 2024-08-05/...
│   └── <YYYY-MM-DD>/                # the resolved quarterly OPEX date
├── replay-window/
│   ├── candidate/
│   │   ├── audit_log.json
│   │   ├── backtest-run.json
│   │   └── metrics.csv
│   └── baseline/
│       ├── audit_log.json
│       ├── backtest-run.json
│       └── metrics.csv
└── property-fuzz/
    ├── seeds.txt                    # one seed per line; first line is the database seed (SeedBundle.hypothesis_database_seed)
    └── counterexamples.json         # list[FuzzCounterexample]; empty on pass
```

**Deterministic write order**: artefacts are written in the order replay-window → shock-replay → property-fuzz → canary-run.json. `canary-run.json` is written LAST so its presence is a guarantee that all sub-artefacts are also complete. The terminal audit row is emitted AFTER `canary-run.json` is fsynced.

**Reproducibility contract (SC-C04)**: re-running with the same `(candidate_rev, baseline_rev, hypothesis_database_seed, window_start_date)` MUST produce byte-identical files MODULO `canary-run.json.started_at` and `canary-run.json.finished_at`. Tested by `tests/integration/test_canary_reproducibility.py`.

---

## Configuration — `config/canary_bands.toml`

```toml
# Acceptance bands for the hardened canary (spec 007 / constitution v3.0.0 IX.B-2).
# Edit and PR to amend. Schema validated by auto_invest.canary.bands at load time.

[L2]
trading_days = 30
pnl_drawdown_pct = 3.0                 # FR-C01 #1
risk_gate_violations = 0               # FR-C01 #2 — must equal 0
audit_integrity_failures = 0           # FR-C01 #3 — must equal 0
latency_p95_regression_pct = 20.0      # FR-C01 #4
llm_cost_regression_pct = 10.0         # FR-C01 #5

[L3]
trading_days = 45                       # FR-C02
pnl_drawdown_pct = 2.0                  # stricter for L3 by default
risk_gate_violations = 0
audit_integrity_failures = 0
latency_p95_regression_pct = 15.0
llm_cost_regression_pct = 7.5
```

Loader rejects: negative numbers, missing keys, unknown tier names, `trading_days < 30`.

---

## Hypothesis target — fuzz post-conditions

`auto_invest.canary.fuzz.fuzz_risk_gates` exposes one Hypothesis strategy and one property:

```python
@given(
    sizing_caps=sizing_caps_strategy(),       # SizingCaps with per_trade < per_symbol < global
    request_qty=qty_strategy(),                # int in [1, 10_000]
    current_symbol_exposure=exposure_strategy(),# Decimal in [0, 1]
    current_global_exposure=exposure_strategy(),
    quote_price=price_strategy(),              # Decimal in [0.01, 10_000]
)
def test_cap_chain_monotonicity(sizing_caps, request_qty, ...):
    request = OrderRequest(qty=request_qty, ...)
    per_trade  = per_trade_cap_gate(request, sizing_caps, quote_price)
    per_symbol = per_symbol_cap_gate(request, sizing_caps, quote_price, current_symbol_exposure)
    glob       = global_exposure_gate(request, sizing_caps, quote_price, current_global_exposure)

    # Post-condition: if per_trade allows, per_symbol either allows or denies for non-K1 reason.
    # Mathematical invariant: order_value <= per_trade_cap_usd <= per_symbol_cap_usd <= global_cap_usd.
    if per_trade.allow:
        order_value = quote_price * request_qty
        assert order_value <= sizing_caps.per_trade_cap_usd, "per_trade gate allowed an over-cap order"
    if per_symbol.allow:
        assert (current_symbol_exposure + order_value) <= sizing_caps.per_symbol_cap_usd, \
            "per_symbol gate allowed exceeding the per-symbol cap"
    if glob.allow:
        assert (current_global_exposure + order_value) <= sizing_caps.global_cap_usd, \
            "global gate allowed exceeding the global cap"
```

The fuzz harness wraps Hypothesis to capture every failure as a `FuzzCounterexample` and persists them under `property-fuzz/counterexamples.json`. The harness exits non-zero only after all iterations complete (it does NOT short-circuit on the first counterexample — full counterexample sets are valuable forensic data).
