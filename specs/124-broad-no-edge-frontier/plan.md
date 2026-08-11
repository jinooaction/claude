# Implementation Plan: Broad NO_EDGE Frontier

**Branch**: `124-broad-no-edge-frontier` | **Date**: 2026-08-11 | **Spec**: `specs/124-broad-no-edge-frontier/spec.md`
**Input**: Feature specification from `specs/124-broad-no-edge-frontier/spec.md`

## Summary

The autonomous-work loop already emits a broad frontier parent candidate when all known work is closed and the money path remains `NO_EDGE_YET`. This change completes that candidate by making the parent fingerprint suppressible after release and by adding a deterministic broad no-edge frontier map that advances to concrete no-live experiment candidates instead of falling back to passive waiting.

## Technical Context

**Language/Version**: Python 3.12 project conventions
**Primary Dependencies**: standard library, existing `auto_invest.analytics` modules
**Storage**: sidecar JSON/Markdown reports and git-tracked SDD documents
**Testing**: pytest plus ruff
**Target Platform**: repository automation and GitHub sidecar workflows
**Project Type**: Python library/automation scripts
**Performance Goals**: deterministic report generation with negligible overhead
**Constraints**: read-only candidate generation; no broker calls, no orders, no capital movement, no secret access
**Scale/Scope**: autonomous-work report, unit tests, SDD artifacts, handoff closeout

## Constitution Check

- **I Position sizing and exposure limits**: Not changed. No order path is touched.
- **II Deny-by-default whitelist**: Not changed. No symbol, order type, session, or account allowlist is widened.
- **III Defined judgment points**: Not changed. No new LLM runtime call is added.
- **IV Append-only audit and reconciliation**: Not changed. The feature reads released-work evidence and emits a candidate report only.
- **V Secret isolation**: Not changed. No secrets are read, written, or logged.
- **VI Backtest -> Canary -> Full live**: Preserved. Follow-up candidates are no-live design/validation tasks only.
- **VII External API robustness**: Preserved. No external API call site is added.
- **VIII.A Change discipline**: This is a code and automation-reporting change, not a market-hours deploy instruction.
- **IX Self-modification boundary**: No constitution, kernel manifest, order limits, secrets, audit schema, or live deploy gate is touched.
- **X Measurement-driven autonomous growth**: Improved by turning `NO_EDGE_YET` exhaustion into measured no-live experiment candidates while keeping edge gates intact.

## Project Structure

### Documentation (this feature)

```text
specs/124-broad-no-edge-frontier/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── broad-no-edge-frontier.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/autonomous_work_execution.py
tests/unit/test_autonomous_work_execution.py
```

**Structure Decision**: Reuse the existing autonomous-work report module and unit test file because the current macro, investment-edge, data-evidence, execution-quality, and agent-ops maps already live there.

## Complexity Tracking

No constitution violation is introduced. The extra map mirrors existing local patterns instead of adding a new subsystem.
