# Implementation Plan: Data Evidence Liveness Contract

**Branch**: `Codex/101-data-evidence-liveness-contract` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/101-data-evidence-liveness-contract/spec.md`

## Summary

Create a read-only data evidence liveness contract that consumes existing public-data, regime-stratify, pipeline-liveness, released-work, and capital-path sidecar snapshots. The report must convert `collect-public-data` and `regime-stratify` liveness into explicit PASS/WAIT/FAIL gates, cross-check pipeline timestamps against the source LAST_RUN files, fail closed when the liveness registry cannot be audited, and prove autonomous-work advances to `candidate-execution-quality-frontier-map` once the final data evidence candidate is released.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing analytics/reporting modules, `pipeline_liveness.parse_timestamp_utc`, released-work scanner, pytest, ruff
**Storage**: No new durable storage; emitted JSON/Markdown sidecar reports only
**Testing**: pytest, ruff, data evidence liveness probe, released-work/autonomous-work replay, handoff fact checker, strict agent harness
**Target Platform**: GitHub Actions sidecar evidence and local Codex worktree
**Project Type**: Python analytics/reporting module plus SDD docs
**Performance Goals**: Deterministic report generation from small sidecar snapshots without network calls
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no paid external service; no fresh public-data collection
**Scale/Scope**: Existing public-data, regime-stratify, pipeline-liveness, released-work, capital-path readiness, and autonomous-work frontier surfaces

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
specs/101-data-evidence-liveness-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── data-evidence-liveness-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/data_evidence_liveness.py
src/auto_invest/analytics/autonomous_work_execution.py
scripts/data_evidence_liveness_probe.py
tests/unit/test_data_evidence_liveness.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_data_evidence_liveness_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a focused analytics module and probe for the data evidence liveness contract, then add only the autonomous-work advancement coverage needed to prove released `candidate-data-evidence-liveness-contract` moves the macro frontier to execution quality.

## Complexity Tracking

No constitution violations or new architectural layers.

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/data-evidence-liveness-contract.md](./contracts/data-evidence-liveness-contract.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

Pass. The design remains read-only, consumes existing sidecars only, adds no external collection, and records the candidate completion marker without touching the safety perimeter.
