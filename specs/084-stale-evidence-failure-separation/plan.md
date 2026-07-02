# Implementation Plan: Stale Evidence Failure Separation

**Branch**: `Codex/084-stale-evidence-failure-separation` | **Date**: 2026-07-02 | **Spec**: `specs/084-stale-evidence-failure-separation/spec.md`
**Input**: Feature specification from `/specs/084-stale-evidence-failure-separation/spec.md`

## Summary

Enhance the read-only capital path readiness report so stale, missing, malformed, or already-released evidence is reported as `observability_issues` rather than blended into growth candidate selection. The implementation keeps the existing money-path gates and candidate scoring intact, adds `released-work` and `pipeline-liveness` to the probe manifest, and updates tests plus handoff evidence.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: standard library, pytest, ruff
**Storage**: GitHub automation sidecar branches only
**Testing**: `uv run pytest`, `uv run ruff check src tests`, focused unit/integration tests
**Target Platform**: GitHub Actions and local Codex workspace
**Project Type**: Python analytics/automation repo
**Performance Goals**: Deterministic sidecar parsing in milliseconds for small JSON/Markdown inputs
**Constraints**: Read-only, no broker/API/order/live-capital calls, no secrets, no external paid services
**Scale/Scope**: One analytics module, one probe manifest, existing workflow path filters and tests

## Constitution Check

- **Safety boundary**: Grade 2 operating-system change. It changes automation reporting, not trading rules or money movement.
- **Money path**: No actual order, capital allocation, whitelist/caps, or live setting changes.
- **Auditability**: New JSON field and Markdown section make stale evidence reproducible from sidecars.
- **SDD fit**: Full lightweight SDD artifacts are used because this changes autonomous work selection inputs.
- **Rollback**: Revert the feature commit to remove the new sidecar inputs and `observability_issues` field; existing candidate routing remains compatible.

## Project Structure

### Documentation

```text
specs/084-stale-evidence-failure-separation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── capital-path-observability.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/capital_path_readiness.py
scripts/capital_path_readiness_probe.py
.github/workflows/capital-path-readiness.yml
tests/unit/test_capital_path_readiness.py
tests/integration/test_capital_path_readiness_probe.py
```

## Complexity Tracking

No constitution violation is expected. The change is additive and read-only.

## Phase 0: Outline & Research

- Confirm current `capital-path-readiness` consumes evolution backlog/ledger/promotion but not `released-work` or `pipeline-liveness`.
- Confirm `autonomous-work-execution` already suppresses released work, so this change prevents stale work from appearing one layer earlier.
- Confirm pipeline liveness JSON may arrive as raw JSON or Markdown fenced JSON.

## Phase 1: Design & Contracts

- Add `ReadinessObservabilityIssue`.
- Extend `CapitalPathReadinessReport` with `observability_issues`.
- Extend candidate routing with released candidate suppression.
- Convert non-OK liveness checks into separate observability issues.

## Phase 2: Implementation

- Update pure analytics module first.
- Update probe manifest and workflow path filters.
- Update unit and integration tests.
- Mark `candidate-6ee3370e933d` complete in contract.

## Phase 3: Validation

- Focused tests from `quickstart.md`.
- Full pytest and ruff.
- Handoff fact checker and strict agent harness.
- PR quality gate before merge.
