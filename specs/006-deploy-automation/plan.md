# Implementation Plan: Deploy Automation

**Branch**: `claude/optimize-token-efficiency-uYiKk`
**Date**: 2026-05-06
**Spec**: [spec.md](./spec.md)
**Constitution**: v1.1.0 (principle VIII.B added in same change set)

## Summary

Add `auto-invest deploy` — a single CLI subcommand that runs the
deploy flow with constitutional guards: market-hours check, dirty-tree
check, deploy lock, audit-logged phases, post-restart health check,
and automatic rollback on failure. Ship systemd unit + timer
templates so a Linux host operator can wire scheduled off-hours
auto-deploy in two commands. Reuses existing infrastructure: the
audit-log writer (constitution IV), `exchange_calendars` (already a
dep, used by the worker for session boundaries), the config loader
(refuses on missing secrets), and the typer-based CLI.

## Technical Context

**Language/Version**: Python 3.11.
**New runtime dependencies**: none. Reuses `httpx` (transitive),
`exchange_calendars`, `pydantic`, `tomllib`, `typer`, plus stdlib
`subprocess` for git and supervisor calls.
**Storage**: extends `audit_log` with four new event-type literals
(`DEPLOY_STARTED`, `DEPLOY_COMPLETED`, `DEPLOY_FAILED`,
`DEPLOY_ROLLED_BACK`) and matching pydantic payload classes. **No new
tables or migrations.** This keeps the deploy script's surface area
small enough to review line-by-line.
**Testing**: unit tests for the market-hours guard, lock acquisition,
phase-state machine, and audit emission; integration test with a
fake git worktree + a fake worker subprocess (no real `systemctl`
calls) verifying the full success and rollback flows.
**Project Type**: extends the existing `auto_invest` package with an
internal `deploy/` subpackage and one new CLI subcommand.
**Performance Goals**: a no-op deploy completes < 2 s; a real deploy
of this size of codebase completes < 60 s including health check.
**Constraints**:
- Constitution VIII.A is non-negotiable: market-hours guard is the
  first phase after acquiring the lock.
- Constitution VIII.B clauses 1–6 are all mandatory; failing any
  clause must surface as a `DEPLOY_FAILED` audit row.
- The deploy script MUST work even if the SessionStart hook (003) is
  not configured.
**Scale/Scope (v1 of 006)**: single host, single operator, single
worker. Designed to extend to a small fleet by replacing the
worker-supervisor calls with a remote-exec backend; not in scope here.

## Constitution Check (v1.1.0)

| # | Principle | How this plan satisfies it | Status |
|---|-----------|---------------------------|--------|
| I | Position Sizing & Exposure Limits | Deploy never places orders; vacuously satisfied. | ✅ pass |
| II | Deny-by-Default (Whitelist) | Deploy refuses on missing required secrets, dirty tree, or open market session — explicit allowlist of conditions. | ✅ pass |
| III | Claude at Defined Judgment Points Only | Deploy makes zero LLM calls. | ✅ pass |
| IV | Append-Only Audit Log + Daily Reconciliation | All deploy events flow into the existing `audit_log` table; no parallel deploy log. | ✅ pass |
| V | Secret Isolation | Deploy script never logs or transmits secrets; existing redaction filter is sufficient. | ✅ pass |
| VI | Backtest → Canary → Full Live | Deploy is infrastructure, not a strategy promotion; vacuously satisfied. | ✅ pass |
| VII | External API Robustness | Deploy uses git/subprocess; failures surface as `DEPLOY_FAILED` and trigger rollback. The worker's own resilience handles its external APIs after restart. | ✅ pass |
| VIII.A | No Live Deploys During Market Hours | Market-hours guard refuses to proceed; verified by integration test. | ✅ pass |
| VIII.B (new) | Deploy Automation Requirements | All six clauses implemented: market-hours guard (FR-D02), audit events (FR-D03/04), health-check gate (FR-D07), rollback obligation (FR-D08), operator-triggered (the script never re-arms itself), secrets isolation (FR-D10). | ✅ pass |

**No violations identified.**

## Project Structure

```text
specs/006-deploy-automation/
├── plan.md                       # this file
├── spec.md
├── tasks.md
└── contracts/
    └── deploy-cli.md             # `auto-invest deploy` flag surface

src/auto_invest/
├── deploy/
│   ├── __init__.py
│   ├── runner.py                 # phase state machine; emits audit rows
│   ├── guards.py                 # market_hours_guard, lock, dirty_tree, secrets_present
│   ├── steps.py                  # pull, sync, migrate, dry_run, stop, start, health_check, rollback
│   └── supervisor.py             # supervisor abstraction (systemd / nohup-pid / dry)
├── cli.py                        # add `deploy` subcommand
└── persistence/audit.py          # extend EventType + add Deploy*Payload classes

deploy/
├── auto-invest.service           # systemd unit (operator copies to /etc/systemd/system/)
├── auto-invest-deploy.service    # systemd one-shot for the deploy script
├── auto-invest-deploy.timer      # systemd timer firing every 30 min off-hours
└── README.md                     # operator copy-paste install steps

tests/
├── unit/
│   ├── test_deploy_guards.py
│   ├── test_deploy_runner.py
│   └── test_deploy_audit.py
└── integration/
    └── test_deploy_end_to_end.py
```

## Constitution Re-Check (post-design)

| # | Principle | Re-check | Status |
|---|-----------|----------|--------|
| IV | Append-only audit | Deploy payloads (started/completed/failed/rolled_back) are pydantic-frozen; `event_type` is the discriminator; existing append-only triggers cover them. | ✅ pass |
| V | Secrets | Deploy reads `.env` only via the existing `config.loader` path; never echoes values. | ✅ pass |
| VIII.A | No market-hours deploys | First phase after lock acquisition is the market-hours guard; failing it emits `DEPLOY_FAILED(phase=market_hours_guard)` and exits 2. | ✅ pass |
| VIII.B | Deploy automation requirements | All six clauses cited in the FR list; integration test in `tests/integration/test_deploy_end_to_end.py` exercises success + rollback paths. | ✅ pass |

**No new violations. Plan ready for `/speckit-tasks`.**
