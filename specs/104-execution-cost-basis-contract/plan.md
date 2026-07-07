# Implementation Plan: Execution Cost Basis Contract

**Branch**: `Codex/104-execution-cost-basis-contract` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/104-execution-cost-basis-contract/spec.md`

## Summary

Create a read-only execution cost basis contract for `candidate-execution-cost-basis-contract`. The report consumes existing execution-quality, KIS smoke, micro GTAA, money-path, pipeline-liveness, released-work, and capital-path sidecar snapshots; separates measurable accepted/fill cost basis from normal observation wait; records the completed candidate marker; and proves autonomous-work advances to `candidate-broker-diagnostic-liveness-contract` after release.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing analytics/reporting patterns, `pytest`, `ruff`, existing released-work and autonomous-work probes
**Storage**: No new durable storage; emitted JSON/Markdown reports only
**Testing**: pytest, ruff, execution cost basis probe, released-work/autonomous-work replay, handoff fact checker, strict agent harness
**Target Platform**: GitHub Actions sidecar evidence and local Codex worktree
**Project Type**: Python analytics/reporting module plus CLI-style probe and SDD docs
**Performance Goals**: Deterministic report generation from small sidecar snapshots without network calls
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no fresh external collection; no paid external service
**Scale/Scope**: Existing execution-quality, KIS smoke, rebalance-micro-gtaa, money-path, pipeline-liveness, released-work, and capital-path readiness sidecars

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principle I/II/VI: No order, position sizing, whitelist, capital, or staged rollout behavior changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No new external API calls are added; existing sidecar snapshots are read only.
- Principle VIII.A: No market-hours live deploy behavior changes.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: The feature improves evidence quality for measurement-driven autonomous growth while staying below the `Backtest -> Canary -> Full` money path. It emits a report and completion marker only.

**Gate Result**: Pass. Risk grade 2 because autonomous work selection/reporting, SDD pointer, and completion ledger inputs change. The money path and safety perimeter are unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/104-execution-cost-basis-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── execution-cost-basis-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/execution_cost_basis.py
scripts/execution_cost_basis_probe.py
tests/unit/test_execution_cost_basis.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_execution_cost_basis_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a focused analytics module and probe for the execution cost basis contract. Reuse existing autonomous-work release advancement logic; add only the verification needed to prove the completed marker moves the next work packet to `candidate-broker-diagnostic-liveness-contract`.

## Complexity Tracking

No constitution violations or new architectural layers.

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/execution-cost-basis-contract.md](./contracts/execution-cost-basis-contract.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

Pass. The design remains read-only, consumes existing sidecars only, adds no external collection, and records the candidate completion marker without touching the safety perimeter.
