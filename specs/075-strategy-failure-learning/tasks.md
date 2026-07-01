# Tasks: Strategy Failure Learning

**Input**: Design documents from `specs/075-strategy-failure-learning/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and changes autonomous loop sidecar consumption.

## Phase 1: Setup

- [x] T001 Create spec 075 design artifacts in `specs/075-strategy-failure-learning/`.
- [x] T002 Move `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 075.

## Phase 2: Promotion failure signal support

- [x] T003 [P] [US1] Add promotion summary evidence requirement in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T004 [P] [US1] Add parsing model/helper for `DISCARD` promotion assessments in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T005 [US1] Merge parsed promotion failures into `learning_ledger.json` as `rejected` entries in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T006 [P] [US1] Add unit tests for two `DISCARD` candidates becoming rejected ledger entries in `tests/unit/test_evolution_loop.py`.

## Phase 3: Re-activation prevention

- [x] T007 [US2] Ensure existing rejected ledger entries are not duplicated when the same promotion failure recurs in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T008 [P] [US2] Add unit tests for no duplicate rejected entries and malformed promotion summary fail-open behavior in `tests/unit/test_evolution_loop.py`.

## Phase 4: Workflow sidecar consumption

- [x] T009 [US3] Update `scripts/evolution_loop_probe.py --manifest` behavior through the default evidence requirements so promotion summary is collected.
- [x] T010 [US3] Update `.github/workflows/autonomous-evolution-loop.yml` trigger paths if needed for promotion learning changes.
- [x] T011 [P] [US3] Update integration tests for manifest collection and read-only workflow safety in `tests/integration/test_evolution_loop_probe.py`.

## Phase 5: Smoke and verification

- [x] T012 Run latest-sidecar local smoke proving `candidate-1ed634d8bf6d` and `candidate-cc96b35062da` become `rejected` ledger entries.
- [x] T013 Run focused evolution tests.
- [x] T014 Run `uv run pytest`.
- [x] T015 Run `uv run ruff check src tests`.
- [x] T016 Run PR quality gate, handoff fact check, and strict agent harness.
- [x] T017 Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- [x] T018 Check post-merge deployment/sidecar status and refresh HANDOFF.

## Dependencies & Execution Order

- T001-T002 before implementation.
- T003-T005 before tests can pass.
- T006-T008 validate US1/US2 and should run before workflow smoke.
- T009-T011 before PR because workflow support input is the production path.
- T012-T018 after implementation.

## Parallel Opportunities

- T003, T004, and T006 touch related files but can be prepared independently before final integration.
- T008 and T011 cover different test files.
- Focused tests can run before full pytest.

## Implementation Strategy

1. Add promotion summary to the existing evolution evidence manifest.
2. Parse only `DISCARD` assessments and ignore every other stage.
3. Merge failures into the existing learning ledger without creating duplicate entries.
4. Prove latest sidecars now turn failed candidates into durable rejected memory.
