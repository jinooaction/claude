# Tasks: Execution Cost Basis Contract

**Input**: Design documents from `specs/104-execution-cost-basis-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/execution-cost-basis-contract.md
**Tests**: Required for every user story because this feature changes autonomous work selection/reporting behavior.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature artifacts and existing sidecar contracts before implementation.

- [x] T001 Confirm `specs/104-execution-cost-basis-contract/plan.md` has no template placeholders and records risk grade 2.
- [x] T002 [P] Add the released-work completed marker for `candidate-execution-cost-basis-contract` in `spec.md` and contract docs.
- [x] T003 [P] Inspect current `execution-quality` and `money-path` sidecar shapes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the read-only report model and parser that all user stories use.

- [x] T004 Create `src/auto_invest/analytics/execution_cost_basis.py` with evidence input definitions, report dataclasses, status constants, and JSON/Markdown serialization helpers.
- [x] T005 [P] Add parser and status coverage in `tests/unit/test_execution_cost_basis.py` for execution-quality, money-path, released-work, and capital-path evidence.
- [x] T006 [P] Add `scripts/execution_cost_basis_probe.py` to read sidecar snapshots and emit the contract report.
- [x] T007 Add integration coverage in `tests/integration/test_execution_cost_basis_probe.py` for repository-root mode, manifest mode, and JSON/Markdown output files.

**Checkpoint**: The report can be generated from sidecar files without network calls, broker calls, secret reads, or durable writes beyond explicit output paths.

---

## Phase 3: User Story 1 - 체결 비용 기준 충분성을 분리한다 (Priority: P1)

**Goal**: Distinguish measurable accepted/fill cost basis from normal observation wait.

**Independent Test**: Run unit cases for ready basis, missing basis block, and accepted sample without measurable cost basis.

- [x] T008 [US1] Implement cost-basis summary and status rules in `src/auto_invest/analytics/execution_cost_basis.py`.
- [x] T009 [P] [US1] Cover ready, missing-block, and incomplete accepted/fill basis cases in `tests/unit/test_execution_cost_basis.py`.

**Checkpoint**: User Story 1 is independently functional.

---

## Phase 4: User Story 2 - money-path 문맥과 안전 경계를 보존한다 (Priority: P2)

**Goal**: Preserve money-path context without creating live-money side effects.

**Independent Test**: Run unit cases for `PREVIEW_ONLY` context and missing money-path.

- [x] T010 [US2] Implement money-path summary and safety boundary gates.
- [x] T011 [P] [US2] Add unit tests for money-path context and BLOCKED missing input outcomes.
- [x] T012 [US2] Verify the report includes safety fields showing no broker/order/capital/live/secret mutation.

**Checkpoint**: User Story 2 is independently functional.

---

## Phase 5: User Story 3 - 완료 후보를 닫고 다음 체결 품질 후보로 전진한다 (Priority: P3)

**Goal**: Mark `candidate-execution-cost-basis-contract` complete and advance autonomous-work to `candidate-broker-diagnostic-liveness-contract`.

**Independent Test**: Run autonomous-work unit and local replay with released-work evidence that includes this spec's completion marker.

- [x] T013 [US3] Add autonomous-work unit coverage in `tests/unit/test_autonomous_work_execution.py` for advancement from execution cost basis to broker diagnostic liveness.
- [x] T014 [US3] Re-run `scripts/released_work_probe.py` and `scripts/autonomous_work_execution_probe.py` locally to confirm the completion marker is detected and the next candidate is selected.

**Checkpoint**: User Story 3 is independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish validation and PR quality evidence. Post-merge HANDOFF refresh is part of done, but the released-work task list tracks the feature PR itself.

- [x] T015 Run focused validation: `uv run pytest tests/unit/test_execution_cost_basis.py tests/integration/test_execution_cost_basis_probe.py tests/unit/test_autonomous_work_execution.py`.
- [x] T016 Run full validation: `uv run pytest` and `uv run ruff check src tests`.
- [x] T017 Run grade-2 operational checks: `uv run python scripts/agent_harness_probe.py --strict` and `uv run python scripts/check_handoff_facts.py`.
- [x] T018 Validate PR quality body with `uv run python scripts/check_pr_quality_gate.py`.

---

## Dependencies & Execution Order

- Phase 1 must finish before code edits.
- Phase 2 blocks all user stories because every story depends on the shared report parser/model.
- User Story 1 and User Story 2 both depend on Phase 2.
- User Story 3 depends on the completed marker and released-work interpretation from earlier phases.
- Phase 6 runs after all stories are implemented.

## Parallel Opportunities

- T005, T006, and T007 can be developed after T004's public interface is sketched.
- T009 and T011 can be expanded in parallel with their corresponding implementation details.
- T013 can be verified while probe integration tests are being finalized.

## Implementation Strategy

Implement MVP first: parse execution-quality and money-path, then add explicit gates, then prove released-work/autonomous-work advancement. Keep all changes read-only and use existing SDD, PR, and validation gates.
