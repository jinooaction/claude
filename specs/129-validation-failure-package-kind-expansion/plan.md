# Implementation Plan: Validation Failure Package-Kind Expansion Contract

**Branch**: `codex/validation-failure-package-kind-expansion-contract` | **Date**: 2026-08-12 | **Spec**: `specs/129-validation-failure-package-kind-expansion/spec.md`
**Input**: Feature specification from `specs/129-validation-failure-package-kind-expansion/spec.md`

## Summary

Create a read-only package-kind expansion contract for the current broad validation failure child candidate. The implementation adds a pure analytics module and probe that join candidate package plans and candidate-result evidence, split `strategy_backtest` and `portfolio_backtest` failures into deterministic buckets, and produce next no-live experiment axes without executing validation commands or touching the money path. It marks `candidate-broad-validation-failure-package-kind-expansion-contract` as completed so released-work can advance autonomous-work to promotion recheck.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Existing stdlib/dataclass analytics style, existing `auto_invest.analytics` modules
**Storage**: Read-only sidecar JSON/Markdown and repository SDD artifacts
**Testing**: `uv run pytest`, focused unit tests, current sidecar replay
**Target Platform**: Local/GitHub Actions repository automation
**Project Type**: Single Python analytics repository
**Performance Goals**: Deterministic report build from small sidecar inputs in under one second locally
**Constraints**: No command execution, no broker API call, no orders, no capital allocation, no live config change, no whitelist/caps change, no secret access
**Scale/Scope**: Current two retryable validation failure packages, generalized to future strategy and portfolio validation packages

## Constitution Check

- Risk grade: 2. The change affects operating contracts, released-work closure, and next-session behavior, but not the safety perimeter or money path.
- Money path: unchanged. No real order, account allocation, live strategy, or external paid service is touched.
- Safety perimeter: unchanged. Constitution and kernel files are not edited.
- Data access: read-only sidecars and repository files only.
- Rollback: revert the feature commit or remove the spec 129 completion marker and module/probe.

## Project Structure

```text
specs/129-validation-failure-package-kind-expansion/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── package-kind-expansion-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md

src/auto_invest/analytics/
└── validation_failure_package_kind_expansion.py

scripts/
└── validation_failure_package_kind_expansion_probe.py

tests/unit/
├── test_validation_failure_package_kind_expansion.py
└── test_autonomous_work_execution.py
```

## Complexity Tracking

No constitution violation. The added module is intentionally separate because it closes a released-work candidate and must be runnable from sidecar artifacts without executing validation commands.
