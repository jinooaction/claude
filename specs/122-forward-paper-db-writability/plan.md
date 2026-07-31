# Implementation Plan: Forward Paper DB Writability

**Branch**: `codex/122-forward-paper-db-writability` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/122-forward-paper-db-writability/spec.md`

## Summary

Restore the forward paper evidence path by making the fixed observe helper repair writability for only the selected paper track DB files before paper prep. The repair keeps the existing safety model: no live orders, no live arming, no capital changes, no live DB chmod/chown, and no live halt flag mutation.

## Technical Context

**Language/Version**: Bash helper scripts, Python 3.11 tests
**Primary Dependencies**: Existing `uv`, `auto-invest` CLI, SQLite paper DBs, GitHub Actions SSH gateway
**Storage**: Server-side SQLite paper DBs under `data/forward_*.db`
**Testing**: `pytest`, `ruff`, shell syntax checks, sidecar verification
**Target Platform**: Linux production instance plus GitHub Actions runner
**Project Type**: Trading automation CLI and operations repository
**Performance Goals**: Repair must add negligible overhead before each paper track run
**Constraints**: Paper-only mutation; no broker order submission; no live DB, live halt flag, secrets, capital, whitelist/caps, or live strategy mutation
**Scale/Scope**: Seven forward paper tracks: trend, notrend, rmbeta, multiasset, global, globalfixed, wide

## Constitution Check

- **I Position Sizing & Exposure Limits**: Pass. No order path changes.
- **II Deny-by-Default Whitelist**: Pass. No tradeable universe or whitelist changes.
- **III Defined Judgment Points**: Pass. No LLM judgment point changes.
- **IV Append-Only Audit + Reconciliation**: Pass. Does not mutate audit logs or live reconciliation state.
- **V Secret Isolation**: Pass. Does not read or write secret values.
- **VI Staged Rollout**: Pass. Restores paper evidence production and does not promote or arm live.
- **VII External API Robustness**: Pass. Does not change KIS retry/rate behavior.
- **VIII Change Discipline**: Pass with grade 3 handling. Root observe helper behavior changes, so focused tests, full validation, PR quality gate, and post-deploy sidecar verification are required.
- **IX Self-Modification Boundary**: Pass. No constitution or kernel manifest change.
- **X Measurement-Driven Autonomous Growth**: Pass. The change restores measured evidence accumulation rather than bypassing evidence gates.

## Project Structure

### Documentation (this feature)

```text
specs/122-forward-paper-db-writability/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── forward-paper-storage.md
└── tasks.md
```

### Source Code

```text
deploy/
└── observe-on-instance.sh

tests/unit/
├── test_forward_workflow_halt_isolation.py
└── test_ssh_boundary_repair.py
```

**Structure Decision**: Keep the repair in the existing root-installed observe helper because `rebalance-paper-forward.yml` already enters through `observe paper-track-run`. Tests stay as text-boundary tests because the safety contract is the command surface and shell behavior.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Root observe helper change | The failure happens inside the forced-command server helper before paper DB writes | A workflow-only change cannot repair server file ownership/mode drift |
