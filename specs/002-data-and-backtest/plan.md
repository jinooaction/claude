# Implementation Plan: Multi-Asset Data Infrastructure & Backtest Engine

**Branch**: `claude/investment-automation-setup-8KPrZ` | **Date**: 2026-05-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-data-and-backtest/spec.md`

## Summary

Spec 001 shipped a safe execution shell but no measurement layer. This
plan turns constitution principle VI (`backtest → canary → full-live`)
into machinery. Two coupled deliverables:

1. **A unified, asset-class-agnostic historical data store** that
   accepts pluggable ingestion adapters (KIS for US equities first; a
   public crypto vendor as the always-open second adapter), tracks
   `as_of_ts` separately from content timestamps for point-in-time
   correctness, and stores OHLCV plus generic `event_series` records
   (corporate actions, fundamentals, news) under a single schema.
2. **A deterministic, point-in-time backtest engine** that replays
   spec 001's TOML rules (and, optionally, programmatic strategy
   modules) over a chosen historical window, applies the *same* risk
   gate code path as the live router, simulates execution with
   itemised costs (commission, slippage, market impact), supports
   walk-forward and held-out OOS evaluation, and emits a
   reproducible report under `data/backtests/<run_id>/`.

A "promotion seal" file then binds a rule-snapshot hash to a
threshold-clearing OOS backtest result; the live worker refuses to
load any rule whose seal is missing or stale. This closes the loop:
no rule reaches canary or full-live without a measured backtest, and
live-vs-backtest divergence becomes a first-class daily metric — the
first primitive of the self-improving loop in the operator's north
star (CLAUDE.md).

## Technical Context

**Language/Version**: Python 3.11 (matches spec 001; no upgrade in 002).
**Primary Dependencies**:
- Reuse: `httpx`, `pydantic` v2, `tenacity`, `exchange_calendars`,
  `pandas`, `numpy`, `ta`, `tomllib` (stdlib).
- New: `pyarrow` (forward-compatible Parquet path; in v2 used only
  for `to_arrow` export of bars, not as primary store — see R-5).
- New (test fixture only): `respx` is already a test dep; we will
  add a small recorded-fixtures dir for the second adapter (no new
  prod dependency).

**Storage**:
- Primary: extend the existing SQLite database (`data/auto_invest.db`)
  with new tables (`historical_bars`, `event_series`,
  `corporate_actions`, `data_quality_events`, `backtest_runs`,
  `promotion_seals`). All append-only or revision-tracked; see
  `data-model.md`.
- Backtest run artifacts: filesystem under `data/backtests/<run_id>/`
  (one directory per run, immutable after completion).
- Promotion seals: filesystem under `data/promotions/<seal_id>.toml`.

**Testing**: `pytest` (matches v1), with three new test categories:
`tests/integration/backtest/`, `tests/integration/ingestion/`,
`tests/unit/data_store/`. Live HTTP gated by `KIS_LIVE_TEST=1` and
`CRYPTO_LIVE_TEST=1` (one gate per vendor). All non-live tests use
recorded fixtures.

**Target Platform**: Linux / macOS CLI, single-process. Same operator
hardware assumption as v1 (a personal machine; ≥ 8 GB RAM, ≥ 2 cores).

**Project Type**: CLI + library, single repo. Same shape as v1.

**Performance Goals**:
- Single-instrument 5-year OHLCV backtest completes in < 60 s on
  operator hardware (SC-003).
- Resident memory stays < 1 GB on the same workload (FR-B-009 / SC-003).
- Ingestion of one trading day of US-equity 1-minute bars across the
  current whitelist completes in < 30 s on a clean connection.

**Constraints**:
- Constitution v1.0.0 binding. Risk-gate code path used by the
  backtest engine MUST be the same import as the live router (SC-005).
- Point-in-time correctness MUST be enforced at the data-store read
  layer, not just by convention (FR-B-002).
- Backtest output MUST be deterministic byte-for-byte under fixed
  inputs and a pinned `as_of_ts` (FR-B-001 / SC-002).

**Scale/Scope**:
- v2 covers ≤ 50 instruments across ≤ 3 venues, ≤ 5 years of 1-minute
  bars per instrument. Beyond that scale (e.g., a full US universe of
  ~10k tickers) we revisit the storage backend (R-5) but the schema
  is forward-compatible.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Mapped against constitution v1.0.0 principles:

| Principle | Compliance | Notes |
|---|---|---|
| **I. Position Sizing & Exposure Limits** | ✅ | Backtest engine imports the same `risk/` module as the live router. Divergence is a P0 bug per SC-005. No new sizing logic in 002. |
| **II. Deny-by-Default (Whitelist)** | ✅ | Whitelist gate runs in the backtest router exactly as in live. Ingestion adapters are gated by an `enabled_adapters` list in `config/data.toml`; an unknown adapter is auto-rejected. |
| **III. Claude Is Invoked Only at Defined Judgment Points** | ✅ (trivial) | 002 contains zero LLM calls. Sibling spec 004 will introduce judgment points; 002 leaves no hooks that bypass principle III. |
| **IV. Append-Only Audit Log + Daily Reconciliation** | ✅ | `historical_bars`, `event_series`, `backtest_runs`, `promotion_seals` are all append-only (revisions write a new row with a fresh `as_of_ts`). Backtest run directories are immutable after completion. |
| **V. Secret Isolation** | ✅ | New ingestion adapters with credentials register secrets via the existing `register_secret()` helper (R-8 in spec 001 research). The public crypto adapter (R-2 below) is keyless, so this surface stays small in v2. |
| **VI. Staged Rollout: Backtest → Canary → Full Live** | ✅ (operationalised) | This spec is the first to make principle VI testable. Promotion seals (FR-P-001, FR-P-002) refuse rules that lack a threshold-clearing OOS backtest. |
| **VII. External API Robustness** | ✅ | New ingestion adapters reuse the existing `tenacity` retry, `AsyncTokenBucket` rate limiter, and `CircuitBreaker` from spec 001. No new resilience framework. |
| **VIII. Change Discipline** | ✅ (trivial) | The backtest engine is offline; running it cannot deploy code into a live session. Ingestion adapters that hit live vendors honour the same rate-limit / breaker discipline as the live KIS adapter. |

**Investment Domain Constraints (constitution §)**:

- The constitution lists "Initial scope: US listed equities" and an
  out-of-scope list (derivatives, leverage, short, options, futures,
  crypto, domestic Korean equities). This is a constraint on
  **trading**, not on **data ingestion or backtest**.
- 002 ingests crypto data (for the always-open calendar test path)
  but does **not** trade crypto. Any future trading spec for a new
  asset class will require a constitution amendment commit before it
  ships (planned in HANDOFF.md).

**Result**: ✅ all gates pass. No `Complexity Tracking` entries needed.

### Post-Design Constitution Re-check (after Phase 1)

After completing Phase 1 (`data-model.md`, `contracts/`,
`quickstart.md`), re-evaluated:

- **I**: `data-model.md` confirms `Whitelist` from spec 001 is
  authoritative; instruments missing from the whitelist are rejected
  even for backtest. No new sizing logic.
- **II**: `config/data.toml` ships with empty `enabled_adapters`;
  every adapter is opt-in.
- **III**: Phase 1 contracts contain zero LLM surface.
- **IV**: every new SQLite table in `data-model.md` carries `frozen`
  + a UPDATE/DELETE-blocking trigger; backtest run directories are
  immutable post-completion; revocation writes a new seal file
  rather than mutating the existing one.
- **V**: `contracts/ingestion-adapter.md` requires
  `register_secret()` for any auth-bearing adapter before tokens
  reach a logger; the v2 second adapter (public crypto) is keyless,
  keeping the surface minimal.
- **VI**: `contracts/promotion-seal.md` makes principle VI
  machinery — the worker's seven-step verification refuses any
  rule whose seal is missing or stale.
- **VII**: `contracts/ingestion-adapter.md` requires reuse of
  `tenacity` retry, `AsyncTokenBucket`, and `CircuitBreaker` from
  spec 001; a shared conformance test enforces this.
- **VIII**: backtest engine is fully offline; no live-deploy
  semantics introduced.

**Result**: ✅ Phase 1 design also passes all gates. Ready for `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/002-data-and-backtest/
├── plan.md                 # This file
├── research.md             # Phase 0 (R-1 … R-6)
├── data-model.md           # Phase 1 — entities + SQLite schema
├── quickstart.md           # Phase 1 — operator walkthrough
├── contracts/              # Phase 1
│   ├── backtest-cli.md     # auto-invest backtest / promote / data CLI
│   ├── backtest-config.md  # backtest TOML config shape
│   ├── ingestion-adapter.md# IngestionAdapter Python interface
│   └── promotion-seal.md   # promotion seal TOML format
├── spec.md
└── tasks.md                # Phase 2 (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/auto_invest/
  config/                  # extended
    data.py                # NEW: data-source config (enabled adapters, etc.)
    backtest.py            # NEW: backtest run config schema
  market_data/             # extended
    adapters/              # NEW: pluggable ingestion adapters
      __init__.py          # IngestionAdapter ABC + registry
      kis_us_equity.py     # NEW: wraps existing KIS adapter into the ABC
      crypto_public.py     # NEW: public crypto bars (always-open calendar)
    store.py               # extended: HistoricalRecord, event_series schema
    revisions.py           # NEW: as_of_ts handling + revision queries
    quality.py             # extended: gap + vendor-disagreement detection
    calendar.py            # NEW: MarketCalendar abstraction (discrete vs always-open)
  backtest/                # NEW (entire module)
    __init__.py
    engine.py              # event-driven replay loop
    cost_model.py          # commission + slippage + impact
    portfolio.py           # cash + position accounting in the simulator
    metrics.py             # returns, Sharpe, drawdown, hit rate, ...
    walkforward.py         # walk-forward + OOS reservation
    report.py              # markdown + JSON report writer
    determinism.py         # seed plumbing + hash pinning
  promotion/               # NEW
    __init__.py
    seal.py                # write/read/validate promotion seals
    thresholds.py          # OOS metric thresholds
    divergence.py          # live-vs-backtest divergence metric
  risk/                    # untouched in 002 (single source of truth)
  execution/               # extended: router accepts a backtest broker
    backtest_broker.py     # NEW: simulates fills using cost_model
  worker/                  # extended: refuse rules without a valid seal
  cli.py                   # extended: backtest / promote / data subcommands

tests/
  unit/
    backtest/              # NEW
    market_data/           # extended
    promotion/             # NEW
  integration/
    backtest/              # NEW: end-to-end run + determinism
    ingestion/             # NEW: per-adapter recorded-fixture tests
    promotion/             # NEW: seal pipeline + worker rejection
  fixtures/
    historical/            # NEW: pinned recorded data slices for CI
    backtests/             # NEW: golden run output for determinism check
```

**Structure Decision**: keep the v1 layout, add new top-level modules
(`backtest/`, `promotion/`) and new submodules under existing packages
(`market_data/adapters/`, `config/data.py`, `config/backtest.py`,
`execution/backtest_broker.py`). The `risk/` package is **not** edited
beyond making it import-clean from both the live router and the
backtest router (single source of truth — SC-005).

## Complexity Tracking

No constitution-check violations to justify. This section intentionally empty.
