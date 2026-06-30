# Tasks: Candidate Result Executor

**Input**: Design documents from `specs/071-candidate-result-executor/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation.

## Phase 1: Setup

- [x] T001 [P] Reuse current candidate factory fixtures in `tests/fixtures/candidate_factory/fresh/` so the executor is tested against the same 9-package handoff the factory emits.
- [x] T002 [P] Add workflow regression fixture expectations in `tests/integration/test_candidate_result_executor_probe.py`.

---

## Phase 2: Foundational

- [x] T003 Implement result executor data model and safety classifier in `src/auto_invest/analytics/candidate_result_executor.py`.
- [x] T004 Add unit tests for result normalization and safety blocking in `tests/unit/test_candidate_result_executor.py`.

---

## Phase 3: User Story 1 - ready 패키지를 결과 증거로 변환 (Priority: P1)

**Goal**: Candidate packages produce one machine-readable result row each.

**Independent Test**: `uv run pytest tests/unit/test_candidate_result_executor.py`.

- [x] T005 [US1] Implement package parsing and one-row-per-package result generation in `src/auto_invest/analytics/candidate_result_executor.py`.
- [x] T006 [US1] Implement markdown, full JSON, and `candidate_results.json` artifact writers in `src/auto_invest/analytics/candidate_result_executor.py`.
- [x] T007 [US1] Add `scripts/candidate_result_executor_probe.py`.

---

## Phase 4: User Story 2 - 안전한 실행만 허용하고 실패를 증거화 (Priority: P2)

**Goal**: Unsafe or unsupported packages are blocked before execution.

**Independent Test**: Unsafe fixture package is blocked and no live/broker/SSH token appears in the workflow.

- [x] T008 [US2] Add allowlisted execution handlers and conservative evidence mapping in `src/auto_invest/analytics/candidate_result_executor.py`.
- [x] T009 [US2] Add safety command registry entry and regression assertions in `src/auto_invest/safety/command_registry.py` and `tests/unit/test_safety_command_registry.py`.
- [x] T010 [US2] Add CLI command `candidate-results` in `src/auto_invest/cli.py`.

---

## Phase 5: User Story 3 - factory와 promotion 루프가 자동 소비 (Priority: P3)

**Goal**: Result evidence is published to a sidecar and consumed by the next factory run.

**Independent Test**: Workflow text tests prove sidecar publication and factory collection.

- [x] T011 [US3] Add `.github/workflows/candidate-result-executor.yml`.
- [x] T012 [US3] Update `.github/workflows/candidate-implementation-factory.yml` to include the result executor workflow trigger path if needed.
- [x] T013 [US3] Register `candidate-result-executor` in `src/auto_invest/analytics/pipeline_liveness.py` and update tests.

---

## Phase 6: Polish & Cross-Cutting

- [x] T014 Run focused candidate result executor tests.
- [x] T015 Run full `uv run pytest`.
- [x] T016 Run `uv run ruff check src tests`.
- [x] T017 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
- [ ] T018 Update handoff after merge if operating truth changed.

## Dependencies & Execution Order

- Phase 1 and Phase 2 come first.
- User Story 1 is the MVP and unlocks artifact generation.
- User Story 2 hardens the executor before workflow automation is trusted.
- User Story 3 wires the scheduled loop after the local behavior is testable.

## Parallel Opportunities

- T001 and T002 can run in parallel.
- Unit and integration test files can be edited independently after the data model is stable.

## Implementation Strategy

Deliver the pure local executor first, then the CLI/probe, then the GitHub Actions sidecar. Keep the workflow no-live and sidecar-only until tests prove the result format is consumed by the existing candidate factory.
