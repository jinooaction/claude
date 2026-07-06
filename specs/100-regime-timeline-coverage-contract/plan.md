# Implementation Plan: Regime Timeline Coverage Contract

**Branch**: `Codex/100-regime-timeline-coverage-contract` | **Date**: 2026-07-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/100-regime-timeline-coverage-contract/spec.md`

## Summary

Create a read-only regime timeline coverage contract that consumes existing `regime_timeline.csv`, `regime-stratify`, pipeline liveness, and released-work sidecar snapshots. The report must prove that timeline labels are structurally usable, every stratified strategy section preserves the d+1 forward join contract, sparse rare-regime observations are represented as `OBSERVATION_WAIT`, malformed joins are `BLOCKED`, and released-work advances the autonomous loop to `candidate-data-evidence-liveness-contract` when this candidate is complete.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing analytics/reporting modules, released-work scanner, pytest, ruff
**Storage**: No new durable storage; emitted JSON/Markdown sidecar reports only
**Testing**: pytest, ruff, regime timeline coverage probe, released-work probe, autonomous-work probe, handoff fact checker, strict agent harness
**Target Platform**: GitHub Actions sidecar evidence and local Codex worktree
**Project Type**: Python analytics/reporting module plus SDD docs
**Performance Goals**: Deterministic report generation from small sidecar snapshots without network calls
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no paid external service; no fresh public-data collection
**Scale/Scope**: Existing public-data regime timeline, regime-stratify, pipeline-liveness, released-work, and autonomous-work frontier surfaces

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principle I/II/VI: No order, position sizing, whitelist, capital, or live deployment path changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No new external API calls are added; existing sidecar snapshots are read only.
- Principle VIII.A: No market-hours live deploy behavior changes.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: The feature improves evidence quality for measurement-driven autonomous growth while remaining below the staged `Backtest -> Canary -> Full` path. It emits a report and completion marker only.

**Gate Result**: Pass. Risk grade 2 because autonomous work selection/reporting and SDD pointers change, but the money path and safety perimeter are unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/100-regime-timeline-coverage-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── regime-timeline-coverage-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/regime_timeline_coverage.py
src/auto_invest/analytics/autonomous_work_execution.py
scripts/regime_timeline_coverage_probe.py
tests/unit/test_regime_timeline_coverage.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_regime_timeline_coverage_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a focused analytics module and probe for the regime timeline coverage contract, then add only the autonomous-work advancement coverage needed to prove released `candidate-regime-timeline-coverage-contract` moves to the next data evidence frontier entry.

## Complexity Tracking

No constitution violations or new architectural layers.

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/regime-timeline-coverage-contract.md](./contracts/regime-timeline-coverage-contract.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

Pass. The design remains read-only, consumes existing sidecars only, adds no external collection, and records the candidate completion marker without touching the safety perimeter.
