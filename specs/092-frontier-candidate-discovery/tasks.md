# Tasks: Frontier Candidate Discovery

**Input**: Design documents from `specs/092-frontier-candidate-discovery/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because this is an operating automation selection-behavior change.

**Organization**: Tasks are grouped by user story so each behavior can be verified independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish SDD artifacts and active feature pointers.

- [x] T001 Create spec 092 SDD artifacts in `specs/092-frontier-candidate-discovery/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` to point at spec 092.

---

## Phase 2: User Story 1 - 후보 고갈을 실행 가능한 frontier 작업으로 드러내기 (Priority: P1)

**Goal**: Closed queues emit an execution-ready frontier discovery candidate.

**Independent Test**: Focused unit test selects `candidate-autonomous-frontier-discovery` when all prior macro candidates are released.

- [x] T003 [P] [US1] Add focused frontier selection tests in `tests/unit/test_autonomous_work_execution.py`.
- [x] T004 [US1] Add frontier discovery constants and generated packet helper in `src/auto_invest/analytics/autonomous_work_execution.py`.
- [x] T005 [US1] Wire frontier discovery after existing macro candidate sequence in `src/auto_invest/analytics/autonomous_work_execution.py`.

---

## Phase 3: User Story 2 - 고갈 원인과 다음 행동을 재현 가능하게 남기기 (Priority: P2)

**Goal**: Frontier candidate explains why the queue is exhausted and what inputs are required next.

**Independent Test**: Frontier packet reason, action, required inputs, and source refs include queue counts and relevant sidecar surfaces.

- [x] T006 [US2] Add assertions for frontier reason, next action, required inputs, and source refs in `tests/unit/test_autonomous_work_execution.py`.
- [x] T007 [US2] Run latest sidecar replay from `specs/092-frontier-candidate-discovery/quickstart.md`.

---

## Phase 4: User Story 3 - 안전 경계와 완료 장부를 보존하기 (Priority: P3)

**Goal**: Close this frontier candidate through released-work without touching money or safety boundaries.

**Independent Test**: Released-work records `candidate-autonomous-frontier-discovery` after tasks complete.

- [x] T008 [US3] Add completion contract marker in `specs/092-frontier-candidate-discovery/contracts/frontier-candidate-discovery.md`.
- [x] T009 [US3] Run focused pytest for autonomous work execution and probe tests.
- [x] T010 [US3] Run released-work reproduction from `quickstart.md`.
- [x] T011 [US3] Run full pytest, ruff, diff check, HANDOFF fact check, and strict harness.
- [x] T012 [US3] Prepare PR quality-gate body with risk grade, problem definition, safety boundary, validation, and handoff notes.

## Operational Closure Outside Released-Work Scan

These are required by repository operating rules, but they are not Speckit implementation checkboxes because `released-work` treats any unchecked checkbox in `tasks.md` as incomplete work.

- Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- Check post-merge sidecar/deploy relevance and refresh HANDOFF if operating truth changed.

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 must complete before code changes.
- User Story 1 must complete before User Story 2 can prove explanatory fields.
- User Story 3 depends on the focused behavior and reproduction checks.

### Parallel Opportunities

- T003 touches only tests and can be reviewed independently from the generated packet helper.

## Implementation Strategy

1. Add tests that prove queue exhaustion selects the frontier discovery candidate.
2. Implement the pure generated packet rule without changing broker, money path, or safety gates.
3. Verify latest sidecar replay and released-work closure.
4. Create and merge PR, then refresh HANDOFF in a follow-up PR.
