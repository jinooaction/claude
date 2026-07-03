# Tasks: Autonomous Growth Objective Calibration

**Input**: Design documents from `specs/091-autonomous-growth-objective-calibration/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because this is an operating automation schema and decision-surface change.

**Organization**: Tasks are grouped by user story so each behavior can be verified independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish SDD artifacts and active feature pointers.

- [x] T001 Create spec 091 SDD artifacts in `specs/091-autonomous-growth-objective-calibration/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` to point at spec 091.

---

## Phase 2: User Story 1 - 후보 선택 근거를 측정 가능한 목적 함수로 남기기 (Priority: P1)

**Goal**: Autonomous-work reports explain selected work through deterministic objective components.

**Independent Test**: Same evidence produces identical `objective_calibration` output.

- [x] T003 [P] [US1] Add focused objective-calibration unit tests in `tests/unit/test_autonomous_work_execution.py`.
- [x] T004 [US1] Add objective calibration dataclasses and pure scoring helpers in `src/auto_invest/analytics/autonomous_work_execution.py`.
- [x] T005 [US1] Include objective calibration in `AutonomousWorkExecutionReport.to_dict()`.

---

## Phase 3: User Story 2 - 탐색 예산과 중단 조건을 출력 계약으로 고정하기 (Priority: P2)

**Goal**: JSON and Markdown reports expose exploration budget, stop conditions, and learning metrics.

**Independent Test**: Probe JSON and Markdown both include the objective calibration contract.

- [x] T006 [US2] Add Markdown rendering for objective calibration in `AutonomousWorkExecutionReport.as_markdown()`.
- [x] T007 [US2] Add probe integration coverage for JSON and Markdown output.
- [x] T008 [US2] Run the quickstart probe reproduction.

---

## Phase 4: User Story 3 - 안전 경계와 완료 장부를 보존하기 (Priority: P3)

**Goal**: Close this macro candidate through released-work without touching money or safety boundaries.

**Independent Test**: Released-work records `candidate-autonomous-growth-objective-calibration` after tasks complete.

- [x] T009 [US3] Add completion contract marker in `specs/091-autonomous-growth-objective-calibration/contracts/autonomous-growth-objective-calibration.md`.
- [x] T010 [US3] Run focused pytest for autonomous work execution and probe tests.
- [x] T011 [US3] Run released-work reproduction from `quickstart.md`.
- [x] T012 [US3] Run full pytest, ruff, diff check, HANDOFF fact check, and strict harness.
- [x] T013 [US3] Prepare PR quality-gate body with risk grade, problem definition, safety boundary, validation, and handoff notes.

## Operational Closure Outside Released-Work Scan

These are required by repository operating rules, but they are not Speckit implementation checkboxes because `released-work` treats any unchecked checkbox in `tasks.md` as incomplete work.

- Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- Check post-merge sidecar/deploy relevance and refresh HANDOFF if operating truth changed.

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 must complete before code changes.
- User Story 1 must complete before User Story 2 can render the contract.
- User Story 3 depends on the focused behavior and reproduction checks.

### Parallel Opportunities

- T003 and T007 touch tests and can be reviewed independently from the scoring helper implementation.

## Implementation Strategy

1. Add tests that describe deterministic objective calibration and safety-margin behavior.
2. Implement the pure report-scoring helpers without changing broker, money path, or ranking gates.
3. Add Markdown/probe coverage and mark tasks complete after validation.
4. Create and merge PR, then refresh HANDOFF in a follow-up PR.
