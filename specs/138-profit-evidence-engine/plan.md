# Implementation Plan: Profit Evidence Engine

**Branch**: `codex/profit-engine-redesign` | **Date**: 2026-08-16 | **Spec**: `specs/138-profit-evidence-engine/spec.md`

## Summary

Replace the contract-only no-edge loop with a deterministic research engine that compiles pre-registered deployable portfolio variants into one temporally held-out profit candidate. Preserve long-history and recent evidence separately, route mixed evidence to forward validation, and add the missing `globalfixed` history path. No live gate is weakened.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Python standard library and existing `auto_invest.analytics` factor/statistics modules
**Storage**: JSON/Markdown automation sidecars and read-only history exports
**Testing**: pytest, ruff
**Target Platform**: GitHub Actions Linux runner and local macOS development
**Project Type**: Python library plus CLI probes and scheduled workflow
**Performance Goals**: Evaluate 12 monthly candidates over 55+ years in under 10 seconds after data download
**Constraints**: Deterministic; no broker call; no order; no capital/live config/whitelist/caps/secret/constitution/kernel change
**Scale/Scope**: 3 allocation families x 4 trend windows, one fixed holdout, one forward leaderboard row

## Constitution Check

- **Risk grade**: 4 because the output is intended to feed the money path, even though this implementation is research-only and cannot submit orders.
- **I Position limits / II whitelist**: unchanged; candidate universes are already-existing paper portfolios and this feature performs no allocation.
- **III Circuit breaker / IV audit / V secrets**: untouched; workflow produces append-only sidecar evidence and reads no secret values.
- **VI Backtest -> Canary -> Full**: strengthened. Historical holdout is only a research gate; current forward PSR and existing hardened canary remain mandatory before live reassignment.
- **VIII.A market hours**: irrelevant to the no-live workflow; no deployment or order path is invoked.
- **IX kernel / safety perimeter**: no kernel or constitution file changes.
- **X measured growth**: directly satisfied by converting measured evidence into an executable, reproducible candidate rather than prose lanes.

All gates pass. No constitutional exception is required.

## Phase 0 Research

- Confirmed current root failure: contract candidates are completed without compiling a concrete strategy; mixed long/recent evidence is collapsed to one failure; `globalfixed` is absent from candidate history support.
- Use the existing 1971+ Shiller/gold data route and portfolio factor implementations to avoid introducing a second metric engine.
- Use a fixed 2007 holdout rather than choosing a split after seeing results.
- Search only 12 pre-registered variants and report the trial count. Selection happens on pre-2007 data; the holdout is evaluated once.
- Charge 50bp annual drag before selection and evaluation.
- Require a neighborhood test around the selected trend window.

## Phase 1 Design

- Add `src/auto_invest/analytics/profit_evidence_engine.py` for pure candidate generation, temporal split, conservative cost drag, deterministic development selection, holdout gates, neighbor robustness, and forward evidence fusion.
- Add `scripts/profit_evidence_engine_probe.py` for public-data loading and optional leaderboard input.
- Refactor `candidate_result_executor.py` so each validation command maps to a distinct evidence axis and mixed evidence becomes pending.
- Add `global-trend-fixed` to `candidate_history_support.py` and the workflow export allowlist.
- Add `.github/workflows/profit-evidence-engine.yml` to publish the no-live sidecar on schedule and manual dispatch.
- Add focused unit/integration/workflow contract tests.

## Post-Design Constitution Check

The designed output can say `HOLDOUT_EDGE` or `FORWARD_VALIDATION`, but it cannot say `EDGE_CONFIRMED`, arm a sentinel, change the strategy, allocate capital, or invoke a broker. Existing forward multiplicity correction, hardened canary, fingerprint matching, rung reset, caps, whitelist, and drawdown budget remain the only promotion path. Constitution checks remain passed.

## Project Structure

```text
src/auto_invest/analytics/
├── profit_evidence_engine.py
├── candidate_result_executor.py
└── candidate_history_support.py
scripts/
└── profit_evidence_engine_probe.py
.github/workflows/
├── candidate-result-executor.yml
└── profit-evidence-engine.yml
tests/
├── unit/test_profit_evidence_engine.py
├── unit/test_candidate_result_executor.py
├── unit/test_candidate_history_support.py
└── integration/test_profit_evidence_engine_probe.py
specs/138-profit-evidence-engine/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/profit-evidence.schema.json
└── tasks.md
```

**Structure Decision**: Reuse the existing analytics/probe/sidecar pattern and patch only the two broken bridge modules. No new service or dependency is introduced.

## Complexity Tracking

No constitutional violations or unjustified abstractions.
