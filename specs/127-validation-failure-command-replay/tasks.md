# Tasks: Validation Failure Command Replay Contract

**Input**: Design documents from `specs/127-validation-failure-command-replay/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/127-validation-failure-command-replay/`
- [x] T002 Update active feature pointer in `.specify/feature.json`
- [x] T003 Update active plan pointer in `CLAUDE.md`

---

## Phase 2: Foundational

- [x] T004 [P] Add focused command replay tests in `tests/unit/test_validation_failure_command_replay.py`
- [x] T005 [P] Expose candidate-result command safety classification in `src/auto_invest/analytics/candidate_result_executor.py`

---

## Phase 3: User Story 1 - 실패 명령을 기계 판독 계약으로 고정한다 (Priority: P1)

**Goal**: Produce deterministic command replay rows for current retryable validation failures.

**Independent Test**: Focused command replay tests produce four rows for the two current packages.

- [x] T006 [US1] Implement command replay report models in `src/auto_invest/analytics/validation_failure_command_replay.py`
- [x] T007 [US1] Join package commands with result evidence in `src/auto_invest/analytics/validation_failure_command_replay.py`

---

## Phase 4: User Story 2 - 안전 재현 범위를 명령별로 판정한다 (Priority: P2)

**Goal**: Classify no-live replay safety per command without executing commands.

**Independent Test**: Unsafe live command fragments produce `BLOCKED_UNSAFE_COMMAND`.

- [x] T008 [US2] Add command safety and missing execution evidence fields in `src/auto_invest/analytics/validation_failure_command_replay.py`
- [x] T009 [US2] Add Markdown and JSON artifact writer in `src/auto_invest/analytics/validation_failure_command_replay.py`

---

## Phase 5: User Story 3 - 다음 child 후보로 전진할 수 있게 완료 표식을 남긴다 (Priority: P3)

**Goal**: Mark command replay candidate complete and provide an executable probe.

**Independent Test**: Probe against current sidecars returns `CONTRACT_READY`.

- [x] T010 [US3] Add probe script in `scripts/validation_failure_command_replay_probe.py`
- [x] T011 [US3] Add completed candidate marker in `specs/127-validation-failure-command-replay/contracts/command-replay-contract.md`

---

## Phase 6: Validation, PR, and Handoff

- [x] T012 Run focused pytest for command replay tests
- [x] T013 Run focused pytest for autonomous-work advancement tests
- [x] T014 Run current sidecar replay from `quickstart.md`
- [x] T015 Run `uv run pytest`
- [x] T016 Run `uv run ruff check src tests`
- [x] T017 Run `git diff --check`
- [x] T018 Run `uv run python scripts/check_handoff_facts.py`
- [x] T019 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T020 Prepare PR body, PR quality gate evidence, release replay evidence, and HANDOFF refresh

## Dependencies & Execution Order

1. Phase 1 records the operating change.
2. Phase 2 locks tests and safety classification.
3. User Story 1 creates the report.
4. User Story 2 preserves command-level safety.
5. User Story 3 makes the contract runnable and releasable.
6. Phase 6 validates, opens PR, merges, and refreshes handoff.

## Implementation Strategy

Implement the read-only contract first. Do not execute package commands. Use released-work to close this candidate and let autonomous-work choose the next child candidate.
