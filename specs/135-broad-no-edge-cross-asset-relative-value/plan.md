# Implementation Plan: Broad No-Edge Cross-Asset Relative Value

**Branch**: `codex/broad-no-edge-cross-asset-relative-value-isolated` | **Date**: 2026-08-15 | **Spec**: `specs/135-broad-no-edge-cross-asset-relative-value/spec.md`  
**Input**: Feature specification from `specs/135-broad-no-edge-cross-asset-relative-value/spec.md`

## Summary

Create a read-only no-live contract for `candidate-broad-no-edge-cross-asset-relative-value-experiment`. The contract consumes existing sidecars, classifies relative-value candidate lanes, verifies money-path remains no-live, provides a probe, and leaves a completed candidate marker so released-work can advance autonomous-work to tail-risk convexity.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Standard library, existing auto_invest analytics modules  
**Storage**: Existing sidecar text/JSON files only  
**Testing**: pytest and ruff  
**Target Platform**: Local repo and GitHub Actions automation  
**Project Type**: Python analytics/CLI contract  
**Performance Goals**: Parse current sidecars in under one second locally  
**Constraints**: Read-only, deterministic, no broker API, no orders, no capital allocation, no live strategy change, no paid external service  
**Scale/Scope**: One analytics module, one probe, focused unit/integration tests, SDD artifacts

## Constitution Check

No violation. This is 등급 2 운영 보정 and no-live contract work. It does not touch actual orders, live arming, capital allocation, whitelist/caps, secrets, audit logs, constitution, or kernel manifest.

## Project Structure

### Documentation

```text
specs/135-broad-no-edge-cross-asset-relative-value/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── broad-no-edge-cross-asset-relative-value.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/broad_no_edge_cross_asset_relative_value.py
scripts/broad_no_edge_cross_asset_relative_value_probe.py
tests/unit/test_broad_no_edge_cross_asset_relative_value.py
tests/integration/test_broad_no_edge_cross_asset_relative_value_probe.py
```

**Structure Decision**: Match the existing broad no-edge contract pattern: dedicated analytics module plus probe, with autonomous-work advancement handled by existing second-wave frontier ordering.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
