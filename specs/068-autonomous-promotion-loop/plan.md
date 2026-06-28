# Implementation Plan: Autonomous Promotion Loop

**Branch**: `Codex/autonomous-promotion-loop` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/068-autonomous-promotion-loop/spec.md`

## Summary

Build a read-only autonomous promotion loop that consumes the autonomous evolution candidate backlog and existing sidecars, classifies each candidate into the next verification stage, explains why backtest evidence and small live canary evidence solve different problems, and publishes a sidecar so future sessions can see the current promotion queue.

The first slice does not register new paper tracks or touch live configuration. It creates the promotion brain, CLI/probe, scheduled workflow, and liveness registration. Existing spec 050 capital ladder and spec 055 reassignment remain the only paths to money effects.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Existing stdlib/Pydantic/Typer project patterns; existing analytics and sidecar helpers  
**Storage**: JSON and Markdown sidecar artifacts under `automation/autonomous-promotion-last-run`  
**Testing**: `pytest`, `ruff`  
**Target Platform**: Local CLI and GitHub Actions runner  
**Project Type**: Python CLI plus read-only analytics/reporting workflow  
**Performance Goals**: Promotion scan completes within 10 minutes in GitHub Actions.  
**Constraints**: No broker calls, no secrets, no orders, no capital change, no whitelist/caps change, no live strategy swap, no sentinels changed.  
**Scale/Scope**: Current autonomous-evolution candidate backlog and existing money-path/reassign/forward sidecars.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Rationale |
|-----------|--------|-----------|
| I. Position sizing and exposure limits | PASS | No orders or cap changes; cap-related candidates are operator review or existing gate only. |
| II. Deny-by-default whitelist | PASS | Whitelist expansion is never applied by this loop. |
| III. Claude judgment points | PASS | First slice is deterministic/read-only, no LLM call path. |
| IV. Append-only audit and reconciliation | PASS | Adds sidecar reports and does not delete audit or mutate broker state. |
| V. Secret isolation | PASS | Runs without secrets and masks secret-like output. |
| VI. Backtest -> Canary -> Full Live | PASS | Explicitly separates backtest, forward, small live canary, and capital ladder gates. |
| VII. External API robustness | PASS | No new external API or broker call in this slice. |
| VIII.A. No market-hours deploys | PASS | No live deploy behavior is changed. |
| IX. Self-modification boundary | PASS | Kernel/safety-boundary candidates are classified, not applied. |
| X. Measurement-driven autonomous growth | PASS | Turns growth candidates into measured promotion stages without bypassing evidence gates. |

## Project Structure

### Documentation (this feature)

```text
specs/068-autonomous-promotion-loop/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── promotion-loop.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/
├── analytics/
│   ├── promotion_loop.py
│   └── pipeline_liveness.py
└── cli.py

scripts/
└── promotion_loop_probe.py

.github/workflows/
└── autonomous-promotion-loop.yml

tests/
├── fixtures/promotion_loop/
├── unit/test_promotion_loop.py
├── integration/test_promotion_loop_probe.py
└── unit/test_pipeline_liveness.py
```

**Structure Decision**: Keep promotion classification in `analytics` because it is a pure decision/reporting layer. Use a small probe script for workflow collection and sidecar publishing. Keep liveness as a registry addition.

## Complexity Tracking

No constitution violation is required. Risk grade 2 applies because this adds an autonomous operating workflow and sidecar. It must not become a parallel money path.
