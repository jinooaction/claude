# Tasks: 자율 루프 품질 폐쇄

**Input**: Design documents from `/specs/081-autonomous-loop-quality-closure/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md, contracts/

**Tests**: Required because this is a grade 2 operating-system change touching autonomous loop reports and workflow triggers.

**Organization**: Tasks are grouped by user story so each slice remains independently verifiable.

## Phase 1: Setup

**Purpose**: Establish traceable SDD artifacts.

- [x] T001 Create `specs/081-autonomous-loop-quality-closure/spec.md`.
- [x] T002 [P] Create `specs/081-autonomous-loop-quality-closure/plan.md`, `research.md`, `data-model.md`, `quickstart.md`, and contract docs.
- [x] T003 Update `.specify/feature.json` to point to `specs/081-autonomous-loop-quality-closure`.

---

## Phase 2: Foundational

**Purpose**: Preserve safety and current behavior before adding fields.

- [x] T004 Read existing autonomous work, money gate alignment, pipeline liveness, and operator status code paths.
- [x] T005 Confirm no open PR is in-flight and work is isolated in a dedicated worktree.

---

## Phase 3: User Story 1 - 다음 세션이 바로 착수한다 (Priority: P1)

**Goal**: Selected work packets explain whether Codex may start autonomously and how to close the work.

**Independent Test**: Unit and integration tests show selected work includes `autonomy_level`, `start_guidance_ko`, and `completion_gates`.

- [x] T006 [P] [US1] Add execution-contract fields and rendering to `src/auto_invest/analytics/autonomous_work_execution.py`.
- [x] T007 [US1] Add regression tests in `tests/unit/test_autonomous_work_execution.py`.

---

## Phase 4: User Story 2 - 관측 시점 차이를 혼동하지 않는다 (Priority: P1)

**Goal**: Aligned waiting reports expose observation-count skew without misclassifying it as a blocker.

**Independent Test**: Money gate alignment tests prove `14/20` and `15/20` inputs produce `SNAPSHOT_SKEW` and still return `ALIGNED_WAITING`.

- [x] T008 [P] [US2] Add observation-count range and snapshot-skew issue logic to `src/auto_invest/analytics/money_gate_alignment.py`.
- [x] T009 [US2] Add regression tests in `tests/unit/test_money_gate_alignment.py`.

---

## Phase 5: User Story 3 - 상태판 뒤 생존 감시가 따라온다 (Priority: P2)

**Goal**: Pipeline liveness can refresh after operator status completes.

**Independent Test**: Workflow tests show `pipeline-liveness.yml` has an `Operator mobile alerts` completion trigger.

- [x] T010 [P] [US3] Add post-operator-status workflow trigger to `.github/workflows/pipeline-liveness.yml`.
- [x] T011 [US3] Add workflow regression test in `tests/unit/test_pipeline_liveness.py`.

---

## Phase 6: Validation and Handoff

**Purpose**: Prove the change and leave current truth for the next session.

- [x] T012 Run focused tests from `specs/081-autonomous-loop-quality-closure/quickstart.md`.
- [x] T013 Run `uv run pytest` and `uv run ruff check src tests`.
- [x] T014 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T015 Create/update PR with risk grade, problem definition, safety boundary review, validation, and handoff notes.
- [ ] T016 Merge when gates pass and refresh `HANDOFF.md` after merge.

## Dependencies & Execution Order

- Setup precedes all implementation.
- US1 and US2 can be implemented in parallel after setup because they touch different modules.
- US3 can be implemented independently after setup.
- Validation runs after all user stories are implemented.

## Implementation Strategy

1. Deliver US1 and US2 first because they remove the operator-facing ambiguity.
2. Add US3 trigger to prevent stale liveness after operator-status.
3. Run focused and full validation before PR and automatic merge.
