# Tasks: Autonomous Evolution Loop

**Input**: Design documents from `/specs/067-autonomous-evolution-loop/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md, contracts/

**Tests**: Required because this creates a new autonomous operating workflow, even though the first slice is read-only.

**Organization**: Tasks are grouped by user story so each slice can be implemented and verified independently.

## Phase 1: Setup

**Purpose**: Establish fixtures, module shell, and sidecar evidence manifest.

- [x] T001 Create evidence fixtures for fresh, stale, missing, and pre-fix sidecar inputs in `tests/fixtures/evolution_loop/`.
- [x] T002 Create pure data models and constants in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T003 Create probe skeleton with `--manifest`, text, and JSON modes in `scripts/evolution_loop_probe.py`.
- [x] T004 Add CLI placeholder or command wiring for `evolution-scan` in `src/auto_invest/cli.py`.

---

## Phase 2: Foundational

**Purpose**: Shared safety classification and secret-safe output required by all stories.

- [x] T005 [P] Implement safety-surface classification for orders, capital, whitelist, caps, secrets, deploy, kernel, live strategy, and paid-service candidates in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T006 [P] Implement secret/account masking assertions for summaries in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T007 [P] Add unit tests for safety classification in `tests/unit/test_evolution_loop.py`.
- [x] T008 [P] Add unit tests for masking and no-secret report output in `tests/unit/test_evolution_loop.py`.

**Checkpoint**: No candidate can be automatically actionable before safety classification exists.

---

## Phase 3: User Story 1 - 전 영역 고레버리지 돌파 후보를 자동으로 발굴한다 (Priority: P1) MVP

**Goal**: Produce a deterministic, ordered breakthrough candidate list from current evidence surfaces.

**Independent Test**: Fixed fixtures produce the same candidate order and safety classifications across repeated runs.

- [x] T009 [P] [US1] Implement domain registry covering at least eight domains in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T010 [US1] Implement evidence parsing for money-path, micro GTAA, reassignment, pipeline-liveness, handoff summary, and released spec signals in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T011 [US1] Implement breakthrough candidate generation and deterministic scoring by long-term profit capacity, evidence confidence, capital-path alignment, safety preservation, learning velocity, and compounding value in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T012 [P] [US1] Add unit tests for deterministic candidate generation in `tests/unit/test_evolution_loop.py`.
- [x] T013 [P] [US1] Add integration tests for `scripts/evolution_loop_probe.py --json` in `tests/integration/test_evolution_loop_probe.py`.

**Checkpoint**: The loop can report top high-leverage breakthrough work without writing trading config.

---

## Phase 4: User Story 2 - 돌파 후보를 안전한 실험으로 바꾼다 (Priority: P1)

**Goal**: Convert selected candidates into bounded experiment plans with success and failure criteria.

**Independent Test**: Candidate fixtures produce experiment plans with goal, non-goal, data, metrics, failure criteria, and allowed stage.

- [x] T014 [US2] Implement experiment-plan generation in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T015 [P] [US2] Add tests for strategy research, execution-quality, and stale-evidence experiment plans in `tests/unit/test_evolution_loop.py`.
- [x] T016 [US2] Ensure thin-sample candidates become observe/wait plans instead of change plans in `src/auto_invest/analytics/evolution_loop.py`.

**Checkpoint**: Every active candidate has a bounded next action.

---

## Phase 5: User Story 3 - 검증된 돌파 후보만 기존 안전 게이트로 승격한다 (Priority: P1)

**Goal**: Promote only evidence-backed candidates, and route money-path or strategy changes through existing gates.

**Independent Test**: Evidence packages produce discard, observe, create-spec, open-pr, feed-existing-gate, or operator-review decisions without bypassing reassignment or capital ladder.

- [x] T017 [US3] Implement evidence-package validation in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T018 [US3] Implement promotion-decision rules in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T019 [P] [US3] Add tests proving strategy-swap candidates route to existing reassignment gates in `tests/unit/test_evolution_loop.py`.
- [x] T020 [P] [US3] Add tests proving capital-scaling candidates route to existing capital ladder or operator review in `tests/unit/test_evolution_loop.py`.

**Checkpoint**: Proven candidates can advance, but the loop still cannot move money directly.

---

## Phase 6: User Story 4 - 루프의 학습 기록과 정지 상태를 남긴다 (Priority: P2)

**Goal**: Publish a latest-run report and durable learning ledger, and expose loop liveness.

**Independent Test**: Rejected candidates do not reactivate without new evidence, and the sidecar appears in pipeline liveness.

- [x] T021 [US4] Implement learning-ledger state transitions in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T022 [US4] Implement Korean markdown and JSON latest-run rendering in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T023 [US4] Add `autonomous-evolution` to `default_specs()` in `src/auto_invest/analytics/pipeline_liveness.py`.
- [x] T024 [P] [US4] Add ledger lifecycle tests in `tests/unit/test_evolution_loop.py`.
- [x] T025 [P] [US4] Add liveness registry regression in `tests/unit/test_pipeline_liveness.py`.

**Checkpoint**: Future sessions can read one sidecar and avoid repeating rejected work.

---

## Phase 7: Workflow and Sidecar

**Purpose**: Run the read-only loop on schedule and publish durable evidence.

- [x] T026 Add `.github/workflows/autonomous-evolution-loop.yml` to collect evidence, run the probe, and publish `automation/autonomous-evolution-last-run`.
- [x] T027 Add workflow shell/YAML validation tests or focused static checks in `tests/integration/test_evolution_loop_probe.py`.
- [x] T028 Verify workflow summary in `.github/workflows/autonomous-evolution-loop.yml` states that orders, capital, whitelist, caps, and live strategy were unchanged.

---

## Phase 8: Validation and Handoff

**Purpose**: Prove the change and leave current truth for the next session.

- [x] T029 Run focused tests: `uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py tests/unit/test_pipeline_liveness.py`.
- [x] T030 Run `uv run pytest` and `uv run ruff check src tests` for `src/` and `tests/`.
- [x] T031 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T032 Open a PR using `.github/pull_request_template.md` with risk grade, problem definition, safety boundary review, validation, and handoff notes.
- [ ] T033 Merge when gates pass, then refresh `HANDOFF.md` if implementation changes operating truth.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on foundational safety classification.
- **User Story 2 (Phase 4)**: Depends on User Story 1 candidates.
- **User Story 3 (Phase 5)**: Depends on evidence packages from User Story 2.
- **User Story 4 (Phase 6)**: Depends on candidate lifecycle states from User Stories 1-3.
- **Workflow (Phase 7)**: Depends on core, probe, and rendering.
- **Validation (Phase 8)**: Depends on selected implementation phases.

### Parallel Opportunities

- T005-T008 can run in parallel after setup.
- T012 and T013 can run in parallel after candidate generation behavior is defined.
- T019 and T020 can run in parallel after promotion rules exist.
- T024 and T025 can run in parallel after ledger and liveness behavior are defined.

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete User Story 1 candidate discovery.
3. Validate read-only probe output against fixtures.
4. Only then add experiment planning, promotion decisions, ledger, and workflow publishing.
