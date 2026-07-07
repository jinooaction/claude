# Tasks: Broker Rejection Taxonomy Contract

**Input**: Design documents from `specs/103-broker-rejection-taxonomy-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/broker-rejection-taxonomy-contract.md
**Tests**: Required for every user story because this feature changes autonomous work selection/reporting behavior.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature artifacts and existing sidecar contracts before implementation.

- [x] T001 Confirm `specs/103-broker-rejection-taxonomy-contract/plan.md` has no template placeholders and records risk grade 2.
- [x] T002 [P] Add the released-work completed marker for `candidate-broker-rejection-taxonomy-contract` in `specs/103-broker-rejection-taxonomy-contract/spec.md` and contract docs.
- [x] T003 [P] Inspect current `execution-quality`, `kis-smoke`, and `rebalance-micro-gtaa` sidecar shapes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the read-only report model and parser that all user stories use.

- [x] T004 Create `src/auto_invest/analytics/broker_rejection_taxonomy.py` with evidence input definitions, report dataclasses, status constants, and JSON/Markdown serialization helpers.
- [x] T005 [P] Add parser and classification coverage in `tests/unit/test_broker_rejection_taxonomy.py` for execution-quality, KIS smoke, micro GTAA live gate, released-work, and capital-path evidence.
- [x] T006 [P] Add `scripts/broker_rejection_taxonomy_probe.py` to read sidecar snapshots and emit the contract report.
- [x] T007 Add integration coverage in `tests/integration/test_broker_rejection_taxonomy_probe.py` for repository-root mode, manifest mode, and JSON/Markdown output files.

**Checkpoint**: The report can be generated from sidecar files without network calls, broker calls, secret reads, or durable writes beyond explicit output paths.

---

## Phase 3: User Story 1 - 브로커 거부 원인을 분류한다 (Priority: P1)

**Goal**: Convert observed KIS rejection signatures into stable taxonomy rows.

**Independent Test**: Run unit cases for `APBK1672`, unknown KIS code, and current KIS smoke success.

- [x] T008 [US1] Implement known and unknown KIS code taxonomy classification in `src/auto_invest/analytics/broker_rejection_taxonomy.py`.
- [x] T009 [P] [US1] Cover current `APBK1672` evidence and unknown-code fallback in `tests/unit/test_broker_rejection_taxonomy.py`.

**Checkpoint**: User Story 1 is independently functional.

---

## Phase 4: User Story 2 - 증거 결손을 PASS/WAIT/FAIL로 분리한다 (Priority: P2)

**Goal**: Convert missing, malformed, empty, and healthy evidence into explicit gates.

**Independent Test**: Run unit cases for ready, missing execution-quality, no rejections, and KIS smoke wait cases.

- [x] T010 [US2] Implement quality gates and overall status rules in `src/auto_invest/analytics/broker_rejection_taxonomy.py`.
- [x] T011 [P] [US2] Add unit tests for BLOCKED, OBSERVATION_WAIT, and CONTRACT_READY outcomes.
- [x] T012 [US2] Verify the report includes safety fields showing no broker/order/capital mutation.

**Checkpoint**: User Story 2 is independently functional.

---

## Phase 5: User Story 3 - 완료 후보를 닫고 다음 체결 품질 후보로 전진한다 (Priority: P3)

**Goal**: Mark `candidate-broker-rejection-taxonomy-contract` complete and advance autonomous-work to `candidate-execution-cost-basis-contract`.

**Independent Test**: Run autonomous-work unit and local replay with released-work evidence that includes this spec's completion marker.

- [x] T013 [US3] Add or confirm autonomous-work unit coverage in `tests/unit/test_autonomous_work_execution.py` for advancement from broker rejection taxonomy to execution cost basis.
- [x] T014 [US3] Re-run `scripts/released_work_probe.py` and `scripts/autonomous_work_execution_probe.py` locally to confirm the completion marker is detected and the next candidate is selected.

**Checkpoint**: User Story 3 is independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish validation and PR quality evidence. Post-merge HANDOFF refresh is part of done, but the released-work task list tracks the feature PR itself.

- [x] T015 Run focused validation: `uv run pytest tests/unit/test_broker_rejection_taxonomy.py tests/integration/test_broker_rejection_taxonomy_probe.py tests/unit/test_autonomous_work_execution.py`.
- [x] T016 Run full validation: `uv run pytest` and `uv run ruff check src tests`.
- [x] T017 Run grade-2 operational checks: `uv run python scripts/agent_harness_probe.py --strict` and `uv run python scripts/check_handoff_facts.py`.
- [x] T018 Validate PR quality body with `uv run python scripts/check_pr_quality_gate.py`.

---

## Dependencies & Execution Order

- Phase 1 must finish before code edits.
- Phase 2 blocks all user stories because every story depends on the shared report parser/model.
- User Story 1 and User Story 2 both depend on Phase 2; implement US1 first so gates can reason over taxonomy output.
- User Story 3 depends on the completed marker and released-work interpretation from earlier phases.
- Phase 6 runs after all stories are implemented.

## Parallel Opportunities

- T005, T006, and T007 can be developed after T004's public interface is sketched.
- T009 and T011 can be expanded in parallel with their corresponding implementation details.
- T013 can be verified while probe integration tests are being finalized.

## Implementation Strategy

Implement MVP first: parse execution-quality and classify KIS codes, then add explicit gates, then prove released-work/autonomous-work advancement. Keep all changes read-only and use existing SDD, PR, and validation gates.
