# Implementation Plan: Backtest Engine

**Branch**: `claude/review-docs-sdd-cycle-SbbBy` (working branch; spec dir: `specs/008-backtest-engine/`)
**Date**: 2026-05-07
**Spec**: [spec.md](./spec.md)
**Constitution**: v2.0.0
**Input**: Feature specification from `specs/008-backtest-engine/spec.md`

## Summary

Build a deterministic, in-process replay engine packaged at `auto_invest.backtest` that drives the existing live pipeline (`Worker.tick` → rule evaluator → `risk/gates.py` → order router) against historical OHLCV bars instead of live KIS quotes, and produces a stable on-disk artifact under `data/backtests/<run_id>/` that the spec 007 hardened canary harness consumes. No live broker contact, no LLM. The engine is non-Kernel by construction (FR-B02); the *first landing* of this feature is the only K-meta event because the new audit migration `0003_backtest_events.sql` is added to `kernel.toml` group K4 in the same change set (per the 2026-05-07 Q3 clarification). After that landing, all subsequent backtest-engine work — vendor adapters, reporting, threshold tuning — is non-Kernel and autonomous-merge-eligible once spec 007 ships.

The engine reuses the live worker code path verbatim by injecting two callables — a historical `quote_provider` and a synthetic `clock` — through new optional kwargs on `Worker.__init__` (a non-Kernel file). Backtest and live therefore execute the same risk-gate, whitelist, sizing-cap, and audit-log code paths, which is what makes a backtest's "passes" usable as a canary input (spec 007 SC-C04 reproducibility, FR-C03 synthetic-shock replay).

## Technical Context

**Language/Version**: Python 3.11 (matches existing project)

**Primary Dependencies** (additions on top of spec 001's stack):
- `yfinance` — OHLCV vendor #1 (FR-B06). Free, daily-adjusted US-equity bars. Pinned minor; isolated to `auto_invest.backtest.ohlcv.yfinance_adapter`.
- `pandas` — already a dependency (spec 001 R-2). Reused for OHLCV manipulation and Sharpe/drawdown math.
- `numpy` — transitive via pandas. Used for vectorised return/Sharpe computation.
- `pydantic` — already a dependency. Used for backtest input config and on-disk artifact schemas.
- `httpx` — already a dependency. Reused by KIS historical adapter (FR-B06 #2) via the existing `ResilientClient`.
- `tomllib` (stdlib) — reads rule TOML, identical to live (constitution VI).
- `click` — already a dependency for the existing CLI; the new `auto-invest backtest` subcommand reuses it.

**Storage**:
- Continues to use the single `data/auto_invest.db` SQLite file with WAL (constitution IV). Backtest events go to the existing `audit_log` table via a new migration `0003_backtest_events.sql`.
- New on-disk artifact tree: `data/backtests/<run_id>/{manifest.json, report.json, daily.csv, fills.csv, audit-events.json}` (FR-B13).
- Named-dataset manifests at `data/ohlcv/datasets/<name>.json` (FR-B19).
- Cached vendor OHLCV at `data/ohlcv/<vendor>/<symbol>.parquet` (or .csv if parquet engine absent), with content hashes recorded in the run manifest (FR-B05).

**Testing**: `pytest` + `pytest-asyncio` (existing). Synthetic deterministic fixtures (sine-wave OHLCV) for arithmetic checks (User Story 2 independent test). Recorded vendor responses via `respx` for `yfinance` HTTP and the existing KIS test rig. Property-based fuzz with `hypothesis` for FR-B12 reproducibility checks.

**Target Platform**: Linux operator workstation (Python 3.11). Same target as the live worker; the engine runs in the same venv on the same machine, sharing the same SQLite WAL. No new platform dependency.

**Project Type**: extension of the existing single-package CLI/worker (`auto_invest`). Adds one subpackage `auto_invest.backtest` plus one persistence migration. No new top-level project.

**Performance Goals**:
- `synthetic_shock_v1` replay (4 dates, ≤ 50 symbols, daily bars) wall-clock < 30 s on the operator's reference machine (SC-B05).
- Year-long daily-OHLCV backtest (252 trading days, 50 symbols, ≤ 20 rules) wall-clock < 60 s, dominated by SQLite append cost not arithmetic.
- Zero perceivable impact on the live worker when run concurrently (SQLite WAL with PRAGMA synchronous = NORMAL).

**Constraints**:
- **Determinism is a hard contract** (FR-B12). All non-deterministic sources must be either eliminated (no system clock; no `random` without seed; no dict ordering reliance on insertion across processes) or surfaced as explicit inputs (seed, dataset_hash, code_sha).
- **No external network egress during replay** (FR-B09). Vendor ingest is a separate phase that runs *before* `BACKTEST_STARTED`; replay reads only from local SQLite + local OHLCV cache.
- **No Kernel file modifications** outside the one-time migration-and-manifest landing (FR-B02; constitution IX.B-1). The deploy-guard wired in spec 006 (`auto_invest.deploy.kernel_guard`) will block any subsequent change set that touches kernel.toml without explicit human review.
- **Append-only invariant** (constitution IV). New `BACKTEST_*` rows go through `persistence/audit.append`; the engine never executes UPDATE or DELETE on `audit_log`.
- **Limit-orders-only by default** (constitution domain constraint). Fill model branches on the live `order_type` (FR-B07) so backtest cannot take a more lenient fill path than live.

**Scale/Scope (v1)**:
- ≤ 50 symbols per backtest run (matches spec 001 whitelist scale).
- ≤ 20 rules per run.
- ≤ 5 years of daily OHLCV per run; intraday bars are explicit follow-up.
- One backtest at a time; no parallel orchestration in v1 (spec 007 also scopes parallelism out).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution at v2.0.0 has nine principles (I–IX). Each is mapped explicitly below. Principle VIII is split (VIII.A, VIII.B) per v1.1.0; principle IX is the Kernel boundary added in v2.0.0.

| # | Principle | How this plan satisfies it | Status |
|---|-----------|---------------------------|--------|
| I | Position Sizing & Exposure Limits | Backtest invokes the **same** `risk/gates.py` checks (per-trade, per-symbol, global) as live (FR-B01, FR-B03). No new caps; no Kernel touch on K1. The fill simulator runs *after* the gate, so a rejected order in live is a rejected order in backtest with the same reason. | ✅ pass |
| II | Deny-by-Default (Whitelist) | Backtest runs the **same** `config/whitelist.py` enforcement. A symbol off the whitelist is rejected before any historical bar is consulted. No K2 touch. | ✅ pass |
| III | Claude at Defined Judgment Points Only | Backtest engine invokes zero LLMs. No `anthropic` client constructed in the `auto_invest.backtest` package. K3 untouched. | ✅ pass |
| IV | Append-Only Audit Log + Daily Reconciliation | New `BACKTEST_STARTED`, `BACKTEST_COMPLETED`, `BACKTEST_FAILED` rows go through the existing `persistence/audit.append` path, INSERT-only. The new migration `0003_backtest_events.sql` is added to `kernel.toml` K4 in the same change set as 008's first landing (Q3 clarification, constitution IX.C). Daily reconciliation is unaffected — backtest runs do not write to `orders` / `fills` tables. | ✅ pass *(one-time K-meta event acknowledged below)* |
| V | Secret Isolation | The yfinance adapter requires no credentials. The KIS historical adapter reuses the existing `broker/auth.py` token flow and existing `logging_config.py` redaction filter; no new secret category is introduced. The engine reads tokens through the existing loader (K5) but never logs them. | ✅ pass |
| VI | Backtest → Canary → Full Live | This feature is the literal "Backtest" arrow that constitution VI requires. The engine emits an advisory `promote_eligible` verdict (FR-B21) the operator (and, post-007, the canary harness) consumes. | ✅ pass |
| VII | External API Robustness | OHLCV ingest is the only external-API surface. The yfinance adapter wraps every call in `tenacity` retry + a per-host rate limiter + a circuit breaker (mirroring `broker/client.py`); the KIS adapter reuses `ResilientClient` directly. Replay itself touches no network. | ✅ pass |
| VIII.A | No live deploys during market hours | Engine code, like all repo code, is deployed off-hours. *Running* a backtest does not deploy the live worker; backtest invocation is safe at any hour. K6 (`worker/schedule.py`) is read-only. | ✅ pass |
| VIII.B | Deploy automation requirements | Engine deploys ride on the spec 006 deploy automation once 006's runner ships. Until then, engine code lands via human merge like every other change. The market-hours guard, audit events, health-check gate, and rollback obligation all apply unchanged. | ✅ pass |
| IX | Self-Modification Boundary | **Engine is NOT a Kernel change** in steady state — FR-B02 forbids modifying any file under any group in `kernel.toml`. The engine adds two new optional kwargs to `Worker.__init__` (`quote_provider`, `clock`) — `worker/loop.py` is non-Kernel, so this is in-bounds. The **first landing** of spec 008 *is* a Kernel touch because it adds `0003_backtest_events.sql` to K4 — this is the documented one-time K-meta human-merge event (Q3 clarification, constitution IX.C "adding a file to the Kernel is always a forward-compatible safety improvement"). | ✅ pass *(with the documented one-time K-meta event)* |

**Constitution check status**: pass. The single Kernel-adjacent action (adding `0003_backtest_events.sql` to `kernel.toml` K4) is explicit, documented, expected, and constitutional under IX.C.

**No constitution violations beyond the documented one-time K-meta landing. Complexity Tracking section below is intentionally empty.**

## Project Structure

### Documentation (this feature)

```text
specs/008-backtest-engine/
├── plan.md                     # This file (/speckit-plan output)
├── spec.md                     # Feature spec (clarified through /speckit-clarify)
├── research.md                 # Phase 0 output
├── data-model.md               # Phase 1 output
├── quickstart.md               # Phase 1 output
├── contracts/
│   ├── cli.md                  # `auto-invest backtest` subcommand surface
│   ├── ohlcv-adapter.md        # Vendor-agnostic adapter Protocol
│   ├── named-dataset.md        # `synthetic_shock_v1` manifest schema
│   ├── run-artifact.md         # `data/backtests/<run_id>/` on-disk schema
│   └── audit-events.md         # `BACKTEST_*` audit-event payload schemas
├── checklists/
│   └── requirements.md         # Spec quality checklist (already complete)
└── tasks.md                    # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Additions only. Existing files are read-only except `worker/loop.py` (non-Kernel; receives two new optional kwargs).

```text
src/auto_invest/
├── backtest/                          # NEW subpackage (non-Kernel)
│   ├── __init__.py                    # public API surface (run_backtest)
│   ├── engine.py                      # main loop: drives Worker.tick over bars
│   ├── clock.py                       # SyntheticClock — deterministic now()
│   ├── ohlcv/
│   │   ├── __init__.py
│   │   ├── adapter.py                 # Protocol — fetch_bars(symbol, range)
│   │   ├── canonical.py               # canonical OHLCV row + content_hash
│   │   ├── cache.py                   # local Parquet/CSV cache + invalidation
│   │   ├── yfinance_adapter.py        # FR-B06 vendor #1
│   │   └── kis_historical_adapter.py  # FR-B06 vendor #2 (uses ResilientClient)
│   ├── fills.py                       # FR-B07 hybrid fill model
│   ├── portfolio.py                   # cash + per-symbol exposure ledger
│   ├── report.py                      # FR-B11 returns/drawdown/Sharpe + per-rule
│   ├── verdict.py                     # FR-B21 promote_eligible
│   ├── manifest.py                    # FR-B05 / FR-B19 manifest IO + hashing
│   ├── named_dataset.py               # FR-B18 synthetic_shock_v1 freeze
│   ├── audit_events.py                # BACKTEST_* payload dataclasses
│   └── cli.py                         # `auto-invest backtest` subcommand
│
├── persistence/migrations/
│   └── 0003_backtest_events.sql       # NEW — extends audit_log payload schema
│
└── worker/loop.py                     # MODIFIED — two new optional kwargs
                                       #   quote_provider, clock
                                       # default behaviour unchanged

tests/
└── backtest/                          # NEW
    ├── __init__.py
    ├── test_engine_determinism.py     # SC-B03: 100 reruns identical
    ├── test_engine_pipeline_reuse.py  # SC-B02: gate-coverage diff vs live
    ├── test_fills_model.py            # FR-B07 hybrid branches
    ├── test_ohlcv_adapter.py          # adapter Protocol contract
    ├── test_yfinance_adapter.py       # respx-mocked
    ├── test_kis_historical_adapter.py # respx-mocked
    ├── test_named_dataset.py          # FR-B18 freeze + hash drift
    ├── test_report_math.py            # closed-form sine-wave fixture
    ├── test_verdict.py                # FR-B21 thresholds
    ├── test_audit_events.py           # FR-B14..B17 lifecycle
    ├── test_kernel_safety.py          # FR-B02 — diff intersect with kernel.toml
    └── fixtures/
        ├── ohlcv_sine_wave.csv
        └── synthetic_shock_v1/        # frozen golden output for goldens

.specify/memory/
└── kernel.toml                        # MODIFIED ONCE — adds
                                       # src/auto_invest/persistence/migrations/0003_backtest_events.sql
                                       # to [K4_append_only_audit].files
```

**Structure Decision**: extend the existing single-package layout with one new subpackage `auto_invest.backtest`. Reuses the existing `auto_invest.persistence.audit` writer, `auto_invest.risk.gates` checks, `auto_invest.config.whitelist` lookup, `auto_invest.execution.order_router` (with the broker substituted), and `auto_invest.worker.loop` (with two new kwargs). No new top-level package; no new database file; no new audit-log table — just a new event-type family inside the existing one. Rationale: spec 007 SC-C04 (reproducibility) is materially easier when only one process can hold the SQLite write lock and only one writer schema exists.

### Two Worker.tick injection seams (the heart of the engine)

The replay engine calls the **unmodified** rule evaluator and order router by:

1. **Clock injection** — passing a `SyntheticClock` instance to `Worker.__init__(clock=...)`; `Worker.tick(now=...)` already accepts an explicit `now`, but the deeper code (`worker/schedule.is_session_open`, K6) is queried via the same `now` argument, never via `datetime.now(UTC)`. The engine drives `now` forward bar-by-bar.

2. **Quote-provider injection** — passing a callable `(symbol: str, now: datetime) -> Quote` to `Worker.__init__(quote_provider=...)`. The default value `None` preserves live behaviour (calls `broker.overseas.get_quote`); when set, `_evaluate_and_route` calls `quote_provider(rule.symbol, now)` instead. The provider returns a `Quote` synthesised from the historical OHLCV bar at or before `now` for `symbol`.

Both kwargs are optional and default-`None`. Live `auto_invest.__main__` constructs `Worker` without them; the live code path is byte-identical to today after the change set lands.

The order router's broker-side dependency is similarly substituted at construction time with a `BacktestBroker` that records `SimulatedFill` rows instead of calling KIS. This is in `execution/`, not in K1, so the substitution is a non-Kernel concern.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | The one-time `kernel.toml` K4 addition is not a violation; it is the explicit documented mechanism in constitution IX.C. | — |
