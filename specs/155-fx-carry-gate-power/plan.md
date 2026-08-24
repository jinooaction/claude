# Implementation Plan: Independent FX Carry and Gate Power

**Branch**: `Codex/155-fx-carry-gate-power` | **Date**: 2026-08-24 | **Spec**: [spec.md](spec.md)

## Summary

Collect four Federal Reserve H.10 currency pairs and five OECD immediate-rate series through FRED,
generate 16 frozen long-only FX carry candidates, and evaluate them with family-local statistics and an
untouched holdout. Extend calibration from one planted effect to a power curve and add a no-capital paper
challenger tier without weakening the live 0.95 gate.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2, NumPy, existing analytics and public-data collector, Typer CLI
**Storage**: Public-data CSV, factory JSON/Markdown, append-only JSONL ledger and derived audit catalog
**Testing**: pytest, ruff, deterministic synthetic fixtures, live public-data no-order replay
**Target Platform**: GitHub Actions research worker and existing Linux deployment worker
**Performance Goals**: Nine added series within the 480-second collection budget; calibration plus 16 candidates within 15 minutes
**Constraints**: Long-only, unlevered, monthly, prior-month information only, one-month embargo, no capital/order/whitelist change
**Scale/Scope**: Four foreign currencies plus USD, four grammars, 16 current candidates, 656 global audit records

## Constitution Check

| Principle | Design response | Status |
|---|---|:---:|
| I Position limits | Research and paper tiers move no money; any later canary retains all caps and the 1% cash buffer. | PASS |
| II Deny by default | Currency ETF representatives are not added to the active whitelist. | PASS |
| III Judgment points | Candidate generation and classification are deterministic and use no LLM call. | PASS |
| IV Audit and reconciliation | Prior 640 records remain immutable; a derived 656-record catalog proves uniqueness. | PASS |
| V Secret isolation | FRED collection is keyless and emits no account secret. | PASS |
| VI Backtest -> Canary -> Full | `PAPER_CHALLENGER` is pre-canary and capital-free; `FACTORY_EDGE` is still only research-canary evidence. | PASS |
| VII External failure | Missing, stale, malformed, inverse-zero, or mismatched evidence fails closed. | PASS |
| VIII.A Market hours | Research, paper classification, and deployment move no capital. | PASS |
| IX Self modification | Grade-4 full SDD, exact fingerprints, PR evidence, rollback, and post-merge replay are required. | PASS |
| X Measured growth | Gate power, untouched holdout, costs, and account blend utility precede any promotion. | PASS |

## Project Structure

```text
specs/155-fx-carry-gate-power/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/fx-carry-evidence.md
├── checklists/requirements.md
└── tasks.md
src/auto_invest/
├── analytics/edge_gate_calibration.py
├── analytics/fx_carry_factory.py
├── config/rules.py
├── execution/rebalancer.py
├── portfolio/autoarm.py
└── strategy/rebalance.py
scripts/fx_carry_factory_probe.py
tests/unit/test_fx_carry_factory.py
tests/integration/test_fx_carry_factory_probe.py
.github/workflows/autonomous-strategy-factory.yml
deploy/public-data.toml
```

**Structure Decision**: Follow the credit factory shape, keep point-in-time FX data and evaluation in one
analytics module, and reuse one pure target-weight function in research and optional order preparation.

## Implementation Sequence

1. Add FRED source contracts and point-in-time FX snapshots.
2. Add the 16-candidate policy grammar and shared target weights.
3. Add unlevered foreign-cash returns, costs, development-only selection, and untouched holdout economics.
4. Extend deterministic gate calibration with family-size power curves and validate both live and paper tiers.
5. Add 656-record audit, evidence validation, no-order probe, workflow, sidecar, and regression tests.
6. Run local and production backtests, merge, deploy, verify KIS no-order state, and refresh handoff.

## Rollback

Revert the optional FX policy, FX analysis/probe/workflow additions, power-curve fields, and nine public series.
Existing price, macro, Treasury, and credit results remain readable; `PREVIEW_ONLY`, capital 0, and orders 0
remain unchanged.

## Post-Design Constitution Check

All principles pass. The paper tier increases evidence collection, not capital authority, and live eligibility
still requires every existing 0.95 and economic gate.
