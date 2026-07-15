# Tasks: Operator Report Liveness Contract

**Input**: Design documents from `specs/118-operator-report-liveness-contract/`  
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/

**Tests**: Required. This is a grade 2 operating-system change and must prove rule surfaces, final-report classification, probe output, and autonomous-work completion behavior.

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/118-operator-report-liveness-contract/`
- [x] T002 Point `.specify/feature.json` at `specs/118-operator-report-liveness-contract`
- [x] T003 Update the Speckit plan pointer in `CLAUDE.md`

## Phase 2: Foundational Tests

- [x] T004 [P] Add operator report liveness unit tests in `tests/unit/test_operator_report_liveness.py`
- [x] T005 [P] Add probe integration coverage in `tests/integration/test_operator_report_liveness_probe.py`
- [x] T006 [P] Add autonomous-work released-candidate completion coverage in `tests/unit/test_autonomous_work_execution.py`
- [x] T007 Run focused new tests and confirm they fail for missing implementation

## Phase 3: User Story 1 - Report rules are alive and traceable

- [x] T008 [US1] Implement rule-surface and report data model in `src/auto_invest/analytics/operator_report_liveness.py`
- [x] T009 [US1] Implement `QUALITY-006`, `AGENTS.md`, quality gate, PR template, and HANDOFF checks in `src/auto_invest/analytics/operator_report_liveness.py`
- [x] T010 [US1] Verify rule-surface focused tests pass

## Phase 4: User Story 2 - Supplied final report is classified without guessing

- [x] T011 [US2] Implement deterministic final-report category checks in `src/auto_invest/analytics/operator_report_liveness.py`
- [x] T012 [US2] Implement JSON/Markdown CLI probe in `scripts/operator_report_liveness_probe.py`
- [x] T013 [US2] Verify final-report and probe tests pass

## Phase 5: User Story 3 - Completion advances the autonomous queue cleanly

- [x] T014 [US3] Ensure released `candidate-operator-report-liveness-contract` is marked released in autonomous-work frontier output
- [x] T015 [US3] Ensure autonomous-work does not reselect the same candidate after release
- [x] T016 [US3] Verify autonomous-work focused test passes

## Phase 6: Safety Boundary and Validation

- [x] T017 Run `uv run pytest tests/unit/test_operator_report_liveness.py tests/integration/test_operator_report_liveness_probe.py tests/unit/test_autonomous_work_execution.py -q`
- [x] T018 Run `uv run pytest -q`
- [x] T019 Run `uv run ruff check src tests`
- [x] T020 Run `git diff --check`
- [x] T021 Run `uv run python scripts/check_handoff_facts.py`
- [x] T022 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T023 Create PR with risk grade, safety boundary, validation, and handoff evidence
- [x] T024 Merge when tests, lint, PR quality gate, and mergeability are clean
- [x] T025 Refresh `HANDOFF.md` after merge and validate it

## Dependencies

- T001-T003 before implementation.
- T004-T007 before implementation tasks T008-T015.
- T008-T010 before final-report classification.
- T011-T013 before probe validation.
- T014-T016 before full validation.
- T017-T022 before PR merge.

## Implementation Strategy

1. Prove missing module and missing autonomous completion behavior with focused tests.
2. Add the smallest read-only report model.
3. Check deterministic meaning categories instead of exact prose shape.
4. Keep released-work as the candidate completion source.
5. Preserve money-path and safety boundaries.
