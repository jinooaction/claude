# Implementation Plan: Validation Failure Command Replay Contract

**Branch**: `codex/validation-failure-command-replay-contract` | **Date**: 2026-08-11 | **Spec**: `specs/127-validation-failure-command-replay/spec.md`
**Input**: Feature specification from `specs/127-validation-failure-command-replay/spec.md`

## Summary

Create a no-live command replay contract for the current retryable validation failures. The implementation adds a pure analytics module and probe that join candidate package commands with candidate result evidence, classify replay safety using existing command safety rules, surface missing exit/output evidence honestly, and mark `candidate-broad-validation-failure-command-replay-contract` as completed for released-work.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Standard library plus existing `auto_invest.analytics` helpers  
**Storage**: Filesystem sidecar JSON and Markdown only  
**Testing**: pytest and ruff  
**Target Platform**: Local and GitHub Actions worker  
**Project Type**: Python analytics library plus probe script  
**Performance Goals**: Parse current sidecars and render reports in under one second for normal sidecar size  
**Constraints**: No command execution, no broker API, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write  
**Scale/Scope**: Current candidate package/result sidecars; no database migration or live integration

## Constitution Check

- Principles I-VII: PASS. No order routing, position limits, whitelist, audit log, or secret surfaces change.
- Principle VIII.A: PASS. No market-hours deploy behavior changes.
- Principle IX: PASS. Kernel manifest and constitution are untouched.
- Principle X: PASS. This improves measurement-driven autonomous growth by making failed validation evidence more precise without opening money gates.
- Risk grade: 2. The change affects operating contracts, released-work closure, and next-session behavior, but not the safety perimeter or money path.

## Project Structure

### Documentation (this feature)

```text
specs/127-validation-failure-command-replay/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── command-replay-contract.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/
├── candidate_result_executor.py
└── validation_failure_command_replay.py

scripts/
└── validation_failure_command_replay_probe.py

tests/unit/
└── test_validation_failure_command_replay.py
```

**Structure Decision**: Use a new analytics module and probe to match the existing sidecar contract pattern. Keep candidate-result execution behavior unchanged; only expose its safety classification for read-only contract generation.

## Complexity Tracking

No constitution violation. The added module is intentionally separate because it closes a released-work candidate and must be runnable from sidecar artifacts without executing validation commands.
