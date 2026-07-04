# Implementation Plan: Forward Regime Edge Experiment

**Branch**: `Codex/095-forward-regime-edge-experiment` | **Date**: 2026-07-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/095-forward-regime-edge-experiment/spec.md`

## Summary

Add a read-only forward-regime-edge experiment report that turns the selected work packet `candidate-forward-regime-edge-experiment` into a concrete no-live contract. The report consumes the five required sidecars, summarizes forward tournament tracks and money-path state, emits validation gates, and marks the candidate complete so autonomous-work can advance to the next investment-edge experiment candidate.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing analytics modules, forward tournament parsing rules, released-work scanner, pytest, ruff
**Storage**: No new durable storage; local/probe JSON and Markdown only
**Testing**: pytest focused unit/integration, full pytest, ruff, diff check, handoff fact checker, strict agent harness
**Target Platform**: Local Codex worktree and GitHub Actions sidecar-style probes
**Project Type**: Python analytics/reporting module plus script probe and SDD docs
**Performance Goals**: Deterministic in-memory parsing of small sidecar snapshots
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no paid external service
**Scale/Scope**: Five sidecar inputs, seven forward tournament tracks, one no-live experiment contract

## Constitution Check

- Principle I/II/VI: No order path, position sizing, whitelist, capital, or live rollout behavior changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No new external API calls are added.
- Principle VIII.A/B: No live deploy behavior or deploy guard behavior is changed.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: The feature is evidence-driven and explicitly separates deploy/code from live money. It creates no-live validation evidence only.

**Gate Result**: Pass. Risk grade 2 because operating reports, candidate closure, and next-session behavior change; money path and safety perimeter remain unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/095-forward-regime-edge-experiment/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── forward-regime-edge-experiment.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/forward_regime_edge_experiment.py
scripts/forward_regime_edge_experiment_probe.py
tests/unit/test_forward_regime_edge_experiment.py
tests/integration/test_forward_regime_edge_experiment_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a dedicated analytics module and probe instead of overloading autonomous-work selection. The autonomous-work module already selects this candidate; the new module materializes the candidate's no-live contract.

## Complexity Tracking

No constitution violations or new architectural layers.
