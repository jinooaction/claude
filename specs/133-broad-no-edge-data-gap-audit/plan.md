# Implementation Plan: Broad NO_EDGE Data Gap Audit

**Branch**: `codex/broad-no-edge-data-gap-audit` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/133-broad-no-edge-data-gap-audit/spec.md`

## Summary

Add a read-only broad no-edge data gap audit report that turns the selected work packet `candidate-broad-no-edge-data-gap-audit` into a concrete no-live contract. The report consumes current public-data, regime timeline, regime-stratify, forward paper, money-path, edge-autoarm, released-work, and pipeline-liveness sidecars. It classifies data publication gaps, cross-check skips, regime indicator gaps, timeline column missingness, stratified join coverage, and causal impact on the current `NO_EDGE_YET` verdict without opening real orders or changing live strategy state.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing analytics modules, released-work scanner, pytest, ruff
**Storage**: No new durable storage; local/probe JSON and Markdown only
**Testing**: pytest focused unit/integration, full pytest, ruff, diff check, handoff fact checker, strict agent harness
**Target Platform**: Local Codex worktree and GitHub Actions sidecar-style probes
**Project Type**: Python analytics/reporting module plus script probe and SDD docs
**Performance Goals**: Deterministic in-memory parsing of small sidecar snapshots
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no fresh external collection; no paid external service
**Scale/Scope**: Ten sidecar inputs, current public-data item set, current regime timeline CSV, current stratified regime sections, one no-live audit contract, one released-work completion marker

## Constitution Check

- Principle I/II/VI: No order path, position sizing, whitelist, capital, or live rollout behavior changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No new external API calls are added.
- Principle VIII.A/B: No live deploy behavior or deploy guard behavior is changed.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: The feature is evidence-driven and explicitly separates data-gap diagnosis from live money. It creates no-live validation evidence only.

**Gate Result**: Pass. Risk grade 2 because operating reports, candidate closure, and next-session behavior change; money path and safety perimeter remain unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/133-broad-no-edge-data-gap-audit/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── broad-no-edge-data-gap-audit.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/broad_no_edge_data_gap_audit.py
scripts/broad_no_edge_data_gap_audit_probe.py
tests/unit/test_broad_no_edge_data_gap_audit.py
tests/integration/test_broad_no_edge_data_gap_audit_probe.py
tests/unit/test_autonomous_work_execution.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a dedicated analytics module and probe, matching the existing broad no-edge experiment pattern. The autonomous-work module already knows the frontier order; the new module materializes the data-gap audit and completion marker.

## Complexity Tracking

No constitution violations or new architectural layers.
