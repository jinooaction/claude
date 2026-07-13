# Implementation Plan: Account Exposure Reservation

**Branch**: `Codex/114-account-exposure-reservation` | **Date**: 2026-07-13 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/114-account-exposure-reservation/spec.md`

## Summary

Tighten K1 exposure enforcement so current positions, already-open BUY orders, and in-run BUY reservations are evaluated together. The change preserves the existing risk gates and feeds them stricter exposure numbers.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: SQLite standard library, existing `auto_invest` execution and persistence modules  
**Storage**: Existing SQLite `orders`, `order_state_history`, and `current_positions` tables  
**Testing**: `pytest`, `ruff`  
**Target Platform**: Local and deployed auto-invest worker environment  
**Project Type**: Python CLI/service package  
**Performance Goals**: Reservation query remains small and deterministic for normal open-order counts  
**Constraints**: No live order execution, no capital/sentinel/whitelist change, no constitution/kernel manifest change  
**Scale/Scope**: One account's open order ledger and one rebalance order bundle at a time

## Constitution Check

| Principle | Result | Notes |
|-----------|--------|-------|
| I. Position Sizing & Exposure Limits | PASS | Inputs become more conservative; gates remain binding. |
| II. Deny-by-Default | PASS | No whitelist expansion. |
| III. LLM Judgment Points | PASS | No LLM call sites. |
| IV. Append-Only Audit + Reconciliation | PASS | Reads existing orders; does not weaken append-only audit. |
| V. Secret Isolation | PASS | No secret handling. |
| VI. Backtest -> Canary -> Full | PASS | No rollout-stage change. |
| VII. External API Robustness | PASS | No new external API calls. |
| VIII.A Market-Hours Deploy Guard | PASS | No deploy workflow change. |
| IX. Self-Modification Boundary | PASS | K1 safety surface is tightened; constitution and kernel manifest unchanged. |
| X. Measurement-Driven Growth | PASS | Deploy remains separate from live money. |

Post-design check: PASS. The design is a safety contraction and introduces no new money-moving path.

## Project Structure

### Documentation

```text
specs/114-account-exposure-reservation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── exposure-reservation.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/execution/
├── exposure_reservation.py
├── order_router.py
└── rebalancer.py

tests/integration/
├── test_order_router.py
└── test_spec_032_live_rebalancer.py
```

**Structure Decision**: Keep reservation logic in execution rather than persistence because it is an execution-safety calculation over existing tables, not a new durable model.

## Complexity Tracking

No constitution violations or new architectural complexity are required.
