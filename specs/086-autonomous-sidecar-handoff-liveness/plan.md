# Implementation Plan: Autonomous Sidecar Handoff Liveness Closure

**Branch**: `Codex/086-autonomous-sidecar-liveness` | **Date**: 2026-07-03 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/086-autonomous-sidecar-handoff-liveness/spec.md`

## Summary

`candidate-88a7e7f07361` asks to register `autonomous-evolution` in `pipeline-liveness` and leave a single HANDOFF entrypoint. Current main already satisfies those conditions, but `evolution_loop` still emits the candidate as `new`. This plan adds a narrow completion predicate so the agent-operations candidate becomes non-actionable when the liveness and handoff evidence are present, while preserving the candidate as actionable if either evidence surface regresses. The work also adds a completed-candidate contract marker for `released-work`.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: stdlib analytics modules, pytest, ruff  
**Storage**: Git-tracked Speckit documents and automation sidecar text/JSON  
**Testing**: pytest focused unit/integration tests, full pytest, ruff, strict harness, HANDOFF fact checker  
**Target Platform**: Local repo plus GitHub Actions sidecar workflows  
**Project Type**: Python CLI/automation repository  
**Performance Goals**: Candidate scan remains deterministic and lightweight; no network call is introduced.  
**Constraints**: Read-only candidate scoring only; no broker, order, capital, whitelist/caps, live strategy, secret, paid-service, constitution, or kernel-manifest change.  
**Scale/Scope**: One autonomous candidate family and one completed-candidate contract.

## Constitution Check

- **Principles I-II**: No position sizing, exposure, whitelist, or order path touched.
- **Principle III**: No LLM judgment point added.
- **Principle IV**: No audit-log mutation or deletion.
- **Principle V**: No secret read/write path added; outputs remain masked by existing evolution-loop safety checks.
- **Principle VI**: No staged rollout or strategy promotion path changed.
- **Principle VII**: No external API path changed.
- **Principle VIII.A**: No live deploy logic changed.
- **Principles IX/X**: Autonomous improvement remains within read-only evidence and PR review path. Risk grade 2 applies because autonomous candidate selection and handoff behavior change, but money-path authority does not expand.

## Project Structure

### Documentation (this feature)

```text
specs/086-autonomous-sidecar-handoff-liveness/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── agent-ops-liveness-closure.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/evolution_loop.py
src/auto_invest/analytics/autonomous_work_execution.py
src/auto_invest/analytics/promotion_loop.py
src/auto_invest/analytics/candidate_factory.py
tests/unit/test_evolution_loop.py
tests/unit/test_autonomous_work_execution.py
tests/unit/test_promotion_loop.py
tests/unit/test_candidate_factory.py
tests/integration/test_evolution_loop_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Keep the predicate in `evolution_loop.py` because candidate status is generated there. Keep the completion marker in Speckit contracts because `released-work` already consumes that pattern.

## Complexity Tracking

No constitutional gate violations. No new abstraction beyond a small local predicate.
