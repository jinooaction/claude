# Implementation Plan: Frontier Candidate Discovery

**Branch**: `Codex/092-frontier-candidate-discovery` | **Date**: 2026-07-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/092-frontier-candidate-discovery/spec.md`

## Summary

Add a deterministic frontier discovery candidate to the autonomous work execution loop. When all regular candidates and existing macro-growth candidates are closed, the report should emit an execution-ready operating task instead of selecting a released candidate as if it were new work.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `auto_invest.analytics.autonomous_work_execution` and `released_work` modules
**Storage**: Repository Markdown/JSON artifacts and automation sidecar reports
**Testing**: pytest, ruff, autonomous-work probe, released-work probe, handoff fact checker, strict agent harness
**Target Platform**: Local and GitHub workflow execution for the dry-run worker
**Project Type**: Python package with automation sidecar reports
**Performance Goals**: Same input sidecars produce deterministic frontier candidate selection in one probe run
**Constraints**: Read-only evidence consumption; no broker API, orders, capital allocation, live strategy, whitelist/caps, secret, constitution, kernel, or paid-service change
**Scale/Scope**: One autonomous-work selection rule, focused tests, one completed-candidate contract, one handoff update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principle I-VII, VIII.A: PASS. No trading, broker, capital, allowlist, secret, audit deletion, or external paid-service behavior changes.
- Principle IX and X: PASS. Uses SDD, explicit risk grade, full validation, PR quality gate, and handoff refresh.
- Risk grade: 2, because the autonomous-work sidecar's next-work selection behavior and next-session decision surface change.
- Safety perimeter: Unchanged. This does not modify `.specify/memory/constitution.md`, `.specify/memory/kernel.toml`, K1~K6, live sentinel, order router, whitelist/caps, secrets, or deployment permissions.
- Rollback path: Revert the frontier discovery rule and spec 092 completion marker, then rerun autonomous-work and released-work probes.

## Project Structure

### Documentation (this feature)

```text
specs/092-frontier-candidate-discovery/
├── checklists/requirements.md
├── contracts/frontier-candidate-discovery.md
├── data-model.md
├── plan.md
├── quickstart.md
├── research.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/autonomous_work_execution.py
scripts/autonomous_work_execution_probe.py
scripts/released_work_probe.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_autonomous_work_execution_probe.py
```

**Structure Decision**: Reuse the existing autonomous-work module. Add the frontier candidate as a pure generated `WorkPacket`; no workflow, service, or dependency is needed.

## Complexity Tracking

No constitution violations.
