# Tasks: Autonomous Sidecar Handoff Liveness Closure

**Input**: Design documents from `/specs/086-autonomous-sidecar-handoff-liveness/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because this is an operating-system behavior change and must be reproducible.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the feature pointer and current evidence baseline.

- [x] T001 Update `.specify/feature.json` to point at `specs/086-autonomous-sidecar-handoff-liveness`.
- [x] T002 Update `CLAUDE.md` Speckit pointer to the spec 086 plan.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Capture the existing satisfied and regressed evidence cases before implementation.

- [x] T003 [P] Add focused unit tests for satisfied and missing agent_ops completion evidence in `tests/unit/test_evolution_loop.py`.
- [x] T004 [P] Add or update probe integration assertions for handoff evidence consumption in `tests/integration/test_evolution_loop_probe.py`.

**Checkpoint**: Tests should describe the repeated-candidate failure before implementation.

---

## Phase 3: User Story 1 - 완료된 agent_ops 후보 반복 발행 차단 (Priority: P1) MVP

**Goal**: `candidate-88a7e7f07361` becomes non-actionable when liveness and handoff evidence are already satisfied.

**Independent Test**: Focused evolution-loop tests pass.

- [x] T005 [US1] Implement agent_ops completion evidence detection in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T006 [US1] Mark the agent_ops candidate `released` when completion evidence is satisfied in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T007 [US1] Suppress released source candidates in `src/auto_invest/analytics/autonomous_work_execution.py`, `src/auto_invest/analytics/promotion_loop.py`, and `src/auto_invest/analytics/candidate_factory.py`.
- [x] T008 [US1] Add downstream regression tests in `tests/unit/test_autonomous_work_execution.py`, `tests/unit/test_promotion_loop.py`, and `tests/unit/test_candidate_factory.py`.
- [x] T009 [US1] Run `uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py tests/unit/test_autonomous_work_execution.py tests/unit/test_promotion_loop.py tests/unit/test_candidate_factory.py`.

---

## Phase 4: User Story 2 - 완료 후보 장부가 후보 소비를 재현 (Priority: P2)

**Goal**: `released-work` can consume this completed autonomous candidate from Speckit artifacts.

**Independent Test**: Local released-work probe includes `candidate-88a7e7f07361`.

- [x] T010 [US2] Ensure `specs/086-autonomous-sidecar-handoff-liveness/contracts/agent-ops-liveness-closure.md` contains `completed_candidate_id: candidate-88a7e7f07361`.

---

## Phase 5: User Story 3 - 안전 경계와 인계 의미가 명확함 (Priority: P3)

**Goal**: The next session can understand the change without rediscovering the same facts.

**Independent Test**: Grade-2 validation and PR quality gate pass.

- [x] T011 [US3] Document safety boundary and rollback meaning in `plan.md`, `quickstart.md`, and `contracts/agent-ops-liveness-closure.md`.
- [x] T012 [US3] Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.

---

## Final Phase: Polish & Cross-Cutting Concerns

- [x] T013 Run `uv run pytest`.
- [x] T014 Run `uv run ruff check src tests`.
- [x] T015 Run `git diff --check`.
- [x] T016 Close post-merge stale-sidecar race by feeding current released-work evidence into promotion and candidate-factory workflows.
- [x] T017 Add stale released-work regression tests for promotion/factory suppression.

## Completion Evidence Outside Released-Work Checklist

Run after all checkboxes above are closed:

- `uv run python scripts/released_work_probe.py --repo-root . --run-id local-086 --commit "$(git rev-parse HEAD)" --json-out /tmp/released_work_086.json --summary-out /tmp/released_work_086.md`
- Confirm `/tmp/released_work_086.json` contains `candidate-88a7e7f07361` with `status: released`.
- Create the PR with risk grade, problem definition, exploration evidence, validation, harness, safety boundary, and handoff notes.
- Merge when gates pass and post-merge sidecars confirm the candidate no longer repeats.
- Refresh `HANDOFF.md` and add a milestone handoff if operating truth changed.

## Dependencies & Execution Order

- Phase 1 before all implementation.
- Phase 2 tests before Phase 3 implementation.
- Phase 3 before released-work reproduction.
- Phase 5 and final validation before PR/merge.

## Parallel Opportunities

- T003 and T004 touch different test scopes and can be prepared independently.
- Documentation and PR body drafting can happen after focused behavior is stable.

## Implementation Strategy

1. Make the smallest candidate-state change in `evolution_loop.py`.
2. Prove both satisfied and regressed evidence paths.
3. Close the released-work marker only after implementation tasks are complete.
4. Use full grade-2 validation before PR and automatic merge.
