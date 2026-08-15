# Tasks: Broad Frontier Expansion NO_EDGE Refresh

**Input**: Design documents from `specs/134-broad-frontier-expansion-no-edge-refresh/`

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/134-broad-frontier-expansion-no-edge-refresh/`
- [x] T002 Update active feature pointer in `.specify/feature.json`

## Phase 2: Implementation

- [x] T003 Add second-wave broad no-edge candidate constants and templates in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T004 Stop reissuing broad no-edge parent candidates after a parent is released
- [x] T005 Add autonomous-work tests for second-wave candidate selection

## Phase 3: Validation, PR, and Handoff

- [x] T006 Run focused autonomous-work tests
- [x] T007 Run `uv run pytest`
- [x] T008 Run `uv run ruff check src tests`
- [x] T009 Run `git diff --check`
- [x] T010 Run `uv run python scripts/check_handoff_facts.py`
- [x] T011 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T012 Prepare PR body, PR quality gate evidence, and handoff refresh

## Implementation Strategy

Keep this as a grade 2 operating-loop change. The code only changes candidate routing and report content. It must not touch live trading, broker calls, capital allocation, secrets, kernel, or constitution files.
