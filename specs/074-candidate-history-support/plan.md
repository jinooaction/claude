# Implementation Plan: Candidate History Support

**Branch**: `Codex/074-candidate-history-support` | **Date**: 2026-07-01 | **Spec**: `specs/074-candidate-history-support/spec.md`

## Summary

Prepare deterministic read-only price history support for candidate strategy and portfolio backtests. The implementation centralizes portfolio-to-history mapping, adds `--history-root` to candidate walk-forward commands, stages server price DB exports in the result executor workflow, and preserves fail-safe pending behavior whenever support input is absent or insufficient.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: `uv`, Typer CLI, GitHub Actions, existing `bars-export`, existing `ingest-history`, existing `portfolio-walk-forward`  
**Storage**: Existing server SQLite price DBs read-only; temporary `/tmp/candidate_result_history` datasets on runner and server  
**Testing**: `uv run pytest`, `uv run ruff check src tests`, synthetic current-command smoke  
**Target Platform**: GitHub Actions ubuntu runner plus `/opt/auto-invest` server over existing SSH support  
**Project Type**: Single Python package with workflow automation  
**Performance Goals**: Candidate result executor remains within the existing 15 minute workflow timeout; missing datasets do not block non-strategy candidates  
**Constraints**: No broker API calls, no orders, no capital/live config, no whitelist/caps/sentinel edits, no secret logging, no source DB writes  
**Scale/Scope**: Current strategy/portfolio candidate datasets: micro GTAA, global-trend-wide, multi-asset trend

## Constitution Check

- **I. Position sizing and II. whitelist**: Not touched. No order path is invoked.
- **III. LLM judgment points**: Not touched. No LLM call is added.
- **IV. Audit log**: Not modified. Candidate audit DBs remain temporary local files.
- **V. Secret isolation**: SSH secret is used only by GitHub Actions support input staging and is never logged.
- **VI. Backtest -> Canary -> Full**: Preserved. This feature strengthens the backtest evidence stage and does not promote anything by itself.
- **VII. External API robustness**: No broker or market data API call is added; existing stored bars are read.
- **VIII.A No market-hours live deploy**: No live deploy path is changed.
- **IX. Self-modification boundary**: No constitution, kernel, caps, whitelist, audit schema, or secret boundary file is changed.
- **X. Measurement-driven growth**: Improved because candidates get measured backtest evidence instead of pending on missing local data.
- **Risk grade**: 2, because workflow and candidate automation behavior change. No grade 3 or 4 boundary is touched.

## Project Structure

```text
src/auto_invest/analytics/candidate_history_support.py
src/auto_invest/analytics/candidate_factory.py
scripts/candidate_history_support_probe.py
.github/workflows/candidate-result-executor.yml
tests/unit/test_candidate_history_support.py
tests/unit/test_candidate_factory.py
tests/unit/test_candidate_result_executor.py
tests/integration/test_candidate_result_executor_probe.py
specs/074-candidate-history-support/
```

## Phase 0: Research

Research is captured in `research.md`.

## Phase 1: Design and Contracts

Data model is captured in `data-model.md`.  
Workflow and command contracts are captured in `contracts/candidate-history-support.md`.  
Operational validation is captured in `quickstart.md`.

## Complexity Tracking

No constitution violation or safety waiver is used. SSH appears only in workflow support input staging, not in candidate package commands. The intentionally duplicated `/tmp` remote and runner roots are documented so staging can tar/extract without writing source or sidecar branches.
