# Implementation Plan: Money Path State Guard

**Branch**: `Codex/money-path-state-guard` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/062-money-path-state/spec.md`

## Summary

Extend the existing read-only money-path status surface so it cannot miss an operator-approved micro GTAA real-money path. The report will consume the micro GTAA arming sentinel and latest sidecar, place the live-money state above the older first-capital ladder stage, and test that `armed:true` is surfaced as a real-order-capable path subject to preflight and safety gates.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Standard library, existing `auto_invest.analytics.money_path` and `scripts/money_path_probe.py`  
**Storage**: Git-tracked sentinel files and generated sidecar markdown; no database writes  
**Testing**: `pytest`, `ruff`  
**Target Platform**: Local development and GitHub Actions money-path workflow  
**Project Type**: Python command-line reporting inside an automated trading repository  
**Performance Goals**: Status generation remains a small local parse and completes within the existing 8 minute workflow timeout  
**Constraints**: Read-only; no broker calls, no secrets, no order dispatch, no capital changes  
**Scale/Scope**: One existing money-path report, one micro GTAA sentinel, one micro GTAA sidecar

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|-----------|-------|--------|
| I. Position sizing | Does not change caps or order sizing. | PASS |
| II. Deny-by-default | Does not change whitelist or allowed sessions. | PASS |
| III. Judgment points | No LLM call path is added. | PASS |
| IV. Append-only audit | Reads sidecar evidence only; does not mutate audit logs. | PASS |
| V. Secret isolation | No secret reads or outbound transmission. | PASS |
| VI. Staged rollout | Reports micro canary state; does not promote or reassign capital. | PASS |
| VII. External API robustness | No external API calls. | PASS |
| VIII.A. Market-hours deploy guard | Does not alter deploy behavior. | PASS |
| IX. Self-modification boundary | No kernel files or constitution files modified. | PASS |
| X. Measurement-driven growth | Preserves deploy != live money distinction and makes delegated micro live state explicit. | PASS |

Risk classification: **Grade 2 operational-system change**, money-path adjacent but read-only. It adds reporting and validation only; no grade 4 execution is performed.

## Project Structure

### Documentation (this feature)

```text
specs/062-money-path-state/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── live-money-state.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/money_path.py
scripts/money_path_probe.py
.github/workflows/money-path.yml
tests/unit/test_money_path.py
tests/integration/test_money_path_probe.py
HANDOFF.md
```

**Structure Decision**: Extend the existing `money_path` report rather than creating a parallel status file. The incident happened because there were too many surfaces; adding another separate entry point would repeat the same failure mode.

## Complexity Tracking

No constitutional or architectural violation.

## Phase 0: Research

See [research.md](./research.md).

## Phase 1: Design

See [data-model.md](./data-model.md), [contracts/live-money-state.md](./contracts/live-money-state.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

The design remains read-only and does not touch order routing, preflight, broker access, secrets, caps, whitelist, audit schema, or deploy guards. PASS.
