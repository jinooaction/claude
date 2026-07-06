# Tasks: Public Data Input Quality Contract

**Input**: Design documents from `/specs/099-public-data-input-quality-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-data-input-quality-contract.md
**Tests**: Required for every user story because this feature changes autonomous work selection/reporting behavior.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature artifacts and existing sidecar contracts before implementation.

- [x] T001 Confirm `specs/099-public-data-input-quality-contract/plan.md` has no template placeholders and records risk grade 2.
- [x] T002 [P] Add the released-work completed marker for `candidate-public-data-input-quality-contract` in `specs/099-public-data-input-quality-contract/spec.md`.
- [x] T003 [P] Inspect existing autonomous data evidence candidate flow in `src/auto_invest/analytics/autonomous_work_execution.py` and related tests in `tests/unit/test_autonomous_work_execution.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the read-only report model and parser that all user stories use.

- [x] T004 Create `src/auto_invest/analytics/public_data_input_quality.py` with evidence input definitions, report dataclasses, status constants, and JSON/Markdown serialization helpers.
- [x] T005 [P] Add parser coverage in `tests/unit/test_public_data_input_quality.py` for public-data summary, regime summary, regime timeline, regime-stratify, pipeline-liveness, released-work, and capital-path readiness evidence.
- [x] T006 [P] Add `scripts/public_data_input_quality_probe.py` to read a manifest of sidecar snapshots and emit the contract report.
- [x] T007 Add integration coverage in `tests/integration/test_public_data_input_quality_probe.py` for manifest replay and repository-root mode.

**Checkpoint**: The report can be generated from sidecar files without network calls, broker calls, secret reads, or durable writes.

---

## Phase 3: User Story 1 - 공개 데이터 입력 품질을 한눈에 판정한다 (Priority: P1)

**Goal**: Produce a deterministic `CONTRACT_READY` report when public-data, regime, regime timeline, regime-stratify, pipeline-liveness, released-work, and capital-path readiness evidence is complete.

**Independent Test**: Run the unit success case and the probe integration success case, then replay the probe against current automation sidecars.

- [x] T008 [US1] Implement the ready-state quality gates in `src/auto_invest/analytics/public_data_input_quality.py`.
- [x] T009 [P] [US1] Cover the ready-state JSON contract and Markdown report in `tests/unit/test_public_data_input_quality.py`.
- [x] T010 [US1] Verify `scripts/public_data_input_quality_probe.py --repo-root . --format json` returns `CONTRACT_READY` on current sidecar evidence when inputs are healthy.

**Checkpoint**: User Story 1 is independently functional.

---

## Phase 4: User Story 2 - 입력 품질 부족을 WAIT/BLOCKED로 분리한다 (Priority: P2)

**Goal**: Distinguish transient observation gaps from blocking input quality failures without touching the money path.

**Independent Test**: Run unit cases that force stale/missing liveness into `OBSERVATION_WAIT` and malformed/failing data quality into `BLOCKED`.

- [x] T011 [US2] Implement `OBSERVATION_WAIT` and `BLOCKED` aggregation rules in `src/auto_invest/analytics/public_data_input_quality.py`.
- [x] T012 [P] [US2] Add unit tests for liveness wait, low regime-stratify coverage, missing evidence, malformed evidence, and failed cross-check evidence in `tests/unit/test_public_data_input_quality.py`.
- [x] T013 [US2] Ensure the report always includes money-path safety fields showing no broker/order/capital mutation.

**Checkpoint**: User Story 2 is independently functional.

---

## Phase 5: User Story 3 - 완료 후보를 닫고 다음 데이터 후보로 전진한다 (Priority: P3)

**Goal**: Mark `candidate-public-data-input-quality-contract` complete and advance autonomous-work to the next unreleased data evidence frontier candidate.

**Independent Test**: Run autonomous-work unit tests with released-work evidence that includes the completed marker and verify the selected candidate advances to the regime timeline coverage candidate.

- [x] T014 [US3] Extend data evidence frontier selection in `src/auto_invest/analytics/autonomous_work_execution.py` so the completed public-data input-quality candidate releases the frontier entry.
- [x] T015 [P] [US3] Add autonomous-work unit coverage in `tests/unit/test_autonomous_work_execution.py` for advancement from `candidate-public-data-input-quality-contract` to the next data evidence candidate.
- [x] T016 [US3] Re-run `scripts/released_work_probe.py` and `scripts/autonomous_work_execution_probe.py` locally to confirm the completion marker is detected and the next candidate is selected.

**Checkpoint**: User Story 3 is independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish validation, PR quality evidence, and handoff safety.

- [x] T017 Run focused validation: `uv run pytest tests/unit/test_public_data_input_quality.py tests/integration/test_public_data_input_quality_probe.py tests/unit/test_autonomous_work_execution.py`.
- [x] T018 Run full validation: `uv run pytest` and `uv run ruff check src tests`.
- [x] T019 Run grade-2 operational checks: `uv run python scripts/agent_harness_probe.py --strict` and `uv run python scripts/check_handoff_facts.py`.
- [x] T020 Validate PR quality body with `uv run python scripts/check_pr_quality_gate.py`.
- [x] T021 Update `HANDOFF.md` after merge-level truth is known and run handoff verification again.

---

## Dependencies & Execution Order

- Phase 1 must finish before code edits.
- Phase 2 blocks all user stories because every story depends on the shared report parser/model.
- User Story 1 precedes User Story 2 because wait/block aggregation extends the ready-state gates.
- User Story 3 depends on the completed marker and released-work interpretation from User Story 1/2.
- Phase 6 runs after all stories are implemented.

## Parallel Opportunities

- T002 and T003 can be done in parallel after T001.
- T005, T006, and T007 can be developed after T004's public interface is sketched.
- T009 and T012 can be expanded in parallel with the implementation details of their respective stories.
- T015 can be written after the autonomous-work selection path is inspected.
