# Implementation Plan: Backtest Engine

**Branch**: `claude/continue-work-ID7Ec` (working branch; spec dir: `specs/008-backtest-engine/`)
**Date**: 2026-05-13
**Spec**: [spec.md](./spec.md) (clarified 2026-05-13)
**Input**: Feature specification from `specs/008-backtest-engine/spec.md`

## Summary

Build a deterministic, offline replay engine, packaged under `src/auto_invest/backtest/`, that drives the existing `Worker.tick` / risk-gate / order-router code path against historical OHLCV. Output is a per-rule, per-run report (return / drawdown / Sharpe / order counts / gate-rejection breakdown) plus a structured on-disk artefact under `data/backtest/<run_id>/`. The engine introduces three new audit-event types (`BACKTEST_STARTED`, `BACKTEST_COMPLETED`, `LLM_CALL_STUBBED`) — a one-time additive K4 touch acknowledged in the spec's Constitutional fit section and approved at merge time per principle IX.B-1.

Two critical safety properties are non-negotiable:

1. **Determinism (FR-B15)** — re-running with the same inputs produces byte-identical per-rule outputs (modulo `run_id` and `start_ts`). Spec 007's hardened canary depends on this.
2. **No live side effects** — a backtest MUST NEVER issue a real broker order (FR-B06) or a real Anthropic call (FR-B08). Both are enforced by hard fails (`BACKTEST_JUDGMENT_LEAK`, in-memory-only broker adapter) plus a `WALL_CLOCK_LEAK` guard on system-clock reads.

The engine ships one OHLCV adapter (operator-provided CSV ingest); the `HistoricalDataSource` protocol is designed so yfinance / KIS-historical / IEX-Cloud adapters can be added by later specs without engine changes.

## Technical Context

**Language/Version**: Python 3.11 (matches spec 001's existing toolchain).
**Primary Dependencies**:
- `pandas` — already in `pyproject.toml` (spec 001 R-2); used for OHLCV in-memory representation and Sharpe / drawdown math.
- `pydantic` v2 — already in deps; CSV schema validation, `BacktestRun` model, `RuleBacktestResult` model.
- `sqlite3` (stdlib) — append-only audit log shared with the live worker.
- `tomllib` (stdlib) — ruleset loading (reused from spec 001).
- `numpy` — pulled in transitively by pandas; vectorised drawdown/Sharpe.
- **No new third-party dependencies in v1.** Vendor adapters (yfinance, IEX) deferred to later specs.

**Storage**:
- Backtest run header + summary metrics → audit_log rows (`BACKTEST_STARTED`, `BACKTEST_COMPLETED`), same SQLite file as the live worker. `correlation_id = run_id`.
- Per-run artefacts → `data/backtest/<run_id>/` directory tree (immutable after `BACKTEST_COMPLETED`).
- Historical OHLCV → `data/history/<dataset_version>/<symbol>.parquet` (operator-provided CSV is converted to parquet at ingest time for fast columnar reads). Dataset version is the SHA-256 of the sorted list of input CSV file digests.

**Testing**: `pytest` + `pytest-asyncio` (existing); two new test modules:
- `tests/unit/test_backtest_*.py` — clock guard, fill model, replay determinism, CSV validation, kernel-guard integration.
- `tests/integration/test_backtest_end_to_end.py` — full one-rule one-year replay against a tiny fixture CSV; verifies byte-identical re-run.

**Target Platform**: Same as live worker — Linux long-running Python 3.11 process. Backtest runs are short-lived CLI invocations on the operator's MacBook or a CI runner; no daemon.

**Project Type**: Adds one new module (`backtest/`) and one new CLI subcommand to the existing single-package `auto_invest` CLI. No new processes or services.

**Performance Goals (SC-B01 derivative)**:
- Full one-year replay over ≤10 rules and ≤20 symbols completes in < 5 min on operator's local hardware.
- CSV→parquet ingest of one year × 20 symbols completes in < 30 s.
- `metrics.csv` and per-rule JSON files write in < 1 s combined.

**Constraints**:
- **Determinism**: every operation that affects on-disk output MUST be deterministic given inputs. Random-number paths (none currently) would need explicit seeding.
- **No live calls**: in-memory broker mock is the ONLY broker adapter wired during a backtest run. The engine MUST fail-fast if a real broker reaches the router during replay (defense-in-depth).
- **Kernel guard at startup**: the backtest CLI consults `auto_invest.deploy.kernel_guard.kernel_diff_check` against `git status --porcelain` before launching (FR-B12). Uncommitted Kernel modifications block the run.
- **Append-only audit**: new event types only; zero UPDATE/DELETE on `audit_log`. The K4 touch is one-time at merge.
- **Memory**: a year × 20 symbols × ~252 bars/year × 6 columns ≈ 30k rows, trivial. No streaming required in v1; pandas in-memory load is acceptable.

**Scale/Scope (v1)**:
- One backtest run at a time per machine (no parallel runs in v1).
- ≤ 20 symbols per run, ≤ 10 rules per run, ≤ 5 years per run (matches v1 operator profile).
- One-shot synthetic-shock replay covers exactly 4 dates by default; configurable.
- Single asset class: US-listed equities. FX / futures / options OUT of v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan satisfies it | Status |
|---|-----------|---------------------------|--------|
| I | Position Sizing & Exposure Limits | Backtest re-uses `risk/gates.py` unchanged. Property: a tightening change to gates can only reduce or preserve fill counts in any historical replay (verified by spec 007's property fuzz, which this engine enables). | ✅ pass |
| II | Deny-by-Default (Whitelist) | Engine loads the SAME whitelist as the live worker; reuses `config/whitelist.py` (K2) without modification. Rules referencing non-whitelisted symbols are rejected at load time (same behavior as spec 001 user-story 1 acceptance #2). Historical whitelist drift is documented as out-of-scope (Assumption #6). | ✅ pass |
| III | Claude at Defined Judgment Points Only | FR-B08 forbids real Anthropic calls during backtest. Stub interface emits `LLM_CALL_STUBBED`; real-call attempt fails the run with `BACKTEST_JUDGMENT_LEAK`. This actively DEFENDS principle III against future spec 004 introducing a backtest-time cost leak. | ✅ pass |
| IV | Append-Only Audit Log + Daily Reconciliation | New event types are append-only. No UPDATE/DELETE introduced. `audit_log` table schema is unchanged (`event_type` is already a Union; we extend the Union). Daily reconciliation is unaffected — backtest rows have `correlation_id = run_id` and are filtered out of live PnL by event-type. | ✅ pass (one-time K4 touch acknowledged below) |
| V | Secret Isolation | Backtest reads NO secrets. Replay uses no real broker, no real LLM. `.env` is not loaded for a backtest CLI invocation. Logging redaction filter remains installed for safety. | ✅ pass |
| VI | Backtest → Canary → Full Live | This feature IS the Backtest stage. Before it, principle VI's first stage was a paper rule. | ✅ pass |
| VII | External API Robustness | No external APIs are called during a backtest. Vacuously satisfied. The OHLCV ingest job (a separate one-shot) reads operator-provided CSV from disk; no network in v1. | ✅ pass |
| VIII | Change Discipline | Backtest is offline; market-hours rule (VIII.A) does not apply. Plan is on a dedicated branch; operator merges via PR. | ✅ pass |
| IX | Self-Modification Boundary | **One-time additive K4 touch acknowledged.** Three event-type literals appended to `src/auto_invest/persistence/audit.py`. The touch is operator-approved at merge time per IX.B-1 — exactly the path spec 006's `kernel_guard` is designed to route. After merge, ongoing backtest operation requires zero further Kernel changes. The engine itself (under `src/auto_invest/backtest/`) is fully outside the Kernel. **The backtest CLI MUST refuse to run if `git status --porcelain` shows any uncommitted modification to a Kernel-listed path (FR-B12)** — defense-in-depth against an experimental Kernel-edited tree being replayed. | ✅ pass (with operator approval at merge) |

**No constitution violations. Complexity Tracking section is intentionally empty.**

## Project Structure

### Documentation (this feature)

```text
specs/008-backtest-engine/
├── plan.md                          # This file (/speckit-plan output)
├── spec.md                          # Clarified 2026-05-13
├── research.md                      # Phase 0 output — R-B1..R-B10 decisions
├── data-model.md                    # Phase 1 output — entities + audit-event schemas + on-disk layout
├── quickstart.md                    # Phase 1 output — operator onboarding for backtest
├── contracts/
│   ├── ohlcv-csv.md                 # CSV ingest format + validation rules
│   ├── backtest-cli.md              # CLI commands + flags + exit codes
│   ├── backtest-run-json.md         # backtest-run.json schema
│   └── historical-data-source.md    # Adapter protocol (CSV in v1; yfinance/IEX later)
├── checklists/
│   └── requirements.md              # Spec quality checklist (updated post-clarify)
└── tasks.md                         # Phase 2 output (/speckit-tasks command — NOT created here)
```

### Source Code (repository root)

```text
src/auto_invest/
├── backtest/                              # NEW PACKAGE — all under here is NON-Kernel
│   ├── __init__.py                        # public surface (BacktestRun, run_backtest, ...)
│   ├── cli.py                             # `auto-invest backtest` subcommand + `ingest-history` subcommand
│   ├── clock.py                           # ReplayClock + Clock protocol + WallClockGuard context manager
│   ├── ingest.py                          # CSV → parquet ingest, dataset versioning, quality checks (FR-B13)
│   ├── data_source.py                     # HistoricalDataSource protocol + CSVDataSource adapter (FR-B16)
│   ├── broker_mock.py                     # In-memory broker that produces pessimistic fills (FR-B07)
│   ├── judgment_stub.py                   # Spec-004 judgment-point stub interface (FR-B08)
│   ├── replay.py                          # Drives Worker.tick across the date range; injects clock + data feed
│   ├── metrics.py                         # Return / drawdown / Sharpe math (per-rule + aggregate)
│   ├── report.py                          # Writes summary.md, metrics.csv, per-rule JSON; emits BACKTEST_COMPLETED
│   ├── synthetic_shocks.py                # Resolves the four canonical shock dates (FR-B09)
│   └── run.py                             # Top-level orchestration: kernel guard → ingest snapshot → audit start → replay → report → audit complete
├── persistence/
│   └── audit.py                           # K4 — one-time touch: append BACKTEST_STARTED, BACKTEST_COMPLETED, LLM_CALL_STUBBED literals + 3 payload models
├── cli.py                                 # WIRING — add the `backtest` and `ingest-history` Typer subcommands
└── ...                                    # everything else UNCHANGED

tests/
├── unit/
│   ├── test_backtest_clock_guard.py       # WALL_CLOCK_LEAK detection
│   ├── test_backtest_csv_ingest.py        # CSV parse + validation + dataset versioning
│   ├── test_backtest_fill_model.py        # pessimistic limit fill semantics (FR-B07)
│   ├── test_backtest_broker_mock.py       # mock never reaches real broker; ORDER_SUBMITTED carries mock adapter id
│   ├── test_backtest_judgment_stub.py     # LLM_CALL_STUBBED emission; BACKTEST_JUDGMENT_LEAK on real call attempt
│   ├── test_backtest_metrics.py           # return/drawdown/Sharpe math on canned series
│   ├── test_backtest_synthetic_shocks.py  # resolves canonical dates
│   └── test_backtest_kernel_guard.py      # backtest CLI refuses to start with uncommitted Kernel diff
└── integration/
    ├── test_backtest_end_to_end.py        # one rule × one year × tiny CSV fixture; verifies all artefacts
    ├── test_backtest_determinism.py       # FR-B15: byte-identical re-run on identical inputs (modulo run_id, start_ts)
    └── test_backtest_synthetic_shock_2020_03_12.py  # SC-B04 gate-trip sanity

data/                                      # gitignored
├── history/                                # NEW — operator-provided CSV converted to parquet
│   └── <dataset_version>/<SYMBOL>.parquet
└── backtest/                               # NEW — per-run artefacts
    └── <run_id>/
        ├── backtest-run.json
        ├── summary.md
        ├── metrics.csv
        └── per-rule/<rule_id>/
            ├── orders.json
            ├── fills.json
            └── gate-rejections.json
```

**Structure Decision**: All new code lives under a single new sub-package `src/auto_invest/backtest/`. This keeps the Kernel surface tiny (one-line K4 touch to extend the event-type Union) and lets every other Kernel-listed module be imported by the engine WITHOUT modification — `risk/gates.py`, `worker/schedule.py`, `config/whitelist.py`, `config/caps.py`, `logging_config.py`, `config/loader.py` are all consumed read-only by the replay path. The Clock injection seam already exists in `Worker.tick(now=...)` and `worker/schedule.py` (which is pure-functional and already takes `now` as argument); the engine simply wires those existing seams.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No new violations. The one-time K4 touch is documented under principle IX in the Constitution Check above and is the precedent path (spec 002 set it). Section intentionally empty.*

## Post-Design Constitution Re-Check

*Per `/speckit-plan` workflow: re-evaluate after Phase 1 design artefacts (research.md, data-model.md, contracts/, quickstart.md) are produced.*

| # | Principle | Re-check after Phase 1 | Status |
|---|-----------|------------------------|--------|
| I | Position Sizing & Exposure Limits | `data-model.md` confirms `risk/gates.py` is imported read-only by `replay.py`; gate-rejection counts are recorded in per-rule JSON. No gate logic is duplicated, mutated, or by-passed. | ✅ pass |
| II | Deny-by-Default (Whitelist) | `data-model.md` confirms whitelist is loaded by reusing `config/whitelist.py`. CSV ingest validates that every (symbol, date) pair belongs to a whitelisted symbol; rules referencing non-whitelisted symbols are dropped at load. | ✅ pass |
| III | Claude at Defined Judgment Points Only | `contracts/historical-data-source.md` and `judgment_stub.py` design guarantee zero outbound LLM calls during replay; `LLM_CALL_STUBBED` audit row is emitted at every stub invocation. | ✅ pass |
| IV | Append-Only Audit Log + Daily Reconciliation | `data-model.md` defines the 3 new payload models (`BacktestStartedPayload`, `BacktestCompletedPayload`, `LLMCallStubbedPayload`); all written via `audit.append()` which is INSERT-only. `current_positions` is untouched (backtest does not write to live position cache). | ✅ pass |
| V | Secret Isolation | `quickstart.md` documents that backtest invocation does NOT load `.env` and does NOT need any secret. Logging redaction filter is still installed (defense-in-depth). | ✅ pass |
| VI | Backtest → Canary → Full Live | This is the backtest stage; report headers state slippage assumption (zero in v1) and fill model (pessimistic) so the operator cannot over-trust. | ✅ pass |
| VII | External API Robustness | No external APIs called during a backtest. `contracts/historical-data-source.md` is offline-only in v1. | ✅ pass |
| VIII | Change Discipline | Backtest is offline; market-hours rule does not apply. Plan ships on a dedicated branch. | ✅ pass |
| IX | Self-Modification Boundary | The K4 touch is one-time; spec 006 kernel guard catches it and routes through operator approval. The backtest CLI itself consults `kernel_diff_check` at startup (FR-B12). After this spec ships, the autonomous tuner can use the engine output but cannot modify the engine's Kernel-touching files. | ✅ pass (with operator approval at merge) |

**No new violations introduced by Phase 1 design. Plan is ready for `/speckit-tasks`.**

## Operator-Visible Notes (read this before approving the merge)

1. **One Kernel file changes.** `src/auto_invest/persistence/audit.py` gains three Literal additions to the `EventType` Union plus three pydantic payload models. No SQL migration. No UPDATE/DELETE pathway. Same precedent as when spec 002 added `migration 0002_token_usage.sql` to K4 — that one needed your sign-off; this one does too.
2. **No live broker, no live LLM.** A backtest run loads no `.env`, opens no broker session, and refuses to issue a real Anthropic call. If you observe an `ORDER_SUBMITTED` audit row whose payload's adapter is anything other than the in-memory mock during a backtest run, that is a bug — please open an issue.
3. **Determinism is a hard contract.** Re-running with the same ruleset, dataset version, and seed must produce byte-identical per-rule artefacts. Spec 007's hardened canary depends on this. Any non-determinism we introduce later (e.g., a future judgment-point fixture mode) becomes a spec amendment, not a casual change.
4. **CSV-only in v1.** You provide the OHLCV (the `ingest-history` job reads CSVs you place under a designated directory). The `HistoricalDataSource` interface is designed to slot in yfinance / KIS-historical / IEX later without changing engine code.
