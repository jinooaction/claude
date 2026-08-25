# Implementation Plan: Options Selection and Objective Repair

**Branch**: `Codex/165-options-selection-objective-repair` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/165-options-selection-objective-repair/spec.md`

## Summary

Extend the released options variance-risk-premium factory without adding strategies. Replace the one-shot development winner with nested, expanding-window selection on PUT; replay the exact selected candidate and weights on the independent WPUT index; and publish separate premium-existence, portfolio-adoption, and timing-objective results. All historical outputs remain diagnostic and non-promotable.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Python standard library, NumPy, scikit-learn, and the repository's existing public-data parsers  
**Storage**: Versioned JSON/Markdown research sidecars and append-only JSONL trial records  
**Testing**: pytest, Ruff, YAML validation, deterministic replay, production probe  
**Target Platform**: GitHub Actions and local Linux/macOS workers  
**Project Type**: Python research and automated-trading control plane  
**Performance Goals**: Complete the focused production probe inside the existing 25-minute workflow timeout  
**Constraints**: No broker call, order submission, capital allocation, margin, whitelist, cap, constitution, or kernel change  
**Scale/Scope**: Preserve 16 options candidates and the existing 752 globally unique research configurations

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1.*

- **Rung 0 exploration**: PASS. The factory remains research-only and cannot request capital.
- **EDGE_CONFIRMED before capital above 20%**: PASS. No capital or promotion state changes.
- **Exact fingerprint identity**: PASS. Existing candidate IDs, hyperparameters, and fingerprints are unchanged; WPUT cannot select a candidate.
- **Missing-evidence failure mode**: PASS. Missing PUT, WPUT, holdout, chronology, forward, hardened-canary, broker, or NAV evidence keeps promotion false.
- **Backtest -> Canary -> Full**: PASS. Historical nested validation does not count as paper, canary, or live evidence.
- **Risk controls and audit logs**: PASS. Existing order authority, caps, reconciliation, idempotency, audit logging, deployment lock, and secret boundaries are untouched.
- **Live-order approval boundary**: PASS. This feature submits no order and grants no order authority.

## Project Structure

### Documentation (this feature)

```text
specs/165-options-selection-objective-repair/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── system-review.md
├── production-result.md
├── contracts/
│   └── options-selection-objective-repair.json.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/
└── options_variance_risk_premium_factory.py

scripts/
└── options_variance_risk_premium_factory_probe.py

tests/
├── unit/test_options_variance_risk_premium_factory.py
└── integration/test_options_variance_risk_premium_factory_probe.py

.github/workflows/
└── autonomous-strategy-factory.yml
```

**Structure Decision**: Amend the released specification 164 factory in place so the same candidates and fingerprints are evaluated under a repaired protocol. A new strategy family would hide the selection defect behind new IDs and would invalidate the controlled comparison.

## Complexity Tracking

No constitution exception is required. The change adds one independent public index and deterministic evaluation layers around the existing candidate set.
