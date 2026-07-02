# Tasks: 주문 거부·체결 품질 손익 관측

**Input**: Design documents from `/specs/083-rejected-order-execution-quality/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a grade 2 autonomous operating-loop evidence and workflow change.

## Phase 1: Setup

**Purpose**: Keep SDD and active feature pointers current.

- [x] T001 Create and validate SDD artifacts in `specs/083-rejected-order-execution-quality/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 083.

---

## Phase 2: Foundation

**Purpose**: Understand and preserve existing rejected-order monitor behavior.

- [x] T003 Read existing 064번 monitor, micro GTAA workflow, evolution loop, liveness registry, and latest sidecar examples.
- [x] T004 Confirm the latest sidecar evidence shape for `opportunity_monitor.json`, `opportunity_history.json`, micro GTAA `LAST_RUN.md`, and KIS smoke `LAST_RUN.md`.

---

## Phase 3: User Story 1 - 실행 품질 증거를 한 패키지로 본다 (Priority: P1)

**Goal**: Build a deterministic execution quality package from existing sidecars only.

**Independent Test**: Unit and probe tests prove monitor, history, broker rejection, smoke, and Markdown output are produced without broker access.

- [x] T005 [P] [US1] Add execution-quality fixtures under `tests/fixtures/execution_quality/`.
- [x] T006 [P] [US1] Add unit tests in `tests/unit/test_execution_quality.py`.
- [x] T007 [US1] Implement `src/auto_invest/analytics/execution_quality.py`.
- [x] T008 [US1] Implement `scripts/execution_quality_probe.py`.
- [x] T009 [US1] Add probe integration tests in `tests/integration/test_execution_quality_probe.py`.
- [x] T010 [US1] Add `.github/workflows/execution-quality.yml` with read-only sidecar collection and publication.

---

## Phase 4: User Story 2 - 자율 성장 루프가 실행 품질 표면을 소비한다 (Priority: P1)

**Goal**: The autonomous evolution loop consumes the new package and keeps `candidate-dff4f9344b02` stable.

**Independent Test**: Evolution tests prove manifest inclusion, evidence refs, and missing/stale dependency behavior.

- [x] T011 [P] [US2] Add evolution fixture coverage for fresh and missing `execution-quality`.
- [x] T012 [US2] Update `src/auto_invest/analytics/evolution_loop.py`.
- [x] T013 [US2] Update `tests/unit/test_evolution_loop.py`.
- [x] T014 [US2] Update `tests/integration/test_evolution_loop_probe.py`.
- [x] T015 [US2] Update `.github/workflows/autonomous-evolution-loop.yml` path filters if needed.

---

## Phase 5: User Story 3 - 새 sidecar의 생존을 감시한다 (Priority: P2)

**Goal**: Pipeline liveness tracks execution-quality as a non-critical sidecar.

**Independent Test**: Liveness unit and probe tests prove registry and manifest inclusion.

- [x] T016 [US3] Update `src/auto_invest/analytics/pipeline_liveness.py`.
- [x] T017 [US3] Update `tests/unit/test_pipeline_liveness.py`.
- [x] T018 [US3] Update `tests/integration/test_pipeline_liveness_probe.py`.

---

## Phase 6: Validation and Handoff

**Purpose**: Prove behavior and prepare PR/merge/handoff.

- [x] T019 Run focused tests from `quickstart.md`.
- [x] T020 Run `uv run pytest` and `uv run ruff check src tests`.
- [x] T021 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T022 Create PR with risk grade, problem definition, safety boundary review, validation, and handoff notes.
- [x] T023 Merge when gates pass and refresh `HANDOFF.md` after merge.

## Dependencies & Execution Order

- Phase 1 and 2 precede implementation.
- US1 must land before US2 and US3 because both consume the new sidecar.
- US2 and US3 can proceed independently after the probe contract exists.
- Validation runs after all stories complete.

## Implementation Strategy

1. Add fixtures and tests first.
2. Build the pure execution-quality core and probe.
3. Wire workflow publication.
4. Wire autonomous evolution and liveness consumption.
5. Run focused and full validation before PR and merge.
