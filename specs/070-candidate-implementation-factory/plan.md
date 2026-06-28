# Implementation Plan: Candidate Implementation Factory

**Branch**: `Codex/candidate-implementation-factory` | **Date**: 2026-06-29 | **Spec**: `specs/070-candidate-implementation-factory/spec.md`
**Input**: Feature specification from `specs/070-candidate-implementation-factory/spec.md`

## Summary

Build a deterministic factory between autonomous evolution and autonomous promotion. It converts every candidate into a candidate-specific implementation package, merges machine-readable validation results into `promotion_evidence`, publishes sidecar artifacts, and lets the promotion scan consume the enriched backlog before falling back to the raw evolution backlog.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Typer, pytest, GitHub Actions, existing `auto-invest` CLI surfaces  
**Storage**: JSON sidecar branch only; no database writes  
**Testing**: pytest unit/integration tests, workflow text regressions, ruff  
**Target Platform**: Local Mac and GitHub Actions Ubuntu runner  
**Project Type**: CLI + automation workflow  
**Performance Goals**: Factory run completes in under one minute for normal candidate backlog size  
**Constraints**: no broker calls, no orders, no live config edits, no capital scaling, no whitelist/caps changes  
**Scale/Scope**: Current 9 candidates, designed for dozens

## Constitution Check

- Principles I-VII: no live order, no audit deletion, no secret movement, no broker side effects.
- VIII.A: workflow publishes evidence, not hidden state.
- IX: autonomous progression is improved by reducing manual handoff.
- X: `Backtest -> Canary -> Full` remains intact; factory can only fill strategy evidence from machine results and cannot skip forward/canary gates.

Risk grade: 2. This changes an automation workflow and agent-visible system behavior, but not safety perimeter or live money execution.

## Project Structure

```text
src/auto_invest/analytics/
├── candidate_factory.py
├── pipeline_liveness.py
├── promotion_loop.py

scripts/
├── candidate_factory_probe.py

.github/workflows/
├── candidate-implementation-factory.yml
├── autonomous-promotion-loop.yml

tests/
├── fixtures/candidate_factory/fresh/
├── integration/test_candidate_factory_probe.py
├── unit/test_candidate_factory.py
├── unit/test_pipeline_liveness.py
├── unit/test_safety_command_registry.py
```

## Safety Strategy

- The core factory is pure and deterministic.
- The CLI writes only operator-specified output files.
- Commands in generated packages are execution plans, not shell execution.
- Promotion evidence is only marked `pass` from explicit result fields.
- Workflow sidecar publishing uses an automation branch and does not mutate `main`.

## Complexity Tracking

No constitution violation. The added complexity is justified because the prior system discovered candidates but had no automated bridge from `BACKTEST_REQUIRED` to executable evidence work.
