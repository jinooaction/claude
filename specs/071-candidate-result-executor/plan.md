# Implementation Plan: Candidate Result Executor

**Branch**: `Codex/candidate-result-executor` | **Date**: 2026-06-30 | **Spec**: `specs/071-candidate-result-executor/spec.md`  
**Input**: Feature specification from `specs/071-candidate-result-executor/spec.md`

## Summary

Build the missing execution layer after the candidate implementation factory. The executor reads `candidate_packages.json`, runs only allowlisted no-live validations, normalizes outputs into `candidate_results.json`, publishes a sidecar branch, and lets the next candidate factory run merge real result evidence into promotion decisions.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Typer, pytest, GitHub Actions, existing `auto-invest` CLI/probe surfaces  
**Storage**: JSON sidecar branch plus local scratch output paths supplied by the operator or workflow  
**Testing**: pytest unit/integration tests, workflow text regressions, ruff  
**Target Platform**: Local Mac and GitHub Actions Ubuntu runner  
**Project Type**: CLI + automation workflow  
**Performance Goals**: Normal current package set completes within the workflow timeout and emits partial evidence on package failures  
**Constraints**: no broker calls, no orders, no live config edits, no capital scaling, no whitelist/caps changes, no sentinel writes  
**Scale/Scope**: Current 9 packages, designed for dozens

## Constitution Check

- Principles I-II: no order placement and no whitelist/caps changes.
- Principles III-VII: no new LLM judgment point, no audit deletion, no secret movement, no broker/API side effect.
- VIII.A: workflow publishes evidence only; deploy timing remains governed by existing deploy workflow.
- IX: adds non-kernel operating automation; no constitution or kernel manifest changes.
- X: preserves `Backtest -> Canary -> Full`; result evidence can only unlock the next safe validation stage.

Risk grade: 2. This changes automation behavior and sidecar evidence flow, but does not change the safety perimeter or live money execution.

## Project Structure

```text
src/auto_invest/analytics/
├── candidate_result_executor.py
├── candidate_factory.py
├── pipeline_liveness.py

scripts/
├── candidate_result_executor_probe.py

.github/workflows/
├── candidate-result-executor.yml
├── candidate-implementation-factory.yml

tests/
├── fixtures/candidate_factory/fresh/
├── integration/test_candidate_result_executor_probe.py
├── unit/test_candidate_result_executor.py
├── unit/test_pipeline_liveness.py
├── unit/test_safety_command_registry.py
```

## Safety Strategy

- Do not run package command strings through a shell.
- Map package kinds to explicit executor functions and command token allowlists.
- Treat unknown package kinds, live order flags, SSH, KIS secrets, sentinels, whitelist/caps, or capital mutation references as `blocked`.
- Normalize inconclusive or missing outputs to `pending`, not `pass`.
- Publish sidecar artifacts only; do not mutate tracked state on `main`.

## Complexity Tracking

No constitution violation. The extra module and workflow are justified because the previous loop could build packages but had no autonomous path to generate machine-readable result evidence.
