# Tasks: Data Evidence Liveness Contract

**Input**: Design documents from `/specs/101-data-evidence-liveness-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/data-evidence-liveness-contract.md
**Tests**: Required for every user story because this feature changes autonomous work selection/reporting behavior.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature artifacts and existing sidecar contracts before implementation.

- [x] T001 Confirm `specs/101-data-evidence-liveness-contract/plan.md` has no template placeholders and records risk grade 2.
- [x] T002 [P] Add the released-work completed marker for `candidate-data-evidence-liveness-contract` in `specs/101-data-evidence-liveness-contract/spec.md`.
- [x] T003 [P] Inspect existing data evidence frontier templates and latest automation sidecars.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the read-only report model and parser that all user stories use.

- [x] T004 Create `src/auto_invest/analytics/data_evidence_liveness.py` with evidence input definitions, report dataclasses, status constants, and JSON/Markdown serialization helpers.
- [x] T005 [P] Add parser coverage in `tests/unit/test_data_evidence_liveness.py` for pipeline-liveness, source LAST_RUN timestamps, released-work, and capital-path evidence.
- [x] T006 [P] Add `scripts/data_evidence_liveness_probe.py` to read sidecar snapshots and emit the contract report.
- [x] T007 Add integration coverage in `tests/integration/test_data_evidence_liveness_probe.py` for repository-root mode, manifest mode, and JSON/Markdown output files.

**Checkpoint**: The report can be generated from sidecar files without network calls, broker calls, secret reads, or durable writes beyond explicit output paths.

---

## Phase 3: User Story 1 - 데이터 증거 생존성을 PASS/WAIT/FAIL로 분리한다 (Priority: P1)

**Goal**: Convert `collect-public-data` and `regime-stratify` pipeline-liveness rows into explicit data-quality liveness gates.

**Independent Test**: Run unit cases for both checks OK, one check stale, and missing check registration.

- [x] T008 [US1] Implement required check extraction and data liveness status gate in `src/auto_invest/analytics/data_evidence_liveness.py`.
- [x] T009 [P] [US1] Cover ready, non-OK wait, and missing-registration block cases in `tests/unit/test_data_evidence_liveness.py`.
- [x] T010 [US1] Verify current `origin/automation/pipeline-liveness-last-run:LAST_RUN.md` replays with both data checks PASS.

**Checkpoint**: User Story 1 is independently functional.

---

## Phase 4: User Story 2 - source sidecar timestamp를 감사 가능하게 맞춘다 (Priority: P2)

**Goal**: Prove the registry rows match direct source LAST_RUN timestamps.

**Independent Test**: Run unit cases that pass exact source/check timestamp matches and block missing or mismatched timestamps.

- [x] T011 [US2] Implement source timestamp observation and consistency gates in `src/auto_invest/analytics/data_evidence_liveness.py`.
- [x] T012 [P] [US2] Add unit tests for source timestamp match, missing timestamp, and mismatched timestamp in `tests/unit/test_data_evidence_liveness.py`.
- [x] T013 [US2] Ensure the report includes safety fields showing no broker/order/capital mutation.

**Checkpoint**: User Story 2 is independently functional.

---

## Phase 5: User Story 3 - 완료 후보를 닫고 다음 거시 후보로 전진한다 (Priority: P3)

**Goal**: Mark `candidate-data-evidence-liveness-contract` complete and advance autonomous-work to the execution quality macro frontier.

**Independent Test**: Run autonomous-work unit tests with released-work evidence that includes all data evidence frontier candidates and verify the selected candidate advances to `candidate-execution-quality-frontier-map`.

- [x] T014 [US3] Add autonomous-work unit coverage in `tests/unit/test_autonomous_work_execution.py` for advancement from completed data evidence liveness to `candidate-execution-quality-frontier-map`.
- [x] T015 [US3] Re-run `scripts/released_work_probe.py` and `scripts/autonomous_work_execution_probe.py` locally to confirm the completion marker is detected and the next candidate is selected.

**Checkpoint**: User Story 3 is independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish validation and PR quality evidence. Post-merge HANDOFF refresh is intentionally outside this released-work task list so candidate release is not blocked by a future merge-truth update.

- [x] T016 Run focused validation: `uv run pytest tests/unit/test_data_evidence_liveness.py tests/integration/test_data_evidence_liveness_probe.py tests/unit/test_autonomous_work_execution.py`.
- [x] T017 Run full validation: `uv run pytest` and `uv run ruff check src tests`.
- [x] T018 Run grade-2 operational checks: `uv run python scripts/agent_harness_probe.py --strict` and `uv run python scripts/check_handoff_facts.py`.
- [x] T019 Validate PR quality body with `uv run python scripts/check_pr_quality_gate.py`.

---

## Dependencies & Execution Order

- Phase 1 must finish before code edits.
- Phase 2 blocks all user stories because every story depends on the shared report parser/model.
- User Story 1 precedes User Story 2 because source timestamp consistency depends on extracted pipeline rows.
- User Story 3 depends on the completed marker and released-work interpretation from earlier phases.
- Phase 6 runs after all stories are implemented.

## Parallel Opportunities

- T005, T006, and T007 can be developed after T004's public interface is sketched.
- T009 and T012 can be expanded in parallel with their corresponding implementation details.
- T014 can be written after the autonomous-work selection path is inspected.

## Implementation Strategy

Implement MVP first: pipeline-liveness required-check extraction and status mapping, then source timestamp consistency, then released-work/autonomous-work advancement proof. Keep all changes read-only and use existing SDD, PR, and validation gates.
