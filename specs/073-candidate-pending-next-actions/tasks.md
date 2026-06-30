# Tasks: Candidate Pending Next Actions

**Input**: Design documents from `specs/073-candidate-pending-next-actions/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and changes candidate execution behavior.

## Phase 1: Setup

- [x] T001 Create spec 073 design artifacts.
- [x] T002 Move `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 073.

## Phase 2: Candidate command contracts

- [x] T003 [US1] Update ops liveness command generation in `src/auto_invest/analytics/candidate_factory.py`.
- [x] T004 [US1] Update analytics validation command generation in `src/auto_invest/analytics/candidate_factory.py`.
- [x] T005 [US1] Replace data quality default DB command with no-live sidecar validation in `src/auto_invest/analytics/candidate_factory.py`.
- [x] T006 [US1] Allow the updated data quality command in `src/auto_invest/analytics/candidate_result_executor.py`.

## Phase 3: Workflow support inputs

- [x] T007 [US2] Stage pipeline liveness sidecars in `.github/workflows/candidate-result-executor.yml`.
- [x] T008 [US2] Stage public data snapshot in `.github/workflows/candidate-result-executor.yml`.
- [x] T009 [US2] Add workflow trigger paths for changed support-input dependencies.

## Phase 4: Tests

- [x] T010 [US1] Add candidate factory command contract tests.
- [x] T011 [US1] Add result executor data quality allowlist test.
- [x] T012 [US2] Add workflow support-input regression test.
- [x] T013 [US3] Preserve missing-history pending tests.

## Phase 5: Current-sidecar smoke

- [x] T014 Prepare current sidecar support inputs locally.
- [x] T015 Generate current candidate packages and run candidate result executor.
- [x] T016 Confirm command contract and default DB diagnostics are removed while history diagnostics remain honest.

## Phase 6: Verification and delivery

- [x] T017 Run focused candidate tests.
- [x] T018 Run `uv run pytest`.
- [x] T019 Run `uv run ruff check src tests`.
- [x] T020 Run PR quality gate, handoff fact check, and strict agent harness.
- [ ] T021 Commit, push, open PR, satisfy checks, merge when automatic merge conditions are met.
- [ ] T022 Check post-merge deployment/sidecar status and refresh HANDOFF.

## Dependencies & Execution Order

- T003-T006 before T010-T011.
- T007-T009 before T012 and local smoke.
- T014-T016 before PR because success criteria depend on current sidecar evidence.
- Full verification and handoff refresh happen after implementation tests.

## Parallel Opportunities

- Factory tests and executor allowlist tests can be edited independently.
- Workflow text regression can be added while unit tests run.
- Local sidecar preparation can happen after command generation is complete.
