# Implementation Plan: PR/Merge Evidence Liveness Contract

**Branch**: `Codex/108-pr-merge-evidence-liveness-contract` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/108-pr-merge-evidence-liveness-contract/spec.md`

## Summary

Add a read-only PR/merge evidence liveness contract that turns PR body quality, main merge evidence, released-work consumption, and deploy-status observation into a deterministic PASS/WAIT/FAIL report. The report records `candidate-pr-merge-evidence-liveness-contract` as the completed candidate and verifies autonomous-work advances to `candidate-worktree-concurrency-liveness-contract` once released-work closes it.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing PR quality-gate script, `auto_invest.analytics.autonomous_work_execution`, released-work sidecar shape, git command-line metadata
**Storage**: Repository Markdown and JSON artifacts only
**Testing**: pytest, ruff, probe smoke, released-work replay, autonomous-work replay, handoff fact checker, strict agent harness
**Target Platform**: Local Codex worktree and GitHub workflow dry-run worker
**Project Type**: Python package with CLI probes and automation sidecar reports
**Performance Goals**: Current repo evaluation completes in one local probe run without network-dependent logic
**Constraints**: Read-only evidence consumption; no broker API, orders, capital allocation, live strategy, whitelist/caps, secret, constitution, kernel, fresh external collection, or paid-service change
**Scale/Scope**: One PR body text, latest main merge fact, released-work sidecar JSON, deploy observation text, and autonomous-work completion transition

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Principles I, II, IV, VI: No orders, positions, capital sizing, audit log schema, or rollout-stage behavior changes.
- Principle V: No secret read/write; reports expose only repository-visible paths, git commit evidence, and supplied observation text.
- Principle VII: No external API call is added.
- Principle VIII.A/B: Code change deploys through the existing guarded pipeline; this feature does not bypass market-hours deploy guards.
- Principle IX: No constitution or kernel file touch.
- Principle X: This improves the autonomous growth loop's completion evidence without changing live money or strategy selection.

**Gate Result**: Pass. Risk grade 2 operating-system observability and next-work completion change.

## Project Structure

### Documentation (this feature)

```text
specs/108-pr-merge-evidence-liveness-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── pr-merge-evidence-liveness.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/pr_merge_evidence_liveness.py
scripts/pr_merge_evidence_liveness_probe.py
tests/unit/test_pr_merge_evidence_liveness.py
tests/integration/test_pr_merge_evidence_liveness_probe.py
tests/unit/test_autonomous_work_execution.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a small analytics module and probe script for the new contract. Reuse existing autonomous-work frontier selection instead of creating a new work-selection mechanism.

## Complexity Tracking

No constitution violations or new architectural complexity.

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/pr-merge-evidence-liveness.md](./contracts/pr-merge-evidence-liveness.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

Pass. The design remains read-only, consumes repo-local facts and supplied observations only, adds no external collection, and records the candidate completion marker without touching the safety perimeter.
