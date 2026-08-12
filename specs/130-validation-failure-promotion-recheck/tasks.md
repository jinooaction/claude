# Tasks: Validation Failure Promotion Recheck Contract

**Input**: Design documents from `specs/130-validation-failure-promotion-recheck/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/130-validation-failure-promotion-recheck/`
- [x] T002 Update active feature pointer in `.specify/feature.json`
- [x] T003 Update active plan pointer in `CLAUDE.md`

---

## Phase 2: Foundational

- [x] T004 [P] Add focused promotion-recheck tests in `tests/unit/test_validation_failure_promotion_recheck.py`
- [x] T005 [P] Add autonomous-work non-repeat test in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - 억제된 실패 후보를 근거 있게 유지한다 (Priority: P1)

**Goal**: Keep rejected candidates suppressed when current failure evidence is unchanged.

**Independent Test**: Focused promotion-recheck tests mark the current two candidates as `SUPPRESSION_ACTIVE`.

- [x] T006 [US1] Implement promotion-recheck report models in `src/auto_invest/analytics/validation_failure_promotion_recheck.py`
- [x] T007 [US1] Join learning ledger, autonomous-promotion, and candidate-result evidence in `src/auto_invest/analytics/validation_failure_promotion_recheck.py`

---

## Phase 4: User Story 2 - 새 증거가 생기면 다시 열 조건을 명확히 한다 (Priority: P2)

**Goal**: Record deterministic recheck conditions without proposing live action.

**Independent Test**: Focused tests prove a changed result status allows recheck for that candidate only.

- [x] T008 [US2] Add stable failure fingerprint and recheck condition generation in `src/auto_invest/analytics/validation_failure_promotion_recheck.py`
- [x] T009 [US2] Add Markdown and JSON artifact writer in `src/auto_invest/analytics/validation_failure_promotion_recheck.py`

---

## Phase 5: User Story 3 - 검증 실패 child 묶음을 닫고 반복 선택을 막는다 (Priority: P3)

**Goal**: Mark promotion-recheck candidate complete and provide an executable probe.

**Independent Test**: Released promotion-recheck candidate is not selected again.

- [x] T010 [US3] Add probe script in `scripts/validation_failure_promotion_recheck_probe.py`
- [x] T011 [US3] Add completed candidate marker in `specs/130-validation-failure-promotion-recheck/contracts/promotion-recheck-contract.md`

---

## Phase 6: Validation, PR, and Handoff

- [x] T012 Run focused pytest for promotion-recheck tests
- [x] T013 Run focused pytest for autonomous-work non-repeat test
- [x] T014 Run current sidecar replay from `quickstart.md`
- [x] T015 Run `uv run pytest`
- [x] T016 Run `uv run ruff check src tests`
- [x] T017 Run `git diff --check`
- [x] T018 Run `uv run python scripts/check_handoff_facts.py`
- [x] T019 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T020 Prepare PR body, PR quality gate evidence, release replay evidence, and HANDOFF refresh plan

## Dependencies & Execution Order

1. Phase 1 records the operating change.
2. Phase 2 locks tests and autonomous-work progression.
3. User Story 1 creates the suppression contract.
4. User Story 2 records recheck conditions.
5. User Story 3 makes the contract runnable and releasable.
6. Phase 6 validates, opens PR, merges, and refreshes handoff.

## Implementation Strategy

Implement the read-only contract first. Do not execute package commands. Use released-work to close this final validation-failure child and prevent repeat selection.
