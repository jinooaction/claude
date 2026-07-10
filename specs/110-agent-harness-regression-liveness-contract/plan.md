# Implementation Plan: Agent Harness Regression Liveness Contract

**Branch**: `Codex/110-agent-harness-regression-liveness-contract` | **Date**: 2026-07-10 | **Spec**: `specs/110-agent-harness-regression-liveness-contract/spec.md`
**Input**: Feature specification from `/specs/110-agent-harness-regression-liveness-contract/spec.md`

## Summary

Add a read-only agent harness regression liveness contract that wraps the existing evaluation, first-response quality, redteam, and strict harness evidence into a deterministic PASS/WAIT/FAIL report and CLI probe. The report verifies harness source surfaces, suite coverage, supplied strict output, released-work completion, and autonomous-work advancement to a new operator-readable report liveness candidate.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `scripts/agent_harness_probe.py`, `scripts/check_handoff_facts.py`, and `auto_invest.analytics.autonomous_work_execution`
**Storage**: Local repository files plus optional supplied sidecar/output files
**Testing**: pytest, ruff, probe smoke, released-work replay, autonomous-work replay, handoff fact checker, strict agent harness
**Target Platform**: Local macOS/Linux checkout and GitHub Actions-compatible repository context
**Project Type**: Single Python package with scripts and Speckit docs
**Performance Goals**: Probe completes in under a few seconds and performs no network or external service calls
**Constraints**: Read-only contract; no broker/order/capital/live/secret/constitution/kernel changes; no fresh external collection
**Scale/Scope**: One analytics module, one CLI probe, focused unit/integration tests, autonomous-work template update, SDD and handoff updates

## Constitution Check

- Safety boundary: no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel modification.
- Money path: unchanged and not executable from this feature.
- External effects: no network, no GitHub API from the report module, no SSH, no paid service.
- Operating risk grade: 2, because agent operating-system observability and next-work selection change.
- Verification required: focused pytest, full pytest, ruff, `git diff --check`, PR body quality gate, `check_handoff_facts.py`, strict agent harness.

## Project Structure

```text
src/auto_invest/analytics/
└── agent_harness_regression_liveness.py
scripts/
└── agent_harness_regression_liveness_probe.py
tests/unit/
├── test_agent_harness_regression_liveness.py
└── test_autonomous_work_execution.py
tests/integration/
└── test_agent_harness_regression_liveness_probe.py
specs/110-agent-harness-regression-liveness-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── agent-harness-regression-liveness.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

## Complexity Tracking

No constitution violations. Complexity is limited to a small read-only analytics module plus autonomous-work frontier continuation.

## Phase 0 Research

See `research.md`. Decision: reuse `scripts/agent_harness_probe.py` evaluator functions and consume strict execution evidence as a supplied observation rather than running external or mutating operations inside the report module.

## Phase 1 Design

See `data-model.md`, `contracts/agent-harness-regression-liveness.md`, and `quickstart.md`.

## Implementation Strategy

1. Add failing focused tests for the report, probe, and autonomous-work transition.
2. Implement the report module around existing harness evaluator functions and static source inspection.
3. Add the CLI probe.
4. Add the next agent-ops candidate template for operator-readable report liveness.
5. Mark tasks complete only after focused and full verification pass.
