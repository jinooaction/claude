# Implementation Plan: Edge Gate Calibration

**Branch**: `Codex/153-edge-gate-calibration` | **Date**: 2026-08-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/153-edge-gate-calibration/spec.md`

## Summary

Replace the heterogeneous 576-row DSR/PBO calculation and holdout winner selection with a
calibrated hierarchy: family-local effective-trial DSR and PBO diagnostics on development data, one frozen
candidate on embargoed holdout data, and a preregistered replacement or diversifier economic route.
Keep the 576-trial append-only audit history and all live-money gates unchanged.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: NumPy, existing analytics and backtest modules  
**Storage**: JSON/JSONL sidecar evidence and existing append-only trial ledger  
**Testing**: pytest, ruff, deterministic Monte Carlo calibration  
**Target Platform**: Linux GitHub Actions worker and production macOS/Linux operator tooling  
**Project Type**: Python CLI and scheduled workflow  
**Performance Goals**: 200-repetition calibration under 60 seconds; factory under 15 minutes  
**Constraints**: no broker call, order, capital, whitelist, cap, secret, constitution, or kernel change  
**Scale/Scope**: 64-current-family trials plus 512 historical audit trials

## Constitution Check

- **I-II Position caps and whitelist**: unchanged; revised output stops at research eligibility.
- **III Judgment points**: no LLM trading judgment is added.
- **IV Audit log**: all 576 historical trials remain append-only and separately reported.
- **V Secrets**: no new secret or paid source.
- **VI Staged rollout**: `Backtest -> Canary -> Full` remains mandatory; no direct live transition.
- **VII External APIs**: unchanged.
- **VIII.A Market-hours deployment**: existing deployment guard remains mandatory.
- **IX-X Safety and money path**: exact decision version and fingerprints fail closed; rung 0, capital 0,
  and order 0 remain until separate promotion evidence exists.

Post-design check: pass. The design narrows invalid statistical inputs without weakening execution safety.

## Project Structure

```text
specs/153-edge-gate-calibration/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/edge-gate-evidence.md
└── tasks.md

src/auto_invest/analytics/
├── backtest_overfitting.py
├── edge_gate_calibration.py
└── treasury_carry_factory.py

scripts/
├── edge_gate_calibration_probe.py
└── treasury_carry_factory_probe.py

tests/unit/
├── test_backtest_overfitting.py
├── test_edge_gate_calibration.py
└── test_treasury_carry_factory.py

tests/integration/
├── test_edge_gate_calibration_probe.py
└── test_treasury_carry_factory_probe.py
```

**Structure Decision**: Extend the existing analytics, probe, workflow, and sidecar patterns. No new service or database.

## Complexity Tracking

No constitutional violation or new runtime subsystem.
