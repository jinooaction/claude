# Implementation Plan: Evolution Source Diversification

**Branch**: `Codex/089-evolution-source-diversification` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/089-evolution-source-diversification/spec.md`

## Summary

Extend the autonomous evolution loop so the upstream candidate backlog can create deterministic evidence-derived candidates after the fixed candidate set is closed by learning ledger and released-work history. The first synthesized candidate turns the current `candidate-evolution-source-diversification` macro work into an actual upstream backlog entry, using only read-only sidecar and ledger evidence.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Existing standard-library JSON/dataclass code, existing evolution loop probe, existing released-work scanner
**Storage**: Existing GitHub automation sidecar branches and Speckit contracts; no database or new service
**Testing**: pytest, ruff
**Target Platform**: Local repo and GitHub Actions runner
**Project Type**: Python CLI/analytics library plus GitHub Actions workflow
**Performance Goals**: Candidate synthesis adds under 1 second for the current sidecar set
**Constraints**: Read-only evidence consumption; no broker, order, capital, whitelist, caps, live strategy, secret, constitution, or kernel changes
**Scale/Scope**: Current autonomous evolution candidate set, learning ledger, promotion failure signals, pipeline liveness, released-work, and capital-path observability inputs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Reason |
|-----------|--------|--------|
| I. Position sizing and exposure limits | PASS | No order sizing or exposure path touched. |
| II. Deny-by-default whitelist | PASS | No trading universe or whitelist change. |
| III. Claude judgment points | PASS | No LLM call sites or judgment-point costs added. |
| IV. Append-only audit and reconciliation | PASS | Existing sidecars remain evidence surfaces; no audit mutation. |
| V. Secret isolation | PASS | Reads existing sidecar text/JSON and keeps existing masking behavior. |
| VI. Backtest -> Canary -> Full | PASS | Does not promote strategies, canaries, capital, or live readiness. |
| VII. External API robustness | PASS | No external API calls added. |
| VIII.A No live deploys during market hours | PASS | No live deploy path changed. |
| IX/X self-modification and autonomous growth | PASS | Improves autonomous growth candidate generation inside the safety perimeter; no kernel or constitution touch. |

## Project Structure

### Documentation (this feature)

```text
specs/089-evolution-source-diversification/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── evolution-source-diversification.md
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
specs/089-evolution-source-diversification/contracts/evolution-source-diversification.md
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Extend the existing spec 067 autonomous evolution loop because it is the upstream source for candidate backlog, learning ledger, and downstream autonomous work execution.

## Complexity Tracking

No constitution or architecture violations.

## Post-Design Constitution Check

PASS. The design remains read-only, deterministic, and limited to candidate backlog generation. It removes no existing ledger, promotion, recovery, approval, or safety guard behavior.
