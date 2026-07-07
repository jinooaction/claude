# Implementation Plan: Broker Diagnostic Liveness Contract

**Branch**: `Codex/105-broker-diagnostic-liveness-contract` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/105-broker-diagnostic-liveness-contract/spec.md`

## Summary

Create a read-only broker diagnostic liveness contract for `candidate-broker-diagnostic-liveness-contract`. The report consumes existing KIS smoke, execution-quality, pipeline-liveness, released-work, and capital-path sidecar snapshots; separates healthy broker diagnostic evidence from observation wait and blocked states; records the completed candidate marker; and proves autonomous-work advances out of the execution-quality frontier after release.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing analytics/reporting patterns, `pytest`, `ruff`, existing released-work and autonomous-work probes
**Storage**: No new durable storage; emitted JSON/Markdown reports only
**Testing**: pytest, ruff, broker diagnostic liveness probe, released-work/autonomous-work replay, handoff fact checker, strict agent harness
**Target Platform**: GitHub Actions sidecar evidence and local Codex worktree
**Project Type**: Python analytics/reporting module plus CLI-style probe and SDD docs
**Performance Goals**: Deterministic report generation from small sidecar snapshots without network calls
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no fresh external collection; no paid external service
**Scale/Scope**: Existing KIS smoke, execution-quality, pipeline-liveness, released-work, and capital-path readiness sidecars

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
specs/105-broker-diagnostic-liveness-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── broker-diagnostic-liveness-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/broker_diagnostic_liveness.py
scripts/broker_diagnostic_liveness_probe.py
tests/unit/test_broker_diagnostic_liveness.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_broker_diagnostic_liveness_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a focused analytics module and probe for the broker diagnostic liveness contract. Reuse existing autonomous-work release advancement logic; add only the verification needed to prove the completed marker moves the next work packet out of the execution-quality frontier.

## Complexity Tracking

No constitution violations or new architectural layers.

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/broker-diagnostic-liveness-contract.md](./contracts/broker-diagnostic-liveness-contract.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

Pass. The design remains read-only, consumes existing sidecars only, adds no external collection, and records the candidate completion marker without touching the safety perimeter.
