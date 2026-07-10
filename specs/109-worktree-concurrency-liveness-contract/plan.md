# Implementation Plan: Worktree Concurrency Liveness Contract

**Branch**: `Codex/109-worktree-concurrency-liveness-contract` | **Date**: 2026-07-10 | **Spec**: `specs/109-worktree-concurrency-liveness-contract/spec.md`
**Input**: Feature specification from `/specs/109-worktree-concurrency-liveness-contract/spec.md`

## Summary

Add a read-only worktree concurrency liveness contract that wraps existing local concurrency guard surfaces into a deterministic PASS/WAIT/FAIL report and CLI probe. The report verifies session-start and git hook wiring, synthetic guard WARN/BLOCK behavior, recovery snapshot surface, optional runtime guard output, released-work completion, and autonomous-work advancement to a new agent harness regression liveness candidate.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `scripts/local_concurrency_guard.py`, `auto_invest.analytics.autonomous_work_execution`, and `released_work` scan path
**Storage**: Local repository files and optional gitignored `.codex/state/concurrency` runtime state
**Testing**: pytest, ruff, probe smoke, released-work replay, autonomous-work replay, handoff fact checker, strict agent harness
**Target Platform**: Local macOS/Linux checkout and GitHub Actions-compatible repository context
**Project Type**: Single Python package with scripts and Speckit docs
**Performance Goals**: Probe completes in under a few seconds and performs no network or external service calls
**Constraints**: Read-only contract; no broker/order/capital/live/secret/constitution/kernel changes; no worktree creation from report module
**Scale/Scope**: One analytics module, one CLI probe, focused unit/integration tests, autonomous-work template update, SDD and handoff updates

## Constitution Check

- Safety boundary: no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel modification.
- Money path: unchanged and not executable from this feature.
- External effects: no network, no GitHub API, no SSH, no paid service.
- Operating risk grade: 2, because agent operating-system observability and next-work selection change.
- Verification required: focused pytest, full pytest, ruff, `git diff --check`, PR body quality gate, `check_handoff_facts.py`, strict agent harness.

## Project Structure

```text
src/auto_invest/analytics/
└── worktree_concurrency_liveness.py
scripts/
└── worktree_concurrency_liveness_probe.py
tests/unit/
├── test_worktree_concurrency_liveness.py
└── test_autonomous_work_execution.py
tests/integration/
└── test_worktree_concurrency_liveness_probe.py
specs/109-worktree-concurrency-liveness-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── worktree-concurrency-liveness.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

## Complexity Tracking

No constitution violations. Complexity is limited to a small read-only analytics module plus autonomous-work frontier continuation.

## Phase 0 Research

See `research.md`. Decision: simulate guard behavior in memory and inspect hook/source surfaces rather than creating real worktrees or mutating local lease state.

## Phase 1 Design

See `data-model.md`, `contracts/worktree-concurrency-liveness.md`, and `quickstart.md`.

## Implementation Strategy

1. Add failing focused tests for the report, probe, and autonomous-work transition.
2. Implement the report module around existing guard dataclasses/functions and static hook inspection.
3. Add the CLI probe.
4. Add the next agent-ops candidate template and required input refs.
5. Mark tasks complete only after focused and full verification pass.
