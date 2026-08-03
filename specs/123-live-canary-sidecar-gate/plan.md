# Implementation Plan: Live Canary Sidecar Gate

**Branch**: `codex/live-canary-sidecar-before-production-gate` | **Date**: 2026-08-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/123-live-canary-sidecar-gate/spec.md`

## Summary

Split the live canary workflow into a preview/status job and a real-order job. The preview/status job can refresh the latest sidecar while unarmed without waiting for production approval, and it enters the server only through fixed observe gateway verbs. The real-order job remains the only path with `--mode live --confirm-live`, guarded by `armed=true`, capital validation, non-push events, and production approval.

## Technical Context

**Language/Version**: GitHub Actions YAML, Bash, Python 3.11 tests
**Primary Dependencies**: Existing `uv`, `auto-invest` CLI, forced-command SSH gateway, GitHub Actions environments, sidecar branch publication
**Storage**: Git sidecar branch `automation/rebalance-live-canary-last-run`; existing server SQLite data is read by current live-canary commands
**Testing**: `pytest`, `ruff`, static workflow boundary tests, YAML parse check, post-merge sidecar dispatch
**Target Platform**: GitHub Actions runner plus existing production instance over the established SSH boundary
**Project Type**: Trading automation operations workflow
**Performance Goals**: Keep the live canary workflow within the existing 15 minute timeout
**Constraints**: No real orders outside production approval; preview/status server entry must use fixed observe commands; no capital ladder change; no whitelist/caps change; no strategy reassignment; no secrets or audit-log change
**Scale/Scope**: One guarded workflow, one sidecar branch, and local tests for workflow structure

## Constitution Check

- **I Position Sizing & Exposure Limits**: Pass. The change does not alter position caps or order sizing code.
- **II Deny-by-Default Whitelist**: Pass. No tradeable universe, account, session, or order-type whitelist changes.
- **III Defined Judgment Points**: Pass. No LLM calls or judgment points are added.
- **IV Append-Only Audit + Reconciliation**: Pass. No audit log or reconciliation mutation is changed.
- **V Secret Isolation**: Pass. Secrets remain GitHub Actions secrets and are not logged or persisted.
- **VI Staged Rollout**: Pass. Real-order execution remains a canary-stage path and remains gated; this feature does not promote to full live or arm live.
- **VII External API Robustness**: Pass. No KIS retry/rate/circuit behavior changes.
- **VIII.A No Live Deploys During Market Hours**: Pass. This is a workflow merge and sidecar dispatch, not a production worker deploy. Real order scheduling semantics are not widened.
- **VIII.B Deploy Automation Requirements**: Pass with risk grade 3 handling. The production approval boundary moves only for preview/status sidecar publication; real-order execution stays production-approved.
- **IX Self-Modification Boundary**: Pass. `.github/workflows/rebalance-live-canary.yml` is not in the Kernel manifest, and no constitution or kernel manifest file changes.
- **X Measurement-Driven Autonomous Growth**: Pass. The change restores truthful liveness evidence instead of bypassing evidence gates.

Risk grade: **3** because the workflow is adjacent to the live-money gate and production approval placement changes. The change is intentionally a safety-preserving split: real orders stay behind the approval gate, while preview/status can refresh evidence.

## Project Structure

### Documentation (this feature)

```text
specs/123-live-canary-sidecar-gate/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── live-canary-sidecar-gate.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
.github/workflows/
└── rebalance-live-canary.yml

deploy/
├── observe-on-instance.sh
└── repair-ssh-boundary.sh

tests/unit/
├── test_ssh_boundary_repair.py
├── test_live_canary_workflow.py
└── test_workflow_nav_capital_basis.py
```

**Structure Decision**: Keep the workflow in the existing live-canary file because it already owns the sentinel, dry-run preview, live command, and sidecar branch. Add narrow observe-helper verbs instead of raw remote shell for preview/status because the production SSH gateway is intentionally fixed-command. Tests stay as static workflow/gateway boundary tests because the safety contract is which command surface owns preview/status and which job owns the real-order command and production approval gate.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Split one live-money workflow into two jobs | Sidecar freshness must not wait for production approval when no real orders can run | Keeping one job requires production approval for unarmed status refreshes, which leaves liveness stale |
| Keep production sidecar overwrite after real orders | A production-approved real run must replace preview-only evidence with actual execution evidence | Leaving only preview evidence after a real run could hide whether orders executed |
| Add fixed observe verbs for live-canary preview/status | The server gateway refuses raw SSH commands after hardening | Reopening arbitrary remote shell would undo the SSH boundary repair |
