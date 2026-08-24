# Implementation Plan: Independent Commodity Term Structure

**Branch**: `Codex/156-commodity-term-structure` | **Date**: 2026-08-25 | **Spec**: [spec.md](spec.md)

## Summary

Parse official BlackRock JSON and World Bank XLSX without adding a runtime spreadsheet dependency, generate
16 lagged long-only GSG/cash candidates, select once on development, and evaluate the untouched holdout with
the existing calibrated gate and incumbent blend tests.

## Technical Context

**Language**: Python 3.11  
**Dependencies**: standard-library ZIP/XML, NumPy, existing analytics, httpx  
**Artifacts**: factory JSON/Markdown, append-only ledger, derived 672-record audit catalog  
**Constraints**: no raw licensed-series publication, no capital/order/whitelist change, one-month signal lag

## Constitution Check

| Principle | Design response | Status |
|---|---|:---:|
| I-II Limits and deny-by-default | Long-only research; GSG is not whitelisted. | PASS |
| III Determinism | Candidate generation and verdict use no LLM call. | PASS |
| IV Audit | Preserve 656 records and add 16 immutable fingerprints. | PASS |
| V Secrets | Both primary sources are keyless. | PASS |
| VI Staging | Passing evidence still requires Backtest -> Canary -> Full. | PASS |
| VII External failure | Source/schema/freshness mismatch fails closed. | PASS |
| VIII.A Market hours | Research and deployment submit no order. | PASS |
| IX Self modification | Full grade-4 SDD, tests, PR, rollback, and replay. | PASS |
| X Measured growth | Holdout, costs, power, and blend utility precede promotion. | PASS |

## Project Structure

```text
specs/156-commodity-term-structure/
src/auto_invest/analytics/commodity_term_structure_factory.py
scripts/commodity_term_structure_factory_probe.py
tests/unit/test_commodity_term_structure_factory.py
tests/integration/test_commodity_term_structure_factory_probe.py
.github/workflows/autonomous-strategy-factory.yml
```

## Sequence

1. Implement source parsers and point-in-time alignment.
2. Implement the 16 frozen candidates, cost model, split, and development-only selection.
3. Reuse calibrated gate evidence and incumbent blend helpers; emit auditable tiered verdicts.
4. Add probe, workflow/ledger/sidecar integration, tests, and immediate production replay.
5. Merge, deploy, verify no-order state, and refresh handoff.

## Rollback

Revert the commodity module, probe, workflow step, and spec pointer. Existing FX and prior factory artifacts
remain readable; capital, orders, whitelist, constitution, and kernel never change.

