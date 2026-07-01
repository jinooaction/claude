# Implementation Plan: Strategy Failure Learning

**Branch**: `Codex/075-strategy-failure-learning` | **Date**: 2026-07-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/075-strategy-failure-learning/spec.md`

## Summary

Teach the autonomous evolution loop to consume the latest autonomous promotion summary and persist `DISCARD` strategy/portfolio decisions into `learning_ledger.json` as `rejected` entries. This closes the loop after spec 074 and PR #426: once a strategy candidate has real history and still fails, the system remembers that failure and stops reintroducing the same candidate without new evidence.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Existing standard-library JSON/dataclass code, Typer CLI via existing commands, GitHub Actions sidecar publishing  
**Storage**: Existing JSON sidecars on automation branches; no database or new persistent service  
**Testing**: pytest, ruff  
**Target Platform**: Local repo and GitHub Actions runner  
**Project Type**: Python CLI/analytics library plus GitHub Actions workflow  
**Performance Goals**: Parse one small promotion summary JSON in under 1 second; no network calls inside the probe  
**Constraints**: Read-only evidence consumption; no broker, order, capital, whitelist, caps, live strategy, secret, constitution, or kernel changes  
**Scale/Scope**: Current autonomous candidate set and future promotion summary assessments; expected tens of candidates, not thousands

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Reason |
|-----------|--------|--------|
| I. Position sizing and exposure limits | PASS | No orders or sizing path touched. |
| II. Deny-by-default whitelist | PASS | No universe or whitelist change. |
| III. Claude judgment points | PASS | No LLM call sites added. |
| IV. Append-only audit and reconciliation | PASS | Existing sidecars remain append/force-published generated evidence; no audit deletion. |
| V. Secret isolation | PASS | Reads only existing sidecar text/JSON and keeps existing masking behavior. |
| VI. Backtest -> Canary -> Full | PASS | Failed backtests are recorded as rejected; no forward/canary/live promotion. |
| VII. External API robustness | PASS | No external API calls added. |
| VIII.A No live deploys during market hours | PASS | Code deploy remains existing guarded dry-run deploy; no live money deploy. |
| IX/X self-modification and autonomous growth | PASS | Improves learning loop inside safety perimeter; no kernel or constitution touch. |

## Project Structure

### Documentation (this feature)

```text
specs/075-strategy-failure-learning/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── strategy-failure-learning.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/evolution_loop.py
scripts/evolution_loop_probe.py
.github/workflows/autonomous-evolution-loop.yml
tests/unit/test_evolution_loop.py
tests/integration/test_evolution_loop_probe.py
```

**Structure Decision**: Extend the existing spec 067 evolution loop instead of creating a new loop. The learning ledger already lives there, and the missing behavior is a sidecar input and merge rule.

## Complexity Tracking

No constitution or architecture violations.
