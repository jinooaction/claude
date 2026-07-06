# Implementation Plan: Public Data Input Quality Contract

**Branch**: `Codex/099-public-data-input-quality-contract` | **Date**: 2026-07-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/099-public-data-input-quality-contract/spec.md`

## Summary

Create a read-only public-data input-quality contract that consumes existing public-data, regime, regime timeline, regime-stratify, pipeline-liveness, released-work, and capital-path readiness sidecar snapshots. The report must distinguish `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED`, close `candidate-public-data-input-quality-contract` through released-work when the spec is complete, and let autonomous-work advance to the next unreleased data evidence candidate.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing analytics/reporting modules, released-work scanner, pytest, ruff
**Storage**: No new durable storage; emitted JSON/Markdown sidecar reports only
**Testing**: pytest, ruff, public-data input-quality probe, released-work probe, autonomous-work probe, handoff fact checker, strict agent harness
**Target Platform**: GitHub Actions sidecar workflow and local Codex worktree
**Project Type**: Python analytics/reporting module plus SDD docs
**Performance Goals**: Deterministic report generation from small sidecar snapshots without network calls
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no paid external service; no fresh public-data collection
**Scale/Scope**: Existing public-data, regime, regime-stratify, pipeline-liveness, released-work, and capital-path readiness sidecar surfaces

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principle I/II/VI: No order, position sizing, whitelist, capital, or live deployment path changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No new external API calls are added; existing sidecar snapshots are read only.
- Principle VIII.A: No market-hours live deploy behavior changes.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: Data quality work is evidence-driven and remains below the existing `Backtest -> Canary -> Full` staged rollout. This feature emits a contract report and work completion marker only.

**Gate Result**: Pass. Risk grade 2 because autonomous work selection/reporting behavior changes, but the money path and safety perimeter are unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/099-public-data-input-quality-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── public-data-input-quality-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/public_data_input_quality.py
src/auto_invest/analytics/autonomous_work_execution.py
scripts/public_data_input_quality_probe.py
tests/unit/test_public_data_input_quality.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_public_data_input_quality_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Use a new focused analytics module and probe for the input-quality contract, then minimally extend autonomous-work candidate advancement so the released candidate moves to the next data evidence frontier entry.

## Complexity Tracking

No constitution violations or new architectural layers.
