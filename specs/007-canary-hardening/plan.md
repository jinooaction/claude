# Implementation Plan: Hardened Canary for Autonomous Production-Deploy

**Branch**: `claude/start-spec-007-6GntK` (working branch; spec dir: `specs/007-canary-hardening/`)
**Date**: 2026-05-14
**Spec**: [spec.md](./spec.md) (promoted stub → active 2026-05-14 under constitution v3.0.0)
**Input**: Feature specification from `specs/007-canary-hardening/spec.md`

## Summary

Build a replay-based hardened canary harness, packaged under `src/auto_invest/canary/`, that consumes spec 008's already-shipped backtest engine and produces a single all-or-nothing pass/fail signal across five acceptance metrics over a ≥30 / ≥45 trading-day window plus a synthetic-shock + property-fuzz adversarial battery. The harness is the production-deploy gate under constitution v3.0.0 IX.B-2 — merges land freely via the autonomous-workflow policy in CLAUDE.md; this harness gates the bits actually reaching the live KIS worker.

The harness ships ONE invocation surface (CLI module `python -m auto_invest.canary` with `run` / `shock` / `fuzz` subcommands), ONE on-disk artefact tree (`data/canary/<run_id>/`), and FOUR new append-only audit-event types (`CANARY_ENTERED`, `CANARY_PASSED`, `CANARY_FAILED`, `CANARY_KERNEL_TOUCH_DETECTED`). The event-type addition is an additive K4 touch (one-time, schema-extension only). Under v3.0.0 a K4 touch no longer blocks the merge; it emits a `CANARY_KERNEL_TOUCH_DETECTED` forensic row when later canary runs see it in a candidate diff.

Two critical safety properties are non-negotiable:

1. **Reproducibility (SC-C04, FR-C04, FR-C07)** — re-running the harness against the same `(candidate-rev, baseline-rev, seed, window-start-date)` tuple produces byte-identical artefacts (modulo `start_ts`). Spec 008's backtest engine already guarantees this on its half; spec 007 must preserve it across its own composition layer (synthetic-shock + property-fuzz + diff-decision merge).
2. **No live side effects** — the canary harness MUST NEVER touch the live KIS broker, MUST NEVER make a real Anthropic call, MUST NEVER deploy. It is read-only against the repo (git diff) and the historical OHLCV dataset (spec 008's `data/history/`). Its only persistent writes are the audit log (append) and `data/canary/<run_id>/` (idempotent within a run_id).

The harness is invoked by an operator-instructed session (or eventually spec 005's autonomous tuner). The decision to deploy is downstream — spec 006's deploy automation consults the most recent `CANARY_PASSED` audit row to determine whether a given `candidate-rev` is deploy-eligible.

## Technical Context

**Language/Version**: Python 3.11 (matches spec 001 / 002 / 003 / 008 toolchain).

**Primary Dependencies**:
- `pydantic` v2 — payload models for the 4 new audit events; `CanaryRun` / `CanaryMetrics` / `FuzzCounterexample` models.
- `hypothesis` (NEW dev/runtime dep, will be added to `pyproject.toml`) — property-based fuzz over `risk.gates` math. Runtime-classified (not test-only) because the canary CLI invokes Hypothesis programmatically as part of an acceptance pipeline, not just under pytest.
- `sqlite3` (stdlib) — append-only audit log shared with the live worker and the backtest engine.
- `tomllib` (stdlib) — `config/canary_bands.toml` loader (operator-amendable defaults).
- `subprocess` (stdlib) — invoke `git diff --name-only <baseline>..<candidate>` and `git rev-parse <ref>`. No third-party git lib in v1.
- **Reused without modification from spec 008**: `auto_invest.backtest.run.run_backtest`, `auto_invest.backtest.synthetic_shocks.resolve_synthetic_shocks`, `auto_invest.backtest.data_source.CSVDataSource`, `auto_invest.backtest.metrics`, `auto_invest.backtest.kernel_pre_flight`. The canary is the first non-CLI consumer of the backtest engine; this validates spec 008's library-shape API.
- **Reused without modification from spec 001**: `auto_invest.risk.gates` (the fuzz target — K1).

**Storage**:
- 4 new audit-event types in the existing single SQLite `audit_log` table. `correlation_id = canary_run_id`. No table schema change beyond extending the `event_type` Literal Union (additive K4 touch).
- Per-run artefacts → `data/canary/<run_id>/` directory tree, immutable after `CANARY_PASSED` / `CANARY_FAILED`.
- Acceptance bands → `config/canary_bands.toml` (operator-amendable; defaults in this PR per spec promotion criteria).
- Synthetic-shock date set → reuses `config/synthetic_shocks.toml` from spec 008. No duplication.

**Testing**: `pytest` (existing), `hypothesis` for property tests; new test modules:
- `tests/unit/test_canary_diff.py` — git diff baseline-resolution + kernel-intersect detection.
- `tests/unit/test_canary_metrics.py` — five-metric evaluation against canned `BacktestRun` pairs.
- `tests/unit/test_canary_fuzz.py` — the Hypothesis suite itself + an off-by-one injection that property fuzz MUST catch (SC-C02).
- `tests/unit/test_canary_report.py` — `canary-run.json` schema + byte-identical re-write determinism.
- `tests/unit/test_canary_audit_events.py` — payload models, K4 additive-touch contract.
- `tests/integration/test_canary_end_to_end.py` — run `canary run` end-to-end on a tiny fixture rev pair; verify all artefacts + pass-path emission of `CANARY_PASSED`.
- `tests/integration/test_canary_kernel_touch.py` — kernel-touching diff produces `CANARY_KERNEL_TOUCH_DETECTED` and STILL evaluates the 5 metrics (does NOT short-circuit).
- `tests/integration/test_canary_reproducibility.py` — SC-C04 byte-identical re-run.

**Target Platform**: Same as live worker — Linux long-running Python 3.11 process. Canary runs are short-lived CLI invocations on the operator's MacBook or a CI runner; no daemon.

**Project Type**: Adds one new module (`canary/`) under `src/auto_invest/`. One CLI subcommand. No new processes or services. No new SQLite tables.

**Performance Goals (SC-C02 / SC-C03 derivatives)**:
- A full canary run (30-day replay × 2 revs + 4 synthetic-shock days × 2 revs + 10k fuzz iterations) MUST complete in < 30 min on operator's local hardware.
- The fuzz pass alone (10k iterations) MUST complete in < 60 s — `risk.gates` is pure math; this is achievable single-threaded.
- A re-run against an unchanged dataset MUST be cache-hit-fast: spec 008 already pickles `data/history/<dataset_version>/<sym>.parquet`; the canary reuses those reads.

**Constraints**:
- **Reproducibility**: every operation that affects on-disk output MUST be deterministic. The Hypothesis seed is recorded in `property-fuzz/seeds.txt`; replay uses spec 008's WallClockLeakError guard.
- **No live broker / no live LLM**: inherited from spec 008's backtest engine. The canary cannot introduce a regression here; it only composes spec 008 outputs.
- **Kernel forensic callout**: per FR-C08, the harness LOUDLY annotates a kernel-touching candidate via `CANARY_KERNEL_TOUCH_DETECTED` but does NOT short-circuit (constitution v3.0.0 IX.B reframed Kernel from barrier → forensic list).
- **Append-only audit**: 4 new event types, no UPDATE/DELETE. One-time additive K4 touch on `src/auto_invest/persistence/audit.py` (analogous to spec 008's additive touch).
- **Memory**: a 30-day replay × 20 symbols is trivial (~15k bars). No streaming required.
- **Determinism of git baseline resolution**: if no prior `CANARY_PASSED` exists, the baseline is `origin/main`. The harness records the resolved SHAs in `canary-run.json` so a re-run against the same SHAs is exactly reproducible.

**Scale/Scope (v1)**:
- One canary run at a time per machine; the harness refuses to start if it detects an in-flight `canary-run.json` without a terminal status (FR-implicit safety, see Edge Cases in spec).
- L2 = 30 trading days, L3 = 45 trading days. L1 (per spec 005's tiered authority) does not need canary; the harness rejects `--tier L1` with an explanatory error.
- Single asset class: US-listed equities (inherited from spec 001).
- One judgment-class baseline at a time per fuzz pass (the property is global to `risk.gates`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan satisfies it | Status |
|---|-----------|---------------------------|--------|
| I | Position Sizing & Exposure Limits | The canary IS the production-deploy guardian of principle I — its property-fuzz pass (FR-C04) directly asserts `per_trade ≤ per_symbol ≤ global` on `risk.gates`. A change that removes a cap is caught by fuzz with probability ≥ 0.99 within 10k iterations (SC-C02). | ✅ pass |
| II | Deny-by-Default (Whitelist) | Replay window passes ORDER_INTENTs through the K2 whitelist gate unchanged. A change that auto-expands the whitelist produces `risk_gate_violation_count > 0` in synthetic-shock replay (every shock date has out-of-whitelist symbols that pre-K2-expansion would have been denied), so FR-C01 #2 trips. | ✅ pass |
| III | LLM at Defined Judgment Points Only | Inherited from spec 008: BACKTEST_MODE=1 forces `LLM_CALL_STUBBED`, and `BACKTEST_JUDGMENT_LEAK` errors a real Anthropic call. The canary harness adds no judgment points; it composes spec 008's replay output. | ✅ pass |
| IV | Append-Only Audit Log | 4 new event types appended to `EventType` Literal; corresponding payload models added. No UPDATE/DELETE. K4 additive touch acknowledged below. Under v3.0.0 IX.A this is a forensic-attention row, not a merge barrier. | ✅ pass (additive K4 touch) |
| V | Secret Isolation | Canary reads NO secrets. No `.env` load. No real broker, no real LLM. Inherited from spec 008. | ✅ pass |
| VI | Backtest → Canary → Full Live | This IS the Canary stage. Spec 008 was the Backtest stage; the live worker is the Full-Live stage. v1 of spec 007 is replay-canary only (no live 5% capital share); a future v2 may layer live-capital canary on top, but the replay canary alone is sufficient as the production-deploy gate under v3.0.0. | ✅ pass |
| VII | External API Robustness | No external APIs called during a canary run. Vacuously satisfied. | ✅ pass |
| VIII.A | No live deploys during market hours | The canary harness DOES NOT deploy — it only emits `CANARY_PASSED` / `CANARY_FAILED`. Spec 006's deploy automation (when it ships) is the deployer and owns the market-hours guard. | ✅ pass |
| VIII.B | Deploy automation requirements | Out of scope — spec 006 owns deploy automation. The canary's job is to produce the gate signal spec 006 consumes. | ✅ pass (delegation) |
| IX.A | Kernel forensic-attention list | The canary harness implements FR-C08 — it scans the candidate diff against `kernel.toml` and emits `CANARY_KERNEL_TOUCH_DETECTED` with kernel-group labels. Under v3.0.0 this is forensic, not blocking. | ✅ pass |
| IX.B-2 | Production-deploy gate | The canary IS the gate. This plan implements it. | ✅ pass (the deliverable itself) |
| IX.C | Kernel manifest discipline | The harness reads `kernel.toml` via `auto_invest.deploy.load_kernel_manifest` (spec 006's helper, already shipped). No hard-coded Kernel paths. | ✅ pass |
| IX.D | Operator Autonomy Supremacy | Defaults ship in this PR; operator amends via future PR. No mid-pipeline permission checks. | ✅ pass |

**One-time additive K4 touch acknowledged** (analogous to spec 008's): four event-type literals appended to `src/auto_invest/persistence/audit.py` plus four payload models. Under v3.0.0 IX.A this is a `CANARY_KERNEL_TOUCH_DETECTED` forensic emission when the K4 commit later flows through a canary run; it does NOT block this PR's merge. The commit message for the audit.py touch MUST surface the K4 hash so `git log --grep="K4"` finds it.

**No constitution violations. Complexity Tracking section is intentionally empty.**

## Project Structure

### Documentation (this feature)

```text
specs/007-canary-hardening/
├── plan.md                          # This file (/speckit-plan output)
├── spec.md                          # Promoted stub → active 2026-05-14
├── research.md                      # Phase 0 output — R-C1..R-C10 decisions
├── data-model.md                    # Phase 1 output — entities + audit-event schemas + on-disk layout
├── quickstart.md                    # Phase 1 output — operator onboarding for canary
├── contracts/
│   ├── canary-cli.md                # CLI commands + flags + exit codes
│   ├── canary-run-json.md           # canary-run.json schema
│   ├── canary-bands-toml.md         # config/canary_bands.toml schema
│   └── property-fuzz-protocol.md    # Hypothesis target shape + post-condition
└── tasks.md                         # Phase 2 output (/speckit-tasks command — NOT created here)
```

### Source Code (repository root)

```text
src/auto_invest/
├── canary/                                # NEW PACKAGE — all under here is NON-Kernel
│   ├── __init__.py                        # public surface (CanaryRun, run_canary, ...)
│   ├── __main__.py                        # `python -m auto_invest.canary` entrypoint
│   ├── cli.py                             # subcommands: run / shock / fuzz
│   ├── diff.py                            # baseline resolution + git diff + kernel-touch detection
│   ├── metrics.py                         # 5-metric evaluator (drawdown / gate-violations / audit-integrity / latency / llm-cost)
│   ├── replay_window.py                   # drives ≥30/≥45-day window replay (calls run_backtest twice)
│   ├── shock.py                           # drives synthetic-shock battery (calls run_backtest with synthetic_shock=True)
│   ├── fuzz.py                            # Hypothesis property fuzz on risk.gates
│   ├── report.py                          # writes canary-run.json, metrics.csv, per-section artefacts
│   ├── data_model.py                      # CanaryRun, CanaryMetrics, CanaryDecision, FuzzCounterexample
│   └── run.py                             # top-level orchestration: kernel-touch detection → audit ENTERED → replay → shock → fuzz → metrics → audit PASSED/FAILED → report
├── persistence/
│   └── audit.py                           # K4 — additive touch: append CANARY_ENTERED, CANARY_PASSED, CANARY_FAILED, CANARY_KERNEL_TOUCH_DETECTED literals + 4 payload models
└── ...                                    # everything else UNCHANGED

config/
└── canary_bands.toml                      # NEW — operator-amendable acceptance bands (defaults from spec FR-C01)

tests/
├── unit/
│   ├── test_canary_diff.py                # baseline resolution + kernel-intersect detection
│   ├── test_canary_metrics.py             # 5-metric eval on canned BacktestRun pairs
│   ├── test_canary_fuzz.py                # Hypothesis suite + SC-C02 off-by-one injection
│   ├── test_canary_report.py              # canary-run.json schema + byte-identical re-write determinism
│   ├── test_canary_audit_events.py        # 4 new payload models + K4 additive contract
│   └── test_canary_bands_toml.py          # config loader + invalid-band rejection
└── integration/
    ├── test_canary_end_to_end.py          # full `canary run` over a fixture rev pair; verifies all artefacts
    ├── test_canary_kernel_touch.py        # kernel-touching diff → CANARY_KERNEL_TOUCH_DETECTED + still evaluates 5 metrics
    └── test_canary_reproducibility.py     # SC-C04 byte-identical re-run

data/                                      # gitignored
└── canary/                                # NEW — per-run artefacts
    └── <canary_run_id>/
        ├── canary-run.json
        ├── metrics.csv
        ├── shock-replay/<YYYY-MM-DD>/
        │   ├── audit_log.json
        │   └── backtest-run.json          # symlink or copy of spec 008's per-shock artefact
        ├── property-fuzz/
        │   ├── seeds.txt
        │   └── counterexamples.json
        └── replay-window/
            ├── candidate/backtest-run.json
            └── baseline/backtest-run.json
```

**Structure Decision**: single-package; `src/auto_invest/canary/` mirrors `src/auto_invest/backtest/` (already shipped). The canary package is fully outside the Kernel except for the one-time additive touch on `persistence/audit.py`. No new top-level package; no new CLI binary — the `python -m auto_invest.canary` invocation matches spec 008's `python -m auto_invest.backtest`.

## Complexity Tracking

*(No constitution violations; section intentionally empty per template.)*
