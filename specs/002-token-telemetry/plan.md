# Implementation Plan: LLM Token Telemetry & Efficiency KPIs

**Branch**: `claude/optimize-token-efficiency-uYiKk` (working branch; spec dir: `specs/002-token-telemetry/`)
**Date**: 2026-05-06
**Spec**: [spec.md](./spec.md)

## Summary

Add an audit-grade telemetry layer for Anthropic API usage. Ship: (1) a `TokenMeter` async context manager that wraps every Anthropic call, (2) a new append-only `token_usage` SQLite table plus an `LLM_CALL` audit-log event type, (3) KPI computation (cache hit rate, tokens/decision, $/decision, latency) with Tier A/B/C classification, (4) a "Token Efficiency" section in the daily report, (5) a new `auto-invest efficiency` CLI command. v1 still makes zero LLM calls (FR-005); this feature stages the rails so 004 can plug in judgment points without a second round of plumbing. All work respects constitution principles III (judgment points only), IV (append-only), V (no prompt content persisted), VII (resilience hooks for the Anthropic client), and VIII (no live deploys during market hours; this is a new-feature commit, not a hotfix).

## Technical Context

**Language/Version**: Python 3.11 (unchanged)
**New runtime dependencies**: none. Reuses `anthropic>=0.97` (already declared), `pydantic` (validation), `tomllib` (price table parsing), stdlib `sqlite3` and `time.perf_counter_ns`.
**Storage**: One new append-only SQLite table `token_usage` plus one new `event_type` literal `LLM_CALL`. Migration `0002_token_usage.sql` adds the table, indexes, and append-only triggers.
**Testing**: `pytest` unit tests for the meter, KPI math, tier classifier, integrity check; integration tests use a fake Anthropic response object so no live API calls are made in CI.
**Project Type**: extends the existing `auto_invest` single-package layout — adds `auto_invest.telemetry` subpackage and one new CLI command.
**Performance Goals**:
- Meter overhead per call: < 1 ms wall-clock against an in-memory SQLite (verified by `tests/integration/test_performance.py`).
- KPI aggregation for a session with ≤ 1,000 LLM calls: < 100 ms (SC-T02).
**Constraints**:
- Append-only invariant on `token_usage` mirrors `audit_log` (constitution IV).
- No prompt or response content stored (FR-T11, constitution V).
- Works correctly when zero LLM calls happen — meter is purely lazy (constitution III).
**Scale/Scope (v2 forecast)**: ≤ 100 LLM calls/day under 004's first judgment-point set. Designed to scale to ~10,000/day without architectural change.

## Constitution Check

*GATE: Must pass before Phase 0. Re-check after Phase 1.*

| # | Principle | How this plan satisfies it | Status |
|---|-----------|---------------------------|--------|
| I | Position Sizing & Exposure Limits | Telemetry does not place orders; vacuously satisfied. | ✅ pass |
| II | Deny-by-Default (Whitelist) | The price table is allow-list shaped: unknown model name → `cost_usd=NULL` + `DATA_QUALITY_ISSUE`, never silently treated as $0. | ✅ pass |
| III | Claude at Defined Judgment Points Only | This feature adds zero judgment points (per spec assumption). The meter is dormant until 004 declares the first one. | ✅ pass |
| IV | Append-Only Audit Log + Daily Reconciliation | `token_usage` is append-only via SQLite triggers. Every metered call also emits one `LLM_CALL` row in the existing `audit_log`. The integrity check (FR-T12) catches partial writes via a startup scan. | ✅ pass |
| V | Secret Isolation | FR-T11 forbids storing prompt/response content. The meter accepts only token counts, model name, decision class, and error class — none of which can carry secrets. The Anthropic API key is loaded by the existing secret pipeline; the meter never sees it. | ✅ pass |
| VI | Backtest → Canary → Full Live | Telemetry is observation-only; it does not promote/demote strategies. Vacuously satisfied. | ✅ pass |
| VII | External API Robustness | The meter wraps an Anthropic call but does not own retry/breaker semantics; the wrapped call site (introduced in 004) is responsible for those, mirroring `broker/client.py`. The meter MUST tolerate exceptions raised inside the wrapped call (FR-T02 error_class field) so it never swallows or amplifies a failure. | ✅ pass |
| VIII | Change Discipline — No Live Deploys During Market Hours | This is a new-feature commit on a dedicated branch; no hot-deploy path exists for v1. Operator restarts the worker between sessions to pick up the migration. | ✅ pass |

**No constitution violations identified. Complexity Tracking section below is intentionally empty.**

## Project Structure

### Documentation

```text
specs/002-token-telemetry/
├── plan.md                     # This file
├── spec.md                     # Feature spec
├── research.md                 # R-T1..R-T4 decisions
├── data-model.md               # token_usage schema + KPI types
├── contracts/
│   ├── kpi-thresholds.md       # Tier A/B/C threshold table (operator-editable)
│   ├── price-table.md          # config/llm_prices.toml schema
│   └── efficiency-cli.md       # `auto-invest efficiency` command surface
├── checklists/
│   └── requirements.md         # Spec quality checklist (deferred)
└── tasks.md                    # Phase 2 output
```

### Source Code (additions to existing tree)

```text
src/auto_invest/
├── telemetry/
│   ├── __init__.py
│   ├── meter.py                # TokenMeter async context manager
│   ├── prices.py               # Price-table loader + cost_usd computation
│   ├── kpi.py                  # KPI aggregation over token_usage rows
│   ├── tier.py                 # Tier A/B/C classifier
│   ├── store.py                # token_usage append-only writer + integrity check
│   └── thresholds.py           # Threshold-table loader (config/llm_kpi_thresholds.toml)
├── persistence/
│   └── migrations/
│       └── 0002_token_usage.sql    # new table + triggers + indexes
├── persistence/audit.py        # add LLM_CALL event_type + LlmCallPayload
├── reports/daily.py            # add Token Efficiency section
└── cli.py                      # add `efficiency` subcommand

config/
├── llm_prices.toml             # default Claude price table (operator-editable)
└── llm_kpi_thresholds.toml     # default Tier A/B/C thresholds (operator-editable)

tests/
├── unit/
│   ├── test_telemetry_meter.py
│   ├── test_telemetry_prices.py
│   ├── test_telemetry_kpi.py
│   ├── test_telemetry_tier.py
│   └── test_telemetry_store.py
└── integration/
    └── test_efficiency_cli.py
```

**Structure Decision**: New code lands under `auto_invest.telemetry` so the existing module boundaries are unchanged. The only edits to existing files are: (a) `persistence/audit.py` gains one new event type + one new payload class, (b) `reports/daily.py` gains one new render section + counters, (c) `cli.py` gains one new command. All three changes are additive and preserve existing tests.

## Constitution Re-Check (Post-Design)

| # | Principle | Re-check after Phase 1 | Status |
|---|-----------|------------------------|--------|
| I | Position Sizing & Exposure Limits | No change; telemetry never reaches `risk/gates.py`. | ✅ pass |
| II | Deny-by-Default (Whitelist) | Price-table loader rejects unknown models with explicit audit + NULL cost; threshold loader rejects unknown KPI names. | ✅ pass |
| III | Claude at Defined Judgment Points Only | Meter is opt-in via `async with TokenMeter(...)` — there is no global hook that intercepts Anthropic calls invisibly. 004 will be the first call site. | ✅ pass |
| IV | Append-Only Audit Log + Daily Reconciliation | `data-model.md` declares the same INSERT-only invariant; SQLite triggers in migration 0002 enforce it; FR-T12 integrity check runs at startup. | ✅ pass |
| V | Secret Isolation | Meter signature accepts only counts + model + decision class. Static type-check rejects `prompt: str` parameters at the call site. | ✅ pass |
| VI | Backtest → Canary → Full Live | n/a (observation only). | ✅ pass |
| VII | External API Robustness | Meter is pass-through on exceptions: it never retries, never swallows, never reorders. The Anthropic call site (in 004) wraps the meter inside its own resilience policy (mirroring `broker/client.py`). | ✅ pass |
| VIII | Change Discipline | New migration uses `IF NOT EXISTS` on every DDL; no destructive change to existing tables. | ✅ pass |

**No new violations. Plan is ready for `/speckit-tasks`.**

## Complexity Tracking

*No violations. Section intentionally empty.*
