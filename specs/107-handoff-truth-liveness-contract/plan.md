# Implementation Plan: HANDOFF Truth Liveness Contract

**Branch**: `Codex/107-handoff-truth-liveness-contract` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/107-handoff-truth-liveness-contract/spec.md`

## Summary

Add a read-only HANDOFF truth liveness contract that wraps the existing HANDOFF fact checker into a reusable analytics report and CLI probe. The report distinguishes current `origin/main` matches from valid handoff-only first-parent matches, blocks truly stale HANDOFF rows, records `candidate-handoff-truth-liveness-contract` as the completed candidate, and verifies autonomous-work advances to `candidate-pr-merge-evidence-liveness-contract` once released-work closes it.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing `scripts/check_handoff_facts.py`, `auto_invest.analytics.autonomous_work_execution`, and `released_work` scan path
**Storage**: Repository Markdown and JSON artifacts only
**Testing**: pytest, ruff, probe smoke, released-work replay, autonomous-work replay, handoff fact checker, strict agent harness
**Target Platform**: Local Codex worktree and GitHub workflow dry-run worker
**Project Type**: Python package with CLI probes and automation sidecar reports
**Performance Goals**: Current repo evaluation completes in one local probe run without network-dependent logic
**Constraints**: Read-only evidence consumption; no broker API, orders, capital allocation, live strategy, whitelist/caps, secret, constitution, kernel, fresh external collection, or paid-service change
**Scale/Scope**: One HANDOFF file, git baseline facts, existing operating-control references, and autonomous-work completion transition

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principles I, II, IV, VI: No orders, positions, capital sizing, audit log schema, or rollout-stage behavior changes.
- Principle V: No secret read/write; reports expose only repository-visible paths and git commit evidence.
- Principle VII: No external API call is added.
- Principle VIII.A/B: Code change deploys through the existing guarded pipeline; no market-hours deploy bypass.
- Principle IX: No constitution or kernel file touch.
- Principle X: This improves the autonomous growth loop's evidence quality without changing live money or strategy selection.

**Gate Result**: Pass. Risk grade 2 operating-system observability and next-work completion change.

## Project Structure

### Documentation (this feature)

```text
specs/107-handoff-truth-liveness-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── handoff-truth-liveness.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/handoff_truth_liveness.py
scripts/handoff_truth_liveness_probe.py
tests/unit/test_handoff_truth_liveness.py
tests/unit/test_autonomous_work_execution.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a small analytics module and probe script for the new contract. Reuse `check_handoff_facts.py` for existing facts rather than duplicating the stale-vs-handoff-only rule.

## Complexity Tracking

No constitution violations or new architectural complexity.

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/handoff-truth-liveness.md](./contracts/handoff-truth-liveness.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

Pass. The design remains read-only, consumes repo-local facts only, adds no external collection, and records the candidate completion marker without touching the safety perimeter.
