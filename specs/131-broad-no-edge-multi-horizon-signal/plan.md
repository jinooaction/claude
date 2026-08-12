# Implementation Plan: Broad NO_EDGE Multi-Horizon Signal

**Branch**: `codex/broad-no-edge-multi-horizon-signal` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/131-broad-no-edge-multi-horizon-signal/spec.md`

## Summary

Add a read-only broad no-edge multi-horizon signal report that turns the selected work packet `candidate-broad-no-edge-multi-horizon-signal-experiment` into a concrete no-live contract. The report consumes current sidecars, summarizes current forward track signal and holding-period exposure, separates already-repeated single-horizon momentum from new trend/carry/quality/volatility candidates, and marks this candidate complete so autonomous-work can advance to the regime-cost robustness candidate.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Existing analytics modules, released-work scanner, pytest, ruff  
**Storage**: No new durable storage; local/probe JSON and Markdown only  
**Testing**: pytest focused unit/integration, full pytest, ruff, diff check, handoff fact checker, strict agent harness  
**Target Platform**: Local Codex worktree and GitHub Actions sidecar-style probes  
**Project Type**: Python analytics/reporting module plus script probe and SDD docs  
**Performance Goals**: Deterministic in-memory parsing of small sidecar snapshots  
**Constraints**: Read-only; no broker API; no orders; no capital allocation; no live strategy change; no whitelist/caps change; no secret read/write; no constitution/kernel modification; no paid external service  
**Scale/Scope**: Eight sidecar inputs, current forward tournament tracks, one no-live experiment contract, one released-work completion marker

## Constitution Check

- Principle I/II/VI: No order path, position sizing, whitelist, capital, or live rollout behavior changes.
- Principle IV/V: No audit log mutation and no secret reads/writes.
- Principle VII: No new external API calls are added.
- Principle VIII.A/B: No live deploy behavior or deploy guard behavior is changed.
- Principle IX: No kernel, constitution, caps, whitelist, audit, secret, or deploy-safety files are modified.
- Principle X: The feature is evidence-driven and explicitly separates no-live experiment design from live money. It creates no-live validation evidence only.

**Gate Result**: Pass. Risk grade 2 because operating reports, candidate closure, and next-session behavior change; money path and safety perimeter remain unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/131-broad-no-edge-multi-horizon-signal/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── broad-no-edge-multi-horizon-signal.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/broad_no_edge_multi_horizon_signal.py
scripts/broad_no_edge_multi_horizon_signal_probe.py
tests/unit/test_broad_no_edge_multi_horizon_signal.py
tests/integration/test_broad_no_edge_multi_horizon_signal_probe.py
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Add a dedicated analytics module and probe, matching the existing broad no-edge experiment pattern. The autonomous-work module already selects this candidate; the new module materializes the candidate's contract and completion marker.

## Complexity Tracking

No constitution violations or new architectural layers.
