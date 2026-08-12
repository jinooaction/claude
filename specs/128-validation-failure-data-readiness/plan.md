# Implementation Plan: Validation Failure Data Readiness Contract

**Branch**: `codex/validation-failure-data-readiness-contract` | **Date**: 2026-08-12 | **Spec**: `specs/128-validation-failure-data-readiness/spec.md`  
**Input**: Feature specification from `specs/128-validation-failure-data-readiness/spec.md`

## Summary

Create a read-only data readiness contract for the current broad validation failure child candidate. The implementation adds a pure analytics module and probe that join candidate package commands, candidate-result execution evidence, candidate history support, portfolio TOML existence, public-data, and regime-stratify evidence. It classifies each validation package as data-ready, waiting for evidence, or blocked by data input, and marks `candidate-broad-validation-failure-data-readiness-contract` as completed for released-work.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: Existing stdlib/dataclass analytics style, existing `auto_invest.analytics` modules  
**Storage**: Read-only sidecar JSON/Markdown and repository files  
**Testing**: `uv run pytest`, focused unit tests, current sidecar replay  
**Target Platform**: Local/GitHub Actions repository automation  
**Project Type**: Single Python analytics repository  
**Performance Goals**: Deterministic report build from small sidecar inputs in under one second locally  
**Constraints**: No command execution, no broker API call, no orders, no capital allocation, no live config change, no whitelist/caps change, no secret access  
**Scale/Scope**: Current two retryable validation failure packages, generalized to future packages with portfolio-walk-forward surfaces

## Constitution Check

- Risk grade: 2. The change affects operating contracts, released-work closure, and next-session behavior, but not the safety perimeter or money path.
- Money path: unchanged. No real order, account allocation, live strategy, or external paid service is touched.
- Safety perimeter: unchanged. Constitution and kernel files are not edited.
- Data access: read-only sidecars and repository files only.
- Rollback: revert the feature commit or remove the spec 128 completion marker and module/probe.

## Project Structure

```text
specs/128-validation-failure-data-readiness/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── data-readiness-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md

src/auto_invest/analytics/
└── validation_failure_data_readiness.py

scripts/
└── validation_failure_data_readiness_probe.py

tests/unit/
├── test_validation_failure_data_readiness.py
└── test_autonomous_work_execution.py
```

## Complexity Tracking

No constitution violation. The added module is intentionally separate because it closes a released-work candidate and must be runnable from sidecar artifacts without executing validation commands.
