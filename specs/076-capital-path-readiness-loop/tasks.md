# Tasks: Capital Path Readiness Loop

**Input**: Design documents from `specs/076-capital-path-readiness-loop/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and adds a recurring sidecar loop.

## Phase 1: Setup

- [X] T001 Create spec 076 design artifacts in `specs/076-capital-path-readiness-loop/`.
- [X] T002 Move `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 076.

## Phase 2: Readiness core

- [X] T003 [P] [US1] Add capital path readiness dataclasses and JSON/Markdown rendering in `src/auto_invest/analytics/capital_path_readiness.py`.
- [X] T004 [P] [US1] Add safe sidecar JSON extraction and missing/malformed evidence handling in `src/auto_invest/analytics/capital_path_readiness.py`.
- [X] T005 [US1] Implement readiness state classification from money-path and reassign evidence in `src/auto_invest/analytics/capital_path_readiness.py`.
- [X] T006 [P] [US1] Add unit tests for accumulating-edge and preview-only classification in `tests/unit/test_capital_path_readiness.py`.

## Phase 3: Candidate routing

- [X] T007 [US2] Parse evolution candidate backlog and learning ledger into priority/suppressed readiness candidates in `src/auto_invest/analytics/capital_path_readiness.py`.
- [X] T008 [P] [US2] Add unit tests proving rejected candidates are suppressed and live-readiness candidates are prioritized in `tests/unit/test_capital_path_readiness.py`.

## Phase 4: Probe and workflow

- [X] T009 [US3] Add `scripts/capital_path_readiness_probe.py` manifest, JSON, and Markdown output support.
- [X] T010 [US3] Add `.github/workflows/capital-path-readiness.yml` to collect sidecars and publish `automation/capital-path-readiness-last-run`.
- [X] T011 [US3] Register `capital-path-readiness` in `src/auto_invest/analytics/pipeline_liveness.py`.
- [X] T012 [P] [US3] Add integration tests for probe manifest/output and pipeline liveness registration in `tests/integration/`.

## Phase 5: Smoke and verification

- [X] T013 Run latest-sidecar local smoke proving current state is not capital-armable and rejected candidates are suppressed.
- [X] T014 Run focused capital path readiness tests.
- [X] T015 Run `uv run pytest`.
- [X] T016 Run `uv run ruff check src tests`.
- [X] T017 Run PR quality gate, handoff fact check, and strict agent harness.
- [X] T018 Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- [X] T019 Check post-merge workflow/sidecar status and refresh HANDOFF.

## Dependencies & Execution Order

- T001-T002 before implementation.
- T003-T005 before probe/workflow.
- T006/T008 validate core and candidate routing before workflow smoke.
- T009-T012 before latest-sidecar smoke.
- T013-T019 after implementation.

## Parallel Opportunities

- T003, T004, and T006 touch different responsibilities and can be prepared independently.
- T008 and T012 cover different test layers.
- Focused tests can run before full pytest.

## Implementation Strategy

1. Build a pure read-only core that classifies readiness from dictionaries/text.
2. Add a probe that mirrors existing sidecar collection patterns.
3. Publish a dedicated workflow sidecar.
4. Register the sidecar in liveness and prove current sidecars produce a safe, non-capital-armable result.
