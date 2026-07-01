# Tasks: Candidate History Support

**Input**: Design documents from `specs/074-candidate-history-support/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and changes workflow support inputs.

## Phase 1: Setup

- [x] T001 Create spec 074 design artifacts in `specs/074-candidate-history-support/`.
- [x] T002 Move `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 074.

## Phase 2: History support manifest

- [x] T003 [P] [US3] Add `CandidateHistoryDataset` manifest helpers in `src/auto_invest/analytics/candidate_history_support.py`.
- [x] T004 [P] [US3] Add manifest probe in `scripts/candidate_history_support_probe.py`.
- [x] T005 [P] [US3] Add manifest regression tests in `tests/unit/test_candidate_history_support.py`.

## Phase 3: Candidate command generation

- [x] T006 [US1] Add manifest-backed `--history-root` arguments in `src/auto_invest/analytics/candidate_factory.py`.
- [x] T007 [US1] Update strategy/portfolio candidate factory tests in `tests/unit/test_candidate_factory.py`.
- [x] T008 [US1] Add result executor allowlist regression for history-root commands in `tests/unit/test_candidate_result_executor.py`.

## Phase 4: Workflow support input

- [x] T009 [US2] Add candidate history staging to `.github/workflows/candidate-result-executor.yml`.
- [x] T010 [US2] Add workflow trigger paths for the new manifest module and probe.
- [x] T011 [US2] Update workflow safety regression in `tests/integration/test_candidate_result_executor_probe.py`.

## Phase 5: Smoke and verification

- [x] T012 [US1] Run synthetic local history smoke proving prepared history roots remove `no ingested datasets`.
- [x] T013 Run focused candidate history tests.
- [x] T014 Run `uv run pytest`.
- [x] T015 Run `uv run ruff check src tests`.
- [x] T016 Run PR quality gate, handoff fact check, and strict agent harness.
- [ ] T017 Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- [ ] T018 Check post-merge deployment/sidecar status and refresh HANDOFF.

## Dependencies & Execution Order

- T001-T002 before implementation.
- T003-T005 before factory/workflow consumption.
- T006-T008 before synthetic smoke.
- T009-T011 before PR because workflow support input is the production path.
- T012-T018 after implementation.

## Parallel Opportunities

- T003, T004, and T005 touch different files and can be reviewed independently.
- T007 and T011 can be edited while workflow implementation is being checked.
- Focused tests can run before full pytest.

## Implementation Strategy

1. Establish the manifest as the single source.
2. Make candidate commands consume it.
3. Make workflow prepare the manifest outputs.
4. Prove locally that prepared history changes the failure mode from missing dataset to real walk-forward evidence.
