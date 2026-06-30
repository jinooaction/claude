# Implementation Plan: Candidate Pending Next Actions

**Branch**: `Codex/candidate-pending-next-actions` | **Date**: 2026-07-01 | **Spec**: `specs/073-candidate-pending-next-actions/spec.md`

## Summary

Reduce current candidate result pending causes that are already diagnosed as automation wiring issues. The implementation fixes generated candidate commands, stages read-only support inputs in the result executor workflow, and keeps missing strategy price history pending until a separate safe ingest path exists.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: `uv`, GitHub Actions, existing `auto-invest` CLI  
**Storage**: Git sidecar branches and local `/tmp` staging directories only  
**Testing**: `uv run pytest`, `uv run ruff check src tests`, current-sidecar smoke  
**Target Platform**: GitHub Actions ubuntu runner and local Codex worktree  
**Project Type**: Single Python package with workflow automation  
**Performance Goals**: Candidate result executor stays under existing 15 minute workflow timeout  
**Constraints**: No broker API, no orders, no capital/live config, no whitelist/caps/sentinel/secret writes  
**Scale/Scope**: Current 9 candidate packages; deterministic sidecar staging for future packages

## Constitution Check

- **Safety perimeter**: No constitution, kernel, K1-K6, order, broker, capital, or live deployment boundary changes.
- **Backtest -> Canary -> Full**: Preserved. Missing history cannot become pass evidence.
- **Auditability**: Candidate results remain JSON and Markdown sidecars; support inputs are read-only copies from existing branches.
- **Secrets**: No new secrets, no secret output, no external paid service.
- **Risk grade**: 2, because workflow and candidate automation behavior change.

## Project Structure

```text
src/auto_invest/analytics/candidate_factory.py
src/auto_invest/analytics/candidate_result_executor.py
.github/workflows/candidate-result-executor.yml
tests/unit/test_candidate_factory.py
tests/unit/test_candidate_result_executor.py
tests/integration/test_candidate_result_executor_probe.py
specs/073-candidate-pending-next-actions/
```

## Implementation Steps

1. Add spec 073 design artifacts and move the Speckit pointer.
2. Update candidate factory commands for ops liveness, analytics validation, and data quality.
3. Update result executor allowlist for the data quality no-live command.
4. Stage pipeline liveness and public data support inputs in the result executor workflow.
5. Add tests for command generation, safe allowlist, workflow staging, and missing-history preservation.
6. Re-run current-sidecar candidate smoke and verify only safe pending causes are reduced.
7. Run full verification, PR quality gate, PR, merge, deployment/sidecar checks, and handoff refresh.

## Complexity Tracking

No constitution violation or safety waiver is used. The only intentional duplication is using pipeline liveness for both ops liveness and data quality because the current data quality candidate concerns sidecar freshness/evidence quality, not live market data reads.
