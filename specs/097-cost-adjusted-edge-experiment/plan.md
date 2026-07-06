# Implementation Plan: Cost-Adjusted Edge Experiment

**Branch**: `Codex/097-cost-adjusted-edge-experiment` | **Date**: 2026-07-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/097-cost-adjusted-edge-experiment/spec.md`

## Summary

Add a read-only cost-adjusted-edge experiment report for `candidate-cost-adjusted-edge-experiment`. The report consumes forward tournament evidence, execution-quality evidence, money-path state, released-work closure evidence, learning ledger state, and pipeline liveness. It computes provisional cost-stressed forward returns while explicitly keeping cost-basis completeness separate from real execution cost. Current evidence should produce `OBSERVATION_WAIT`, not false readiness.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing analytics modules, forward tournament parsing rules, execution-quality report format, released-work scanner, pytest, ruff
**Storage**: No new durable storage; local/probe JSON and Markdown only
**Testing**: pytest focused unit/integration, local sidecar replay, full pytest, ruff, diff check, handoff fact checker, strict agent harness
**Target Platform**: Local Codex worktree and GitHub Actions sidecar-style probes
**Project Type**: Python analytics/reporting module plus script probe and SDD docs
**Performance Goals**: Deterministic in-memory parsing of small sidecar snapshots
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no paid external service
**Scale/Scope**: Six sidecar inputs, current forward tournament tracks, one no-live experiment contract, one released-work completion marker

## Constitution Check

- Principle I/II/VI: No order path, position sizing, whitelist, capital, or live rollout behavior changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No new external API calls are added.
- Principle VIII.A/B: No live deploy behavior or deploy guard behavior is changed.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: The feature is evidence-driven and explicitly separates no-live experiment design from live money.

**Gate Result**: Pass. Risk grade 2 because operating reports, candidate closure, and next-session behavior change; money path and safety perimeter remain unchanged.

## Project Structure

### Documentation

```text
specs/097-cost-adjusted-edge-experiment/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cost-adjusted-edge-experiment.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/cost_adjusted_edge_experiment.py
scripts/cost_adjusted_edge_experiment_probe.py
tests/unit/test_cost_adjusted_edge_experiment.py
tests/integration/test_cost_adjusted_edge_experiment_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a dedicated analytics module and probe, matching the existing no-live experiment contract pattern. Reuse released-work scanning through `--repo-root` so local replay can prove candidate closure without waiting for sidecar lag.

## Complexity Tracking

No constitution violations or new architectural layers.

