# Implementation Plan: Learning Ledger Candidate Memory

**Branch**: `Codex/087-learning-ledger-candidate-memory` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/087-learning-ledger-candidate-memory/spec.md`

## Summary

Teach the autonomous evolution loop to apply existing learning ledger decisions beyond rejected entries. Evidence-dependent, deferred, and operator-review ledger decisions should make matching candidates non-actionable before `safe_high_leverage_work` is computed. This turns the learning ledger from a passive record into a durable memory surface that prevents repeated rediscovery of held or review-gated candidates.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Existing standard-library JSON/dataclass code, existing Typer CLI/probe wrappers, GitHub Actions sidecar publishing
**Storage**: Existing JSON sidecars on automation branches; no database or new persistent service
**Testing**: pytest, ruff
**Target Platform**: Local repo and GitHub Actions runner
**Project Type**: Python CLI/analytics library plus GitHub Actions workflow
**Performance Goals**: Apply ledger decisions across the current candidate set in under 1 second; no network calls inside the probe
**Constraints**: Read-only evidence consumption; no broker, order, capital, whitelist, caps, live strategy, secret, constitution, or kernel changes
**Scale/Scope**: Current autonomous candidate set and future learning ledger entries; expected tens of candidates, not thousands

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Reason |
|-----------|--------|--------|
| I. Position sizing and exposure limits | PASS | No orders or sizing path touched. |
| II. Deny-by-default whitelist | PASS | No universe or whitelist change. |
| III. Claude judgment points | PASS | No LLM call sites added. |
| IV. Append-only audit and reconciliation | PASS | Existing generated sidecars remain the evidence surface; no audit deletion. |
| V. Secret isolation | PASS | Reads existing JSON and uses existing masking for candidate text. |
| VI. Backtest -> Canary -> Full | PASS | Does not promote strategies, forward tracks, canaries, or live readiness. |
| VII. External API robustness | PASS | No external API calls added. |
| VIII.A No live deploys during market hours | PASS | Deploy remains existing guarded dry-run deploy; no live money deploy. |
| IX/X self-modification and autonomous growth | PASS | Improves autonomous learning loop inside safety perimeter; no kernel or constitution touch. |

## Project Structure

### Documentation (this feature)

```text
specs/087-learning-ledger-candidate-memory/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── learning-ledger-candidate-memory.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/evolution_loop.py
scripts/evolution_loop_probe.py
tests/unit/test_evolution_loop.py
tests/integration/test_evolution_loop_probe.py
specs/087-learning-ledger-candidate-memory/contracts/learning-ledger-candidate-memory.md
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Extend the existing spec 067 evolution loop and spec 075 learning-ledger behavior. The ledger already exists; the missing behavior is applying hold/review decisions to generated candidates, not adding a second memory file.

## Complexity Tracking

No constitution or architecture violations.
