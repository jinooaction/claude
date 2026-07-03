# Implementation Plan: Autonomous Macro Growth Discovery

**Branch**: `Codex/088-autonomous-macro-growth-discovery` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/088-autonomous-macro-growth-discovery/spec.md`

## Summary

Add a deterministic macro-growth synthesis layer to the autonomous work execution loop. When all normal work packets are closed as released or suppressed and no recovery or approval work is pending, the loop emits a read-only agent-ops candidate that tells Codex to expand the autonomous growth system itself. The bootstrap candidate is skipped once released, allowing the next macro candidate to become the next autonomous task.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Existing standard-library JSON/dataclass code, existing released-work scanner, existing Typer/probe wrappers
**Storage**: Existing GitHub automation sidecar branches and Speckit contracts; no database or new service
**Testing**: pytest, ruff
**Target Platform**: Local repo and GitHub Actions runner
**Project Type**: Python CLI/analytics library plus GitHub Actions workflow
**Performance Goals**: Macro synthesis adds under 1 second for the current work packet set
**Constraints**: Read-only evidence consumption; no broker, order, capital, whitelist, caps, live strategy, secret, constitution, or kernel changes
**Scale/Scope**: Current autonomous work packet set and a short ordered macro candidate backlog

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Reason |
|-----------|--------|--------|
| I. Position sizing and exposure limits | PASS | No orders, sizing, or exposure paths touched. |
| II. Deny-by-default whitelist | PASS | No universe or whitelist change. |
| III. Claude judgment points | PASS | No LLM call sites added. |
| IV. Append-only audit and reconciliation | PASS | Existing sidecars remain evidence surfaces; no audit deletion. |
| V. Secret isolation | PASS | Reads only existing sidecar text/JSON and uses existing masking paths. |
| VI. Backtest -> Canary -> Full | PASS | Does not promote strategies, canaries, capital, or live readiness. |
| VII. External API robustness | PASS | No external API calls added. |
| VIII.A No live deploys during market hours | PASS | No live deploy path changed. |
| IX/X self-modification and autonomous growth | PASS | Improves autonomous growth task selection inside the safety perimeter; no kernel or constitution touch. |

## Project Structure

### Documentation (this feature)

```text
specs/088-autonomous-macro-growth-discovery/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── autonomous-macro-growth-discovery.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/autonomous_work_execution.py
scripts/autonomous_work_execution_probe.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_autonomous_work_execution_probe.py
specs/088-autonomous-macro-growth-discovery/contracts/autonomous-macro-growth-discovery.md
.specify/feature.json
CLAUDE.md
```

**Structure Decision**: Extend the existing spec 077 autonomous work execution loop because it is the point where released-work, learning-ledger, capital-path, pipeline, and candidate evidence are already reconciled into a single next-work decision.

## Complexity Tracking

No constitution or architecture violations.

## Post-Design Constitution Check

PASS. The design remains read-only, deterministic, and limited to work packet selection. It removes no existing recovery, approval, or safety guard behavior.
