# Tasks: Validation Failure Data Readiness Contract

**Input**: Design documents from `specs/128-validation-failure-data-readiness/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/128-validation-failure-data-readiness/`
- [x] T002 Update active feature pointer in `.specify/feature.json`
- [x] T003 Update active plan pointer in `CLAUDE.md`

---

## Phase 2: Foundational

- [x] T004 [P] Add focused data readiness tests in `tests/unit/test_validation_failure_data_readiness.py`
- [x] T005 [P] Add autonomous-work advancement test in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - 검증 실패가 데이터 문제인지 분리한다 (Priority: P1)

**Goal**: Produce deterministic package-level data readiness rows for current validation failures.

**Independent Test**: Focused data readiness tests produce two package rows and three data surfaces.

- [x] T006 [US1] Implement data readiness report models in `src/auto_invest/analytics/validation_failure_data_readiness.py`
- [x] T007 [US1] Join package commands with candidate history support and result evidence in `src/auto_invest/analytics/validation_failure_data_readiness.py`

---

## Phase 4: User Story 2 - 관측 기간과 sidecar 한계를 함께 남긴다 (Priority: P2)

**Goal**: Record observation windows, data freshness, public-data context, and regime-stratify context without false data failures.

**Independent Test**: stdout JSON fields and public/regime summaries appear in the contract.

- [x] T008 [US2] Add observation metric parsing and stable cause codes in `src/auto_invest/analytics/validation_failure_data_readiness.py`
- [x] T009 [US2] Add Markdown and JSON artifact writer in `src/auto_invest/analytics/validation_failure_data_readiness.py`

---

## Phase 5: User Story 3 - 다음 child 후보로 전진할 수 있게 완료 표식을 남긴다 (Priority: P3)

**Goal**: Mark data readiness candidate complete and provide an executable probe.

**Independent Test**: Probe against current sidecars returns `CONTRACT_READY`.

- [x] T010 [US3] Add probe script in `scripts/validation_failure_data_readiness_probe.py`
- [x] T011 [US3] Add completed candidate marker in `specs/128-validation-failure-data-readiness/contracts/data-readiness-contract.md`

---

## Phase 6: Validation, PR, and Handoff

- [x] T012 Run focused pytest for data readiness tests
- [x] T013 Run focused pytest for autonomous-work advancement tests
- [x] T014 Run current sidecar replay from `quickstart.md`
- [x] T015 Run `uv run pytest`
- [x] T016 Run `uv run ruff check src tests`
- [x] T017 Run `git diff --check`
- [x] T018 Run `uv run python scripts/check_handoff_facts.py`
- [x] T019 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T020 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 records the operating change.
2. Phase 2 locks tests and autonomous-work progression.
3. User Story 1 creates the report.
4. User Story 2 records observation and sidecar context.
5. User Story 3 makes the contract runnable and releasable.
6. Phase 6 validates, opens PR, merges, and refreshes handoff.

## Implementation Strategy

Implement the read-only contract first. Do not execute package commands. Use released-work to close this candidate and let autonomous-work choose the next child candidate.
