# Implementation Plan: Candidate Evidence Diagnostics

**Branch**: `Codex/candidate-evidence-diagnostics` | **Date**: 2026-07-01 | **Spec**: `specs/072-candidate-evidence-diagnostics/spec.md`  
**Input**: Feature specification from `specs/072-candidate-evidence-diagnostics/spec.md`

## Summary

Extend the candidate result evidence contract so every pending or blocked package carries a structured diagnostic and safe next action. The result executor will classify failure output into stable diagnostic codes, publish those codes in JSON and Markdown sidecars, and the candidate factory will preserve the same diagnostics in `promotion_evidence` without relaxing pass criteria or advancing money-path stages.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: existing `auto-invest` analytics modules, Typer CLI, pytest, GitHub Actions sidecar workflows  
**Storage**: JSON sidecar artifacts (`candidate_result_executor.json`, `candidate_results.json`, enriched backlog JSON) and Markdown summaries  
**Testing**: pytest unit and integration tests, workflow text checks, ruff, strict agent harness  
**Target Platform**: Local Mac worktrees and GitHub Actions Ubuntu runners  
**Project Type**: CLI + analytics module + automation workflow  
**Performance Goals**: Additive diagnostics should not add external calls; current 9-package executor run remains within existing workflow timeout  
**Constraints**: no broker calls, no orders, no live config edits, no capital scaling, no whitelist/caps changes, no sentinel writes, no raw secret/log leakage  
**Scale/Scope**: Current 9 candidate packages, additive schema that can handle dozens of packages and multiple diagnostics per result

## Constitution Check

- Principles I-II: no position sizing, order placement, or whitelist changes.
- Principle III: no new LLM judgment point.
- Principles IV-V: no audit deletion or secret movement; excerpts remain masked and bounded.
- Principle VI: `Backtest -> Canary -> Full` is preserved; diagnostics do not promote candidates.
- Principle VII: no new external API call path beyond existing validation commands.
- VIII.A/B: workflow remains evidence sidecar only; production deploy remains under existing deploy guard.
- IX: no constitution, kernel manifest, or kernel path change.
- X: improves measurement-driven autonomous growth by making missing evidence explicit before tuning or promotion.

Risk grade: 2. This changes operating evidence flow and handoff context, but does not change the safety perimeter or live money execution.

## Project Structure

### Documentation (this feature)

```text
specs/072-candidate-evidence-diagnostics/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── candidate-evidence-diagnostics.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/analytics/
├── candidate_result_executor.py
├── candidate_factory.py

scripts/
├── candidate_result_executor_probe.py

tests/
├── fixtures/candidate_factory/fresh/
├── integration/test_candidate_result_executor_probe.py
├── unit/test_candidate_result_executor.py
├── unit/test_candidate_factory.py
```

**Structure Decision**: Extend existing spec 070/071 modules in place. A new module would add indirection without reducing risk because diagnostics are part of the existing result evidence contract.

## Phase 0 Research

See `research.md`.

## Phase 1 Design

See `data-model.md`, `contracts/candidate-evidence-diagnostics.md`, and `quickstart.md`.

## Post-Design Constitution Check

The design remains compliant with principles I-X. Diagnostics are additive evidence metadata; they do not execute new commands, alter candidate pass criteria, touch broker paths, change capital, change live strategy, or modify safety perimeter files.

## Complexity Tracking

No constitution violation. The added diagnostic object is justified because the existing one-line pending reason cannot be safely consumed by downstream automation.
