# Implementation Plan: Agent Ops Frontier Map

**Branch**: `Codex/106-agent-ops-frontier-map` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/106-agent-ops-frontier-map/spec.md`

## Summary

Add a deterministic operating-system frontier map to the autonomous-work execution report and use it to regenerate the next executable agent-ops candidate after `candidate-agent-ops-frontier-map` is released. The feature stays read-only, consumes existing evidence and repo-local operating controls, and preserves existing repair, operator approval, blocked, released, and suppressed priority rules.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `auto_invest.analytics.autonomous_work_execution` and `released_work` modules
**Storage**: Repository Markdown/JSON artifacts and automation sidecar reports
**Testing**: pytest, ruff, autonomous-work probe, released-work probe, handoff fact checker, strict agent harness
**Target Platform**: Local and GitHub workflow execution for the dry-run worker
**Project Type**: Python package with automation sidecar reports
**Performance Goals**: Same input sidecars produce deterministic map and candidate selection in one probe run
**Constraints**: Read-only evidence consumption; no broker API, orders, capital allocation, live strategy, whitelist/caps, secret, constitution, kernel, fresh external collection, or paid-service change
**Scale/Scope**: Existing autonomous-work sidecar evidence set plus repo-local handoff, harness, PR quality, and concurrency control references

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principles I, II, IV, VI: No orders, capital, whitelist/caps, audit schema, or rollout-stage change.
- Principle V: No secret read/write and no new external integration.
- Principle VII: No external API path is added; the report reads existing sidecars and repo-local files only.
- Principle VIII.A/B: Code change deploys through existing guarded pipeline; no market-hours deploy bypass.
- Principle IX: No constitution or kernel file touch; this is an operating report change only.
- Principle X: Candidate regeneration is evidence-driven by released-work, autonomous-work, handoff, harness, and PR quality controls. It does not move live money.

**Gate Result**: Pass. Risk grade 2 operating automation change.

## Project Structure

### Documentation (this feature)

```text
specs/106-agent-ops-frontier-map/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── agent-ops-frontier-map.md
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
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Reuse the existing autonomous-work execution report as the sole runtime surface. Do not add a new workflow or write-capable automation.

## Complexity Tracking

No constitution violations or new architectural complexity.

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/agent-ops-frontier-map.md](./contracts/agent-ops-frontier-map.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

Pass. The design remains read-only, consumes existing sidecars and repo-local operating controls only, adds no external collection, and records the candidate completion marker without touching the safety perimeter.
