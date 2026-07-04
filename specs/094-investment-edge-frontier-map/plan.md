# Implementation Plan: Investment Edge Frontier Map

**Branch**: `Codex/094-investment-edge-frontier-map` | **Date**: 2026-07-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/094-investment-edge-frontier-map/spec.md`

## Summary

Extend the read-only autonomous-work execution report so the selected investment-edge frontier candidate becomes a nested investment-edge frontier map. Before this spec is released, the loop continues to select `candidate-investment-edge-frontier-map`; after released-work records that candidate, it advances to the first no-live experiment candidate, `candidate-forward-regime-edge-experiment`, using forward paper, money-path, released-work, learning-ledger, and liveness evidence refs.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `auto_invest.analytics.autonomous_work_execution`, released-work scanner, pytest, ruff
**Storage**: No new durable storage; emitted JSON/Markdown sidecar fields only
**Testing**: pytest, ruff, autonomous-work probe, released-work probe, handoff fact checker, strict agent harness
**Target Platform**: GitHub Actions sidecar workflow and local Codex worktree
**Project Type**: Python analytics/reporting module plus SDD docs
**Performance Goals**: Deterministic sidecar report generation with small in-memory candidate lists
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no paid external service
**Scale/Scope**: Existing autonomous-work evidence set plus three read-only investment-edge evidence surfaces

## Constitution Check

- Principle I/II/VI: No order, position sizing, whitelist, capital, or live deployment path changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No external API calls are added.
- Principle VIII.A: No market-hours live deploy behavior changes.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: Candidate generation is evidence-driven and remains below the existing `Backtest -> Canary -> Full` staged rollout. This feature generates no-live work packets only.

**Gate Result**: Pass. Risk grade 2 because autonomous work selection/reporting behavior changes, but the money path and safety perimeter are unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/094-investment-edge-frontier-map/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── investment-edge-frontier-map.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/autonomous_work_execution.py
scripts/autonomous_work_execution_probe.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_autonomous_work_execution_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Use the existing autonomous-work module and probe. The feature is a reporting and work-packet selection extension, so no new package or workflow is needed.

## Complexity Tracking

No constitution violations or new architectural layers.
