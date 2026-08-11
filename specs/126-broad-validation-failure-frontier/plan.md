# Implementation Plan: Broad Validation Failure Frontier

**Branch**: `codex/broad-validation-failure-frontier` | **Date**: 2026-08-11 | **Spec**: `specs/126-broad-validation-failure-frontier/spec.md`  
**Input**: Feature specification from `specs/126-broad-validation-failure-frontier/spec.md`

## Summary

The autonomous-work loop already creates a broad validation-failure parent candidate when every known candidate is closed and retryable validation packages remain blocked. This change completes that parent by adding a deterministic validation-failure frontier map and by advancing from the released parent to concrete no-live candidates instead of falling back to passive evidence waiting.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Standard library plus existing auto-invest analytics modules  
**Storage**: Read-only sidecar JSON/Markdown inputs and released-work scan output  
**Testing**: pytest, ruff  
**Target Platform**: Local and GitHub workflow execution for auto-invest sidecars  
**Project Type**: Python package plus CLI/reporting scripts  
**Performance Goals**: Deterministic report generation in under one second for current sidecar payloads  
**Constraints**: No broker call, no order, no capital allocation, no live config change, no secret read/write, no whitelist/caps change  
**Scale/Scope**: Current candidate-result and released-work sidecars; no database migration or broker integration

## Constitution Check

- Principles I and II: position sizing and whitelist are untouched; no order path changes.
- Principle III: no new LLM judgment point is introduced.
- Principle IV: audit log is untouched; no audit deletion or mutation.
- Principle V: no secret read/write is introduced.
- Principle VI: staged rollout remains unchanged; output is no-live work selection only.
- Principle VII: no external API call is added.
- Principle VIII.A: no live deploy path is changed.
- Principles IX and X: this supports measured autonomous growth while preserving the safety perimeter.

Result: PASS. Risk grade 2 operating-system change, no safety boundary or money-path change.

## Project Structure

### Documentation (this feature)

```text
specs/126-broad-validation-failure-frontier/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── broad-validation-failure-frontier.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/autonomous_work_execution.py
tests/unit/test_autonomous_work_execution.py
```

**Structure Decision**: Extend the existing autonomous-work report because the failure parent, released-work suppression, frontier maps, Markdown rendering, and work packet selection already live there. Do not add a broker-facing command or live execution path.

## Complexity Tracking

No constitution violation. The added complexity is a small nested frontier map, matching the existing investment, data, execution, agent-ops, and broad no-edge frontier patterns.
