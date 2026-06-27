# Implementation Plan: Strategy Review Observation Health

**Branch**: `Codex/strategy-review-observation-repair` | **Date**: 2026-06-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/066-strategy-review-observation-health/spec.md`

## Summary

Repair the strategy review observation-health gate so the autonomous reassignment loop does not confuse normal pre-minimum observation skew with broken candidate input. The implementation keeps missing verdict and incumbent-missing failures conservative, keeps `lagging_keys` visible, and changes only the read-only leaderboard health classification.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Existing stdlib-only `auto_invest.analytics.forward_tournament` code  
**Storage**: Existing forward verdict JSON files and sidecar markdown; no new storage  
**Testing**: `pytest`, `ruff`  
**Target Platform**: Local tests and GitHub Actions workflow runners  
**Project Type**: Python library plus CLI probe  
**Performance Goals**: Pure in-memory leaderboard classification remains effectively instantaneous.  
**Constraints**: No broker mutation, no live arming, no capital change, no whitelist change, no secret handling change.  
**Scale/Scope**: Seven forward-paper tournament tracks used by strategy review and autonomous reassignment.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Rationale |
|-----------|--------|-----------|
| I. Position sizing and exposure limits | PASS | No order path or exposure limit is changed. |
| II. Deny-by-default whitelist | PASS | No tradable symbol or account allowlist changes. |
| III. Claude judgment points | PASS | No LLM judgment point is added. |
| IV. Append-only audit and reconciliation | PASS | No audit deletion or reconciliation path changes. |
| V. Secret isolation | PASS | The code reads only public verdict JSON fields. |
| VI. Backtest -> Canary -> Full Live | PASS | This repair only clarifies forward-paper evidence; it does not promote a strategy. |
| VII. External API robustness | PASS | No external API call is added. |
| VIII.A. No market-hours deploys | PASS | Deploy restrictions are unchanged. |
| IX. Self-modification boundary | PASS | Kernel safety files are untouched. |
| X. Measurement-driven autonomous growth | PASS | The change improves measured-evidence interpretation and preserves the five-gate reassignment safety model. |

## Project Structure

### Documentation (this feature)

```text
specs/066-strategy-review-observation-health/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/
└── forward_tournament.py

tests/
├── unit/test_forward_tournament.py
└── integration/test_forward_tournament_probe.py
```

**Structure Decision**: Keep the behavior in `forward_tournament.py` because observation health is a leaderboard property consumed by existing reassignment logic. No new module or workflow is needed.

## Complexity Tracking

No constitution violation is required. This is risk grade 2 because it changes autonomous strategy-review classification, but it does not touch the live-money execution surface.
