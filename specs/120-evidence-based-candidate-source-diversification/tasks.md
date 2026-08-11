# Tasks: Evidence-Based Candidate Source Diversification

**Input**: Design documents from `/specs/120-evidence-based-candidate-source-diversification/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature changes autonomous operating behavior, so tests are required and are written before implementation tasks.

**Organization**: Tasks are grouped by independently testable user story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature pointer and test surface before code changes.

- [x] T001 Verify `.specify/feature.json` points to `specs/120-evidence-based-candidate-source-diversification`.
- [x] T002 [P] Review existing selection behavior in `src/auto_invest/analytics/autonomous_work_execution.py`.
- [x] T003 [P] Review blocked package diagnostic flow in `src/auto_invest/analytics/candidate_result_executor.py` and `src/auto_invest/analytics/candidate_factory.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared constants and helper shape before user stories.

- [x] T004 Define the evidence-source-diversification candidate identity and source refs in `src/auto_invest/analytics/autonomous_work_execution.py`.
- [x] T005 Add helper functions to extract retryable blocked validation packages from candidate factory and result executor evidence in `src/auto_invest/analytics/autonomous_work_execution.py`.

**Checkpoint**: Foundation ready - user story implementation can begin.

---

## Phase 3: User Story 1 - Select a Fresh Evidence-Based Candidate (Priority: P1)

**Goal**: Closed candidates should not become active selected work when blocked validation evidence can produce a fresh work packet.

**Independent Test**: A fixture with released static candidates and two blocked packages selects the new evidence-source-diversification candidate.

### Tests for User Story 1

- [x] T006 [P] [US1] Add an autonomous-work unit test for released candidates plus blocked validation packages in `tests/unit/test_autonomous_work_execution.py`.

### Implementation for User Story 1

- [x] T007 [US1] Build a synthesized evidence-source-diversification `WorkPacket` from blocked package evidence in `src/auto_invest/analytics/autonomous_work_execution.py`.
- [x] T008 [US1] Insert the synthesized packet before closed suppressed work can become `selected_work` in `src/auto_invest/analytics/autonomous_work_execution.py`.

**Checkpoint**: US1 can be tested independently with `uv run pytest tests/unit/test_autonomous_work_execution.py -q`.

---

## Phase 4: User Story 2 - Turn Blocked Validation Packages Into Actionable Evidence (Priority: P1)

**Goal**: The selected packet should preserve candidate/package traceability and group repeated failure causes.

**Independent Test**: Blocked strategy and portfolio packages produce grouped `execution_failed` evidence with package-level refs and safe next actions.

### Tests for User Story 2

- [x] T009 [P] [US2] Extend the autonomous-work unit test assertions for diagnostic grouping and package traceability in `tests/unit/test_autonomous_work_execution.py`.

### Implementation for User Story 2

- [x] T010 [US2] Add machine-readable blocked package refs to the synthesized packet output in `src/auto_invest/analytics/autonomous_work_execution.py`.
- [x] T011 [US2] Render the blocked validation package summary in Markdown without leaking sensitive values in `src/auto_invest/analytics/autonomous_work_execution.py`.

**Checkpoint**: US2 can be tested independently with the focused autonomous-work unit test.

---

## Phase 5: User Story 3 - Preserve Real-Money Safety While Improving Candidate Flow (Priority: P2)

**Goal**: The packet must explain that live money remains unavailable under `PREVIEW_ONLY` / `NO_EDGE_YET`.

**Independent Test**: The same fixture includes money-path and edge-autoarm status, and the selected packet keeps read-only safety language.

### Tests for User Story 3

- [x] T012 [P] [US3] Add assertions that money-path and edge-autoarm evidence are safety context only in `tests/unit/test_autonomous_work_execution.py`.

### Implementation for User Story 3

- [x] T013 [US3] Include money-path and edge-autoarm source refs and read-only safety language in `src/auto_invest/analytics/autonomous_work_execution.py`.
- [x] T014 [US3] Ensure pending protected live workflow evidence never becomes an execution-ready live-money action in `src/auto_invest/analytics/autonomous_work_execution.py`.

**Checkpoint**: US3 proves this work does not approve real orders or live rearming.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify SDD, local quality gates, and handoff readiness.

- [x] T015 Update SDD quickstart or contract notes if implementation fields differ in `specs/120-evidence-based-candidate-source-diversification/`.
- [x] T016 Run focused tests: `uv run pytest tests/unit/test_autonomous_work_execution.py tests/unit/test_candidate_factory.py tests/unit/test_candidate_result_executor.py -q`.
- [x] T017 Run integration probes: `uv run pytest tests/integration/test_autonomous_work_execution_probe.py tests/integration/test_candidate_factory_probe.py tests/integration/test_candidate_result_executor_probe.py -q`.
- [x] T018 Run full validation: `uv run pytest`, `uv run ruff check src tests`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, and `git diff --check`.
- [x] T019 Refresh `HANDOFF.md` after merge-ready validation if operating truth changes.

---

## Phase 7: Follow-up - Broaden Scope After Candidate Exhaustion (Priority: P1)

**Purpose**: Prevent the loop from treating released source-diversification work as the end of exploration when current retryable validation failures still exist.

- [x] T020 Add broad-frontier acceptance criteria to `specs/120-evidence-based-candidate-source-diversification/spec.md`.
- [x] T021 Extend the evidence-source-diversification contract with fingerprinted broad-frontier output.
- [x] T022 Add autonomous-work unit coverage for all known candidates released plus retryable blocked validation packages.
- [x] T023 Implement deterministic `candidate-broad-frontier-expansion-validation-failures-<fingerprint>` generation before `WAIT_FOR_FRESH_EVIDENCE`.
- [x] T024 Verify the same released fingerprint falls back to wait instead of looping.
- [x] T025 Add autonomous-work unit coverage for all known candidates released plus `PREVIEW_ONLY` / `NO_EDGE_YET` without retryable blocked packages.
- [x] T026 Implement deterministic `candidate-broad-frontier-expansion-no-edge-<fingerprint>` generation before `WAIT_FOR_FRESH_EVIDENCE`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks user stories.
- **US1 (Phase 3)**: Must complete before US2 because the packet must exist before traceability fields can be asserted.
- **US2 (Phase 4)**: Depends on US1 packet creation.
- **US3 (Phase 5)**: Depends on US1 packet creation and can run after or alongside US2 implementation if file conflicts are coordinated.
- **Polish (Phase 6)**: Depends on user story completion.

### Parallel Opportunities

- T002 and T003 can be reviewed in parallel.
- T006, T009, and T012 touch the same test file and must be applied carefully, but their assertions are conceptually independent.
- Final validation commands can run in parallel where they do not mutate state.

## Implementation Strategy

### MVP First

1. Complete T001-T008.
2. Run the focused autonomous-work unit test.
3. Confirm selected work is the new source-diversification packet, not a released candidate.

### Incremental Delivery

1. Add package traceability and grouping (T009-T011).
2. Add money-path safety context (T012-T014).
3. Run focused and full validations.
4. PR, merge, then refresh HANDOFF if the next-session state changed.
