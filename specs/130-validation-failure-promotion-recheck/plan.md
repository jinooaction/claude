# Implementation Plan: Validation Failure Promotion Recheck Contract

**Branch**: `codex/validation-failure-promotion-recheck-contract` | **Date**: 2026-08-12 | **Spec**: `specs/130-validation-failure-promotion-recheck/spec.md`
**Input**: Feature specification from `specs/130-validation-failure-promotion-recheck/spec.md`

## Summary

Create a read-only promotion recheck contract for the final broad validation failure child candidate. The implementation adds a pure analytics module and probe that join learning ledger, autonomous-promotion, and candidate-result evidence. It keeps candidates suppressed when the current failure fingerprint is unchanged, records deterministic conditions for future recheck, and marks `candidate-broad-validation-failure-promotion-recheck-contract` as completed so released-work stops the same child from being selected again.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Existing stdlib/dataclass analytics style, existing `auto_invest.analytics` modules
**Storage**: Read-only sidecar JSON/Markdown and repository SDD artifacts
**Testing**: `uv run pytest`, focused unit tests, current sidecar replay
**Target Platform**: Local/GitHub Actions repository automation
**Project Type**: Single Python analytics repository
**Performance Goals**: Deterministic report build from small sidecar inputs in under one second locally
**Constraints**: No command execution, no broker API call, no orders, no capital allocation, no live config change, no whitelist/caps change, no secret access
**Scale/Scope**: Current two rejected validation candidates, generalized to future rejected promotion candidates with result evidence

## Constitution Check

- Risk grade: 2. The change affects operating contracts, released-work closure, and next-session behavior, but not the safety perimeter or money path.
- Money path: unchanged. No real order, account allocation, live strategy, or external paid service is touched.
- Safety perimeter: unchanged. Constitution and kernel files are not edited.
- Data access: read-only sidecars and repository files only.
- Rollback: revert the feature commit or remove the spec 130 completion marker and module/probe.

## Project Structure

```text
specs/130-validation-failure-promotion-recheck/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── promotion-recheck-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md

src/auto_invest/analytics/
└── validation_failure_promotion_recheck.py

scripts/
└── validation_failure_promotion_recheck_probe.py

tests/unit/
├── test_validation_failure_promotion_recheck.py
└── test_autonomous_work_execution.py
```

## Complexity Tracking

No constitution violation. The added module is intentionally separate because it closes a released-work candidate and must be runnable from sidecar artifacts without executing validation commands.
