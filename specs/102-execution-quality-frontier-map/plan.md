# Implementation Plan: Execution Quality Frontier Map

**Branch**: `Codex/102-execution-quality-frontier-map` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/102-execution-quality-frontier-map/spec.md`

## Summary

Extend the read-only autonomous-work execution report so the selected execution-quality frontier candidate becomes a nested execution quality frontier map. Before this spec is released, the loop continues to select `candidate-execution-quality-frontier-map`; after released-work records that candidate, it advances to the first execution-quality candidate, `candidate-broker-rejection-taxonomy-contract`, using execution-quality, KIS smoke, rebalance-micro-gtaa, money-path, pipeline-liveness, released-work, and capital-path readiness evidence refs.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `auto_invest.analytics.autonomous_work_execution`, released-work scanner, pytest, ruff
**Storage**: No new durable storage; emitted JSON/Markdown sidecar fields only
**Testing**: pytest, ruff, autonomous-work probe, released-work probe, handoff fact checker, strict agent harness
**Target Platform**: GitHub Actions sidecar workflow and local Codex worktree
**Project Type**: Python analytics/reporting module plus SDD docs
**Performance Goals**: Deterministic sidecar report generation with small in-memory candidate lists
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no paid external service; no fresh external collection in this feature
**Scale/Scope**: Existing autonomous-work evidence set plus execution-quality and broker diagnostic read-only sidecar surfaces

## Constitution Check

- Principle I/II/VI: No order, position sizing, whitelist, capital, or live deployment path changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No new external API calls are added; existing sidecar snapshots are read only.
- Principle VIII.A: No market-hours live deploy behavior changes.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: Candidate generation remains measurement-driven and below the existing `Backtest -> Canary -> Full` staged rollout. This feature generates work packets only.

**Gate Result**: Pass. Risk grade 2 because autonomous work selection/reporting behavior changes, but the money path and safety perimeter are unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/102-execution-quality-frontier-map/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── execution-quality-frontier-map.md
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

