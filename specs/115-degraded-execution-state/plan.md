# Implementation Plan: Degraded Execution State

**Branch**: `codex/115-degraded-execution-state` | **Date**: 2026-07-13 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/115-degraded-execution-state/spec.md`

## Summary

Add a sell-only execution state that blocks new BUY orders whenever account-critical evidence is uncertain. The change is a safety contraction: it adds a gate before broker submission without enabling live trading, changing caps, or replacing the current K1 gate chain.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: SQLite standard library, existing worker and order-router modules  
**Storage**: Existing `orders` and `reconciliation_runs` tables; no new migrations  
**Testing**: `pytest`, `ruff`  
**Target Platform**: Local and deployed auto-invest worker environment  
**Project Type**: Python CLI/service package  
**Performance Goals**: One small DB read per live order route; worker runtime blockers are in-memory  
**Constraints**: No live order execution, no sentinel/capital/whitelist/cap/constitution/kernel changes  
**Scale/Scope**: One worker process and one SQLite account ledger; cross-process locking remains later work

## Constitution Check

| Principle | Result | Notes |
|-----------|--------|-------|
| I. Position Sizing & Exposure Limits | PASS | New BUY eligibility becomes stricter. |
| II. Deny-by-Default | PASS | Unclear state denies BUY by default. |
| III. LLM Judgment Points | PASS | No LLM call sites. |
| IV. Append-Only Audit + Reconciliation | PASS | Uses existing audit and reconciliation tables; no mutation of append-only records. |
| V. Secret Isolation | PASS | No secret handling. |
| VI. Backtest -> Canary -> Full | PASS | No rollout-stage change. |
| VII. External API Robustness | PASS | Failed critical reads degrade BUY instead of being ignored. |
| VIII.A Market-Hours Deploy Guard | PASS | No deploy workflow change. |
| IX. Self-Modification Boundary | PASS | Safety boundary tightens; kernel and constitution remain unchanged. |
| X. Measurement-Driven Growth | PASS | Validation is test and audit based; no live money action. |

Post-design check: PASS. The design blocks exposure-increasing orders under uncertainty and preserves exits.

## Project Structure

### Documentation

```text
specs/115-degraded-execution-state/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── degraded-execution-state.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/execution/
├── execution_state.py
└── order_router.py

src/auto_invest/worker/
└── loop.py

tests/
├── unit/test_execution_state.py
└── integration/
    ├── test_order_router.py
    ├── test_worker_fill_sync.py
    └── test_worker_capital_tracking.py
```

**Structure Decision**: Keep the state evaluator in `execution/` because it is an execution-safety calculation over order and reconciliation evidence, not a persistence model or a portfolio strategy.

## Complexity Tracking

No constitution violations or architectural escalation are required. Cross-process locks and a central execution authority stay out of scope.
