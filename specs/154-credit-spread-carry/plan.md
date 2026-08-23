# Implementation Plan: Independent Credit Spread Carry

**Branch**: `Codex/154-credit-spread-carry` | **Date**: 2026-08-23 | **Spec**: [spec.md](spec.md)

## Summary

Collect Treasury HQM 10-year and 20-year corporate rates, generate exactly 64 frozen credit-spread timing
candidates, and evaluate them with the calibrated family-local DSR/PBO plus untouched holdout blend PSR and
economic gates. Preserve 640 global audit trials and publish no-order evidence only.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2, existing NumPy/Pandas, Typer CLI, public-data collector
**Storage**: Public-data CSV, strategy-factory JSON/Markdown, append-only JSONL trial ledger
**Testing**: pytest, ruff, deterministic fixtures, production no-order workflow
**Target Platform**: GitHub Actions research worker and existing Linux worker
**Project Type**: Single Python package with CLI, workflows, configs, and SDD artifacts
**Performance Goals**: Two added series within the 480-second collector budget; 64 candidates within 15 minutes
**Constraints**: Long-only, unlevered, monthly, no future leakage, 1-month embargo, fail closed, no capital/order/whitelist change
**Scale/Scope**: Two corporate maturities, one Treasury defensive sleeve, four grammars, 64 current and 640 audit trials

## Constitution Check

| Principle | Design response | Status |
|---|---|:---:|
| I Position limits | Research moves no money; later orders retain 50% per trade, 60% per symbol, 100% global and 1% cash buffer. | PASS |
| II Deny by default | `LQD` is not added to the active whitelist; a research pass cannot arm live trading. | PASS |
| III Judgment points | Candidate grammar is deterministic and makes no LLM call. | PASS |
| IV Audit and reconciliation | The historical ledger remains append-only and a derived catalog proves 640 unique trials; any later order uses the existing audited route. | PASS |
| V Secret isolation | HQM/FRED collection is keyless and reports contain no account secret. | PASS |
| VI Backtest -> Canary -> Full | A pass is research-canary evidence only; initial eventual share remains NAV 10%. | PASS |
| VII External failure | Missing, stale, malformed, or mismatched evidence fails closed. | PASS |
| VIII.A Market hours | Research and deployment move no capital; existing guard is unchanged. | PASS |
| IX Self modification | Grade-4 full SDD, PR evidence, exact fingerprints, and rollback are required. | PASS |
| X Measured growth | Untouched holdout, costs, blend utility, and calibrated statistics precede promotion. | PASS |

## Project Structure

```text
specs/154-credit-spread-carry/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/credit-spread-evidence.md
├── checklists/requirements.md
└── tasks.md
src/auto_invest/
├── analytics/credit_spread_factory.py
├── config/rules.py
├── execution/rebalancer.py
├── market_data/public_data.py
├── portfolio/autoarm.py
└── strategy/rebalance.py
scripts/credit_spread_factory_probe.py
tests/unit/test_credit_spread_factory.py
tests/integration/test_credit_spread_factory_probe.py
.github/workflows/autonomous-strategy-factory.yml
deploy/public-data.toml
```

**Structure Decision**: Follow the Treasury factory structure, isolate credit data and evaluation in one
analytics module, and place the shared pure target-weight function in the strategy module.

## Implementation Sequence

1. Add HQM collection contracts and point-in-time snapshots.
2. Add the frozen policy model, exact 64-candidate generator, and shared target weights.
3. Add synthetic rolling-par returns, costs, and development-only selection.
4. Add 640-trial audit, family-local diagnostics, holdout confirmation, and blend economics.
5. Add evidence validation, no-order probe, workflow, sidecar, and regression tests.
6. Run full verification, merge, deploy, production replay, KIS smoke, and handoff.

## Rollback

Revert the optional policy, credit analysis/probe/workflow branch, and two extra public series. Existing
Treasury and macro factories remain valid, while `PREVIEW_ONLY`, capital 0, and orders 0 are unchanged.

## Post-Design Constitution Check

All principles still pass. The design can nominate research evidence but cannot widen K2, allocate capital,
or call a broker.
