# Implementation Plan: Macro Candidate Map Regenerator

**Branch**: `Codex/093-macro-candidate-map-regenerator` | **Date**: 2026-07-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/093-macro-candidate-map-regenerator/spec.md`

## Summary

Add a deterministic macro candidate map to the autonomous-work execution report and use it to regenerate the next executable frontier candidate after the known macro queue, frontier discovery candidate, and map-regenerator candidate have all been released. The feature stays read-only and preserves existing safety and operator-approval gates.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `auto_invest.analytics.autonomous_work_execution` and `released_work` modules
**Storage**: Repository Markdown/JSON artifacts and automation sidecar reports
**Testing**: pytest, ruff, autonomous-work probe, released-work probe, handoff fact checker, strict agent harness
**Target Platform**: Local and GitHub workflow execution for the dry-run worker
**Project Type**: Python package with automation sidecar reports
**Performance Goals**: Same input sidecars produce deterministic map and candidate selection in one probe run
**Constraints**: Read-only evidence consumption; no broker API, orders, capital allocation, live strategy, whitelist/caps, secret, constitution, kernel, or paid-service change
**Scale/Scope**: Existing autonomous-work sidecar evidence set; at least four high-level frontier domains

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principles I, II, IV, VI: No orders, capital, whitelist/caps, audit schema, or rollout-stage change.
- Principle V: No secret read/write and no new external integration.
- Principle VIII.A/B: Code change deploys through existing guarded pipeline; no market-hours deploy bypass.
- Principle IX: No constitution or kernel file touch; this is an operating report change only.
- Principle X: Candidate regeneration is evidence-driven by released-work, learning, pipeline, and capital-path sidecars. It does not move live money.

Result: PASS. Risk grade 2 operating automation change.

## Project Structure

### Documentation (this feature)

```text
specs/093-macro-candidate-map-regenerator/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── macro-candidate-map-regenerator.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/autonomous_work_execution.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_autonomous_work_execution_probe.py
scripts/autonomous_work_execution_probe.py
```

**Structure Decision**: Reuse the existing autonomous-work execution report as the sole runtime surface. Do not add a new workflow or write-capable automation.

## Complexity Tracking

No constitution violations or new architectural complexity.
