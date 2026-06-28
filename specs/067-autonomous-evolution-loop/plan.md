# Implementation Plan: Autonomous Evolution Loop

**Branch**: `Codex/autonomous-evolution-loop` | **Date**: 2026-06-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/067-autonomous-evolution-loop/spec.md`

## Summary

Build a read-first permanent autonomous growth loop that continuously compounds profit capacity, evidence quality, capital-path readiness, safety, and learning speed. The loop scans current evidence surfaces, ranks high-leverage breakthrough candidates across the whole operating domain, turns selected candidates into bounded experiments, promotes only evidence-backed improvements through existing gates, and records learning so future sessions do not repeat the same discovery work.

The first implementation slice is intentionally read-only: breakthrough candidate discovery, experiment planning, evidence packaging, latest-run sidecar, and learning ledger. It must not submit orders, increase capital, widen whitelists, relax caps, enable live order mode, or swap live strategies outside the existing reassignment and capital ladder gates.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Existing stdlib/Pydantic/Typer project patterns; existing analytics, sidecar, and CLI helpers
**Storage**: JSON artifacts and markdown summaries in automation sidecars; optional local JSON ledger under generated output paths
**Testing**: `pytest`, `ruff`
**Target Platform**: Local CLI, GitHub Actions runner, and existing automation sidecar branches
**Project Type**: Python CLI plus read-only analytics/reporting workflow
**Performance Goals**: A normal scan over current sidecars and specs completes within one scheduled workflow run under 10 minutes.
**Constraints**: No broker mutation, no live arming, no capital change, no whitelist change, no cap relaxation, no secret exposure, no paid external service call by default.
**Scale/Scope**: At least eight operating domains and the current auto-invest automation surfaces.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Rationale |
|-----------|--------|-----------|
| I. Position sizing and exposure limits | PASS | The loop may identify cap-related candidates, but cannot modify caps or orders. |
| II. Deny-by-default whitelist | PASS | Whitelist expansion is classified as safety-boundary review and not auto-applied. |
| III. Claude judgment points | PASS | First slice is deterministic/read-only. Future LLM use would require a declared judgment point. |
| IV. Append-only audit and reconciliation | PASS | The loop adds durable reports and must not delete audit or sidecar history. |
| V. Secret isolation | PASS | Reports must mask secrets and run without broker secrets in read-only mode. |
| VI. Backtest -> Canary -> Full Live | PASS | Trading improvements are routed into backtest/paper/canary gates before live effect. |
| VII. External API robustness | PASS | First slice uses repository and sidecar evidence; paid or new external calls are review items. |
| VIII.A. No market-hours deploys | PASS | The loop does not deploy live trading code during a scan. Future deploy remains governed by existing workflows. |
| IX. Self-modification boundary | PASS | Kernel or constitution changes are classified as safety-boundary review, not auto-applied by this loop. |
| X. Measurement-driven autonomous growth | PASS | The feature exists to make improvement evidence-driven and to reject thin-sample changes. |

## Project Structure

### Documentation (this feature)

```text
specs/067-autonomous-evolution-loop/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── evolution-loop.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/
├── analytics/
│   ├── evolution_loop.py          # breakthrough discovery, scoring, promotion classification
│   └── pipeline_liveness.py       # existing liveness registry extended with evolution sidecar
├── cli.py                         # planned `evolution-scan` command wiring
└── reports/
    └── evolution.py               # operator-facing markdown/JSON report helpers if shared rendering is needed

scripts/
└── evolution_loop_probe.py         # workflow-friendly manifest, scan, text/json output

.github/workflows/
└── autonomous-evolution-loop.yml   # scheduled read-only scan and sidecar publish

tests/
├── unit/test_evolution_loop.py
├── integration/test_evolution_loop_probe.py
└── unit/test_pipeline_liveness.py
```

**Structure Decision**: Keep the scoring core in `analytics` because it is a read-only decision/reporting engine like money-path and pipeline-liveness. Use a small script for GitHub Actions sidecar collection, and only add CLI wiring once the pure core is covered by tests.

## Complexity Tracking

No constitution violation is required. The implementation will be risk grade 2 because it creates a new autonomous operating workflow and sidecar. It must remain outside grade 4 money-path execution unless a later, separately specified change explicitly asks for live-money behavior.
