# Tasks: Regime Timeline Coverage Contract

**Input**: Design documents from `/specs/100-regime-timeline-coverage-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/regime-timeline-coverage-contract.md
**Tests**: Required for every user story because this feature changes autonomous work selection/reporting behavior.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature artifacts and existing sidecar contracts before implementation.

- [x] T001 Confirm `specs/100-regime-timeline-coverage-contract/plan.md` has no template placeholders and records risk grade 2.
- [x] T002 [P] Add the released-work completed marker for `candidate-regime-timeline-coverage-contract` in `specs/100-regime-timeline-coverage-contract/spec.md`.
- [x] T003 [P] Inspect existing regime timeline producer/consumer contracts in `src/auto_invest/market_data/macro_regime.py`, `src/auto_invest/analytics/regime_stratified.py`, and latest automation sidecars.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the read-only report model and parser that all user stories use.

- [x] T004 Create `src/auto_invest/analytics/regime_timeline_coverage.py` with evidence input definitions, report dataclasses, status constants, and JSON/Markdown serialization helpers.
- [x] T005 [P] Add parser coverage in `tests/unit/test_regime_timeline_coverage.py` for timeline CSV, multi-section regime-stratify markdown, pipeline-liveness, and released-work evidence.
- [x] T006 [P] Add `scripts/regime_timeline_coverage_probe.py` to read sidecar snapshots and emit the contract report.
- [x] T007 Add integration coverage in `tests/integration/test_regime_timeline_coverage_probe.py` for repository-root mode and JSON/Markdown output files.

**Checkpoint**: The report can be generated from sidecar files without network calls, broker calls, secret reads, or durable writes beyond explicit output paths.

---

## Phase 3: User Story 1 - 레짐 타임라인 라벨 커버리지를 판정한다 (Priority: P1)

**Goal**: Produce deterministic timeline shape and label coverage facts from `regime_timeline.csv`.

**Independent Test**: Run unit success cases for timeline shape, canonical label counts, missing labels, duplicate dates, and out-of-order dates.

- [x] T008 [US1] Implement timeline shape and label coverage gates in `src/auto_invest/analytics/regime_timeline_coverage.py`.
- [x] T009 [P] [US1] Cover ready timeline JSON contract and Markdown report in `tests/unit/test_regime_timeline_coverage.py`.
- [x] T010 [US1] Verify current `origin/automation/public-data:regime_timeline.csv` replays with timeline shape PASS.

**Checkpoint**: User Story 1 is independently functional.

---

## Phase 4: User Story 2 - 레짐별 관측 수 부족을 정직하게 대기 상태로 분리한다 (Priority: P2)

**Goal**: Distinguish sparse rare-regime samples from blocking malformed stratified outputs.

**Independent Test**: Run unit cases that force `RISK_OFF` below 20 into `OBSERVATION_WAIT` and malformed/count-mismatch sections into `BLOCKED`.

- [x] T011 [US2] Implement multi-section stratified summary and observation floor gates in `src/auto_invest/analytics/regime_timeline_coverage.py`.
- [x] T012 [P] [US2] Add unit tests for sparse label wait, missing stratified JSON, malformed JSON, and count mismatch in `tests/unit/test_regime_timeline_coverage.py`.
- [x] T013 [US2] Ensure current `origin/automation/regime-stratify-last-run:LAST_RUN.md` replays as `OBSERVATION_WAIT` due to sparse `RISK_OFF`.

**Checkpoint**: User Story 2 is independently functional.

---

## Phase 5: User Story 3 - 전망적 조인 품질을 계약으로 고정한다 (Priority: P3)

**Goal**: Fail closed when the sidecar no longer proves d+1 forward joining or label count consistency.

**Independent Test**: Run unit cases for missing/non-forward join rule and label count mismatch.

- [x] T014 [US3] Implement forward join quality gate in `src/auto_invest/analytics/regime_timeline_coverage.py`.
- [x] T015 [P] [US3] Add unit tests for forward join PASS/FAIL behavior in `tests/unit/test_regime_timeline_coverage.py`.
- [x] T016 [US3] Ensure the report always includes safety fields showing no broker/order/capital mutation.

**Checkpoint**: User Story 3 is independently functional.

---

## Phase 6: User Story 4 - 완료 후보를 닫고 다음 데이터 증거 후보로 전진한다 (Priority: P4)

**Goal**: Mark `candidate-regime-timeline-coverage-contract` complete and advance autonomous-work to the next unreleased data evidence frontier candidate.

**Independent Test**: Run autonomous-work unit tests with released-work evidence that includes the completed marker and verify the selected candidate advances to `candidate-data-evidence-liveness-contract`.

- [x] T017 [US4] Add autonomous-work unit coverage in `tests/unit/test_autonomous_work_execution.py` for advancement from `candidate-regime-timeline-coverage-contract` to `candidate-data-evidence-liveness-contract`.
- [ ] T018 [US4] Re-run `scripts/released_work_probe.py` and `scripts/autonomous_work_execution_probe.py` locally to confirm the completion marker is detected and the next candidate is selected.

**Checkpoint**: User Story 4 is independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Finish validation, PR quality evidence, and handoff safety.

- [x] T019 Run focused validation: `uv run pytest tests/unit/test_regime_timeline_coverage.py tests/integration/test_regime_timeline_coverage_probe.py tests/unit/test_autonomous_work_execution.py`.
- [x] T020 Run full validation: `uv run pytest` and `uv run ruff check src tests`.
- [x] T021 Run grade-2 operational checks: `uv run python scripts/agent_harness_probe.py --strict` and `uv run python scripts/check_handoff_facts.py`.
- [x] T022 Validate PR quality body with `uv run python scripts/check_pr_quality_gate.py`.
- [ ] T023 Update `HANDOFF.md` after merge-level truth is known and run handoff verification again.

---

## Dependencies & Execution Order

- Phase 1 must finish before code edits.
- Phase 2 blocks all user stories because every story depends on the shared report parser/model.
- User Story 1 precedes User Story 2 because stratified label floors depend on timeline canonical label coverage.
- User Story 3 depends on the stratified section parser from User Story 2.
- User Story 4 depends on the completed marker and released-work interpretation from earlier phases.
- Phase 7 runs after all stories are implemented.

## Parallel Opportunities

- T002 and T003 can be done in parallel after T001.
- T005, T006, and T007 can be developed after T004's public interface is sketched.
- T009, T012, and T015 can be expanded in parallel with their corresponding implementation details.
- T017 can be written after the autonomous-work selection path is inspected.

## Implementation Strategy

Implement MVP first: timeline shape and label coverage, then multi-section stratified observation floors, then forward join fail-closed behavior, then released-work/autonomous-work advancement proof. Keep all changes read-only and use existing SDD, PR, and handoff gates.
