# Tasks: 레짐·성과 후보 점수화

**Input**: Design documents from `/specs/082-regime-performance-candidate-scoring/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a grade 2 autonomous operating-loop scoring change.

## Phase 1: Setup

**Purpose**: Keep SDD and active feature pointers current.

- [x] T001 Create and validate SDD artifacts in `specs/082-regime-performance-candidate-scoring/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 082.

---

## Phase 2: Foundation

**Purpose**: Understand existing scoring and evidence surfaces before changing behavior.

- [x] T003 Read `src/auto_invest/analytics/evolution_loop.py`, `scripts/evolution_loop_probe.py`, `tests/unit/test_evolution_loop.py`, and `tests/integration/test_evolution_loop_probe.py`.
- [x] T004 Confirm latest `regime-stratify` and `promote-readiness` sidecar shapes from automation branches.

---

## Phase 3: User Story 1 - 성과 표면을 후보 점수에 반영 (Priority: P1)

**Goal**: Analysis candidates use regime and performance evidence in scoring.

**Independent Test**: Unit tests prove fresh performance evidence is included and deterministically affects candidate scoring.

- [x] T005 [P] [US1] Add fresh `promote-readiness` fixture coverage in `tests/fixtures/evolution_loop/fresh/promote-readiness.md`.
- [x] T006 [P] [US1] Add unit tests for analysis candidate evidence refs and score behavior in `tests/unit/test_evolution_loop.py`.
- [x] T007 [US1] Add `promote-readiness` evidence requirement and scoring logic in `src/auto_invest/analytics/evolution_loop.py`.

---

## Phase 4: User Story 2 - 성과 표면 이상을 과신하지 않음 (Priority: P2)

**Goal**: Missing or stale performance evidence reduces confidence instead of creating false conviction.

**Independent Test**: Unit tests prove missing/stale performance sidecars produce sidecar freshness dependency.

- [x] T008 [P] [US2] Add stale or missing performance fixture coverage under `tests/fixtures/evolution_loop/`.
- [x] T009 [US2] Add unit tests for missing/stale/setup-error-like `promote-readiness` behavior in `tests/unit/test_evolution_loop.py`.
- [x] T010 [US2] Implement freshness/error handling for performance evidence in `src/auto_invest/analytics/evolution_loop.py`.

---

## Phase 5: User Story 3 - 다음 루프가 새 입력을 수집함 (Priority: P3)

**Goal**: The probe manifest and workflow contract include the new evidence surface.

**Independent Test**: Integration tests prove manifest and workflow contracts include `promote-readiness` without adding forbidden effects.

- [x] T011 [P] [US3] Add manifest assertions for `promote-readiness` in `tests/integration/test_evolution_loop_probe.py`.
- [x] T012 [US3] Confirm workflow contract remains read-only in `tests/integration/test_evolution_loop_probe.py`.

---

## Phase 6: Validation and Handoff

**Purpose**: Prove behavior and prepare PR/merge/handoff.

- [x] T013 Run focused tests from `quickstart.md`.
- [x] T014 Run `uv run pytest` and `uv run ruff check src tests`.
- [x] T015 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
- [ ] T016 Create PR with risk grade, problem definition, safety boundary review, validation, and handoff notes.
- [ ] T017 Merge when gates pass and refresh `HANDOFF.md` after merge.

## Dependencies & Execution Order

- Phase 1 and 2 precede implementation.
- US1 must land before US2 because missing/stale behavior modifies the same candidate scoring surface.
- US3 can be implemented after the evidence requirement is added.
- Validation runs after all stories complete.

## Implementation Strategy

1. Update fixtures and tests first.
2. Add the evidence requirement and deterministic score adjustment.
3. Verify manifest/workflow contract.
4. Run full validation and handoff refresh.
