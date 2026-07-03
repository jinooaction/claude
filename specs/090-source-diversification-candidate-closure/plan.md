# Implementation Plan: Source Diversification Candidate Closure

**Branch**: `Codex/090-source-diversification-bottleneck` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/090-source-diversification-candidate-closure/spec.md`

## Summary

Close the source-diversification output candidate emitted by spec 089 so the autonomous work loop does not reselect already implemented work. The implementation uses the existing released-work completion marker contract, adds a focused regression around autonomous work selection, and validates latest sidecar replay advances to the next macro candidate.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `auto_invest.analytics` modules and Speckit documents
**Storage**: Repository Markdown/YAML/JSON artifacts only
**Testing**: pytest, ruff, released-work probe, autonomous-work probe, handoff fact checker, strict agent harness
**Target Platform**: Local and GitHub workflow execution for the dry-run worker
**Project Type**: Python package with automation sidecar reports
**Performance Goals**: Same input sidecars produce deterministic selected work in one probe run
**Constraints**: Read-only evidence consumption; no broker API, orders, capital allocation, live strategy, whitelist/caps, secret, constitution, kernel, or paid-service change
**Scale/Scope**: One completion marker, one regression path, one handoff update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principle I-VII, VIII.A: PASS. No trading, broker, capital, allowlist, secret, audit deletion, or external paid-service behavior changes.
- Principle IX and X: PASS. Uses SDD, explicit risk grade, full validation, PR quality gate, and handoff refresh.
- Risk grade: 2, because released-work and handoff state change next-session autonomous behavior.
- Rollback path: Remove the spec 090 completion marker and regression test commit, then rerun released-work and autonomous-work replay.

## Project Structure

### Documentation (this feature)

```text
specs/090-source-diversification-candidate-closure/
├── checklists/requirements.md
├── contracts/source-diversification-candidate-closure.md
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
scripts/released_work_probe.py
scripts/autonomous_work_execution_probe.py
tests/unit/test_autonomous_work_execution.py
```

**Structure Decision**: Reuse existing released-work and autonomous-work execution modules. The behavior is mainly contract-driven; code changes are limited to regression coverage unless the test exposes a gap.

## Complexity Tracking

No constitution violations.
