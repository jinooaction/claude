# Tasks: Macro Candidate Map Regenerator

**Input**: Design documents from `specs/093-macro-candidate-map-regenerator/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are required because this changes autonomous work selection behavior.

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/093-macro-candidate-map-regenerator/`

---

## Phase 2: Foundational Tests

- [x] T003 [P] Add failing unit coverage for regenerator candidate selection in `tests/unit/test_autonomous_work_execution.py`
- [x] T004 [P] Add failing unit coverage for post-regenerator map-derived candidate selection in `tests/unit/test_autonomous_work_execution.py`
- [x] T005 [P] Add failing report contract coverage for `macro_candidate_map` JSON/Markdown in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - 후보 고갈 뒤 다음 실행 후보 재생성 (Priority: P1)

**Goal**: Closed queue after frontier/regenerator release produces a new execution-ready candidate.

**Independent Test**: Focused unit tests select `candidate-macro-candidate-map-regenerator` before its release and `candidate-investment-edge-frontier-map` after its release.

- [x] T006 [US1] Add candidate constants and generated packet sequencing in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T007 [US1] Preserve existing priority ordering for regular, repair, blocked, and operator-approval candidates in `src/auto_invest/analytics/autonomous_work_execution.py`

---

## Phase 4: User Story 2 - 후보 영역별 거시 지도 제공 (Priority: P2)

**Goal**: JSON and Markdown explain the domain map that caused regenerated candidate selection.

**Independent Test**: Report output includes deterministic `macro_candidate_map` and `## 거시 후보 지도`.

- [x] T008 [US2] Add macro candidate map data model and serialization in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T009 [US2] Render macro candidate map in Markdown in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T010 [US2] Verify probe JSON/Markdown contract in `tests/integration/test_autonomous_work_execution_probe.py`

---

## Phase 5: User Story 3 - 안전 경계와 완료 후보 소비 유지 (Priority: P3)

**Goal**: Regenerated candidates stay read-only and released-work prevents repetition.

**Independent Test**: Safety/operator candidates still win, and released regenerated candidates are skipped.

- [x] T011 [US3] Add released-work skip logic for regenerated map candidates in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T012 [US3] Confirm safety boundary and completion marker contract in `specs/093-macro-candidate-map-regenerator/contracts/macro-candidate-map-regenerator.md`

---

## Phase 6: Validation and Release

- [x] T013 Run focused unit tests: `uv run pytest tests/unit/test_autonomous_work_execution.py -q`
- [x] T014 Run probe integration tests: `uv run pytest tests/integration/test_autonomous_work_execution_probe.py -q`
- [x] T015 Run local sidecar replay from `specs/093-macro-candidate-map-regenerator/quickstart.md`
- [x] T016 Run full tests: `uv run pytest`
- [x] T017 Run lint and repository gates: `uv run ruff check src tests`, `git diff --check`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`
- [x] T018 Prepare commit, push, PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

- T001-T002 before implementation.
- T003-T005 before T006-T011.
- T006-T007 complete User Story 1.
- T008-T010 complete User Story 2.
- T011-T012 complete User Story 3.
- T013-T018 are release gates.

## Parallel Opportunities

- T002 can run independently of pointer updates.
- T003-T005 can be drafted together because they touch related assertions but different scenarios.
- T013-T014 can run in parallel once implementation is complete.

## Implementation Strategy

Implement MVP first: make the closed queue produce the regenerator candidate, then prove the regenerator's own release advances to a map-derived investment-edge frontier candidate. Add reporting after the selection behavior is stable, then run the full gate and handoff refresh.
