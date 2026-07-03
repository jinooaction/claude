# Implementation Plan: Autonomous Growth Objective Calibration

**Branch**: `Codex/091-autonomous-growth-objective-calibration` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/091-autonomous-growth-objective-calibration/spec.md`

## Summary

Add a deterministic objective calibration contract to the autonomous work execution report. The loop will continue to use the existing safe ranking and operator-approval gates, but each report will now explain the selected candidate through measurable component scores, exploration budget, stop conditions, and learning metrics. The feature also publishes a completed-candidate marker so released-work can close `candidate-autonomous-growth-objective-calibration` after this implementation is complete.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Existing `auto_invest.analytics.autonomous_work_execution` and `released_work` modules  
**Storage**: Repository Markdown/JSON artifacts and automation sidecar reports  
**Testing**: pytest, ruff, autonomous-work probe, released-work probe, handoff fact checker, strict agent harness  
**Target Platform**: Local and GitHub workflow execution for the dry-run worker  
**Project Type**: Python package with automation sidecar reports  
**Performance Goals**: Objective calibration is computed in-memory during one probe run and remains deterministic for identical inputs  
**Constraints**: Read-only evidence consumption; no broker API, orders, capital allocation, live strategy, whitelist/caps, secret, constitution, kernel, or paid-service change  
**Scale/Scope**: One report schema extension, focused tests, one completed-candidate contract, one handoff update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principle I-VII, VIII.A: PASS. No trading, broker, capital, allowlist, secret, audit deletion, or external paid-service behavior changes.
- Principle IX and X: PASS. Uses SDD, explicit risk grade, full validation, PR quality gate, and handoff refresh.
- Risk grade: 2, because the autonomous-work sidecar schema and next-session decision surface change.
- Safety perimeter: Unchanged. This does not modify `.specify/memory/constitution.md`, `.specify/memory/kernel.toml`, K1~K6, live sentinel, order router, whitelist/caps, secrets, or deployment permissions.
- Rollback path: Revert the report schema extension and spec 091 completion marker, then rerun autonomous-work and released-work probes.

## Project Structure

### Documentation (this feature)

```text
specs/091-autonomous-growth-objective-calibration/
├── checklists/requirements.md
├── contracts/autonomous-growth-objective-calibration.md
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

**Structure Decision**: Reuse the existing autonomous-work report as the single output surface. Add typed dataclasses and pure helper functions in `autonomous_work_execution.py`; no new workflow, service, or external dependency is needed.

## Complexity Tracking

No constitution violations.
