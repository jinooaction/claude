# Tasks: Candidate Evidence Diagnostics

**Input**: Design documents from `specs/072-candidate-evidence-diagnostics/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and changes evidence consumed by downstream loops.

## Phase 1: Setup

- [x] T001 [P] Add diagnostic fixture expectations to `tests/unit/test_candidate_result_executor.py`.
- [x] T002 [P] Add factory propagation fixture expectations to `tests/unit/test_candidate_factory.py`.
- [x] T003 [P] Add probe and workflow regression expectations to `tests/integration/test_candidate_result_executor_probe.py`.

---

## Phase 2: Foundational

- [x] T004 Define diagnostic and next-action data model in `src/auto_invest/analytics/candidate_result_executor.py`.
- [x] T005 Implement diagnostic classification helpers in `src/auto_invest/analytics/candidate_result_executor.py`.

---

## Phase 3: User Story 1 - pending 후보의 원인을 구조화 (Priority: P1)

**Goal**: Every pending or blocked result row has machine-readable diagnostics and safe next actions.

**Independent Test**: `uv run pytest tests/unit/test_candidate_result_executor.py`.

- [x] T006 [US1] Attach diagnostics, flattened next actions, and retryable flag to `CandidateResultRow` in `src/auto_invest/analytics/candidate_result_executor.py`.
- [x] T007 [US1] Classify data missing, command contract error, insufficient evidence, timeout, unsafe command, unsupported package, missing command, and execution failure in `src/auto_invest/analytics/candidate_result_executor.py`.
- [x] T008 [US1] Preserve existing pass/fail/pending/blocked counts while adding diagnostics in `tests/unit/test_candidate_result_executor.py`.

---

## Phase 4: User Story 2 - 후보 공장과 승격 루프가 진단을 소비 (Priority: P2)

**Goal**: Candidate factory carries diagnostics into enriched backlog without creating false pass evidence.

**Independent Test**: `uv run pytest tests/unit/test_candidate_factory.py`.

- [x] T009 [US2] Extend `EvidenceResult` parsing for diagnostics, next actions, and retryable state in `src/auto_invest/analytics/candidate_factory.py`.
- [x] T010 [US2] Add diagnostic propagation to `_promotion_patch` in `src/auto_invest/analytics/candidate_factory.py`.
- [x] T011 [US2] Prove pending diagnostics survive factory enrichment without increasing pass counts in `tests/unit/test_candidate_factory.py`.

---

## Phase 5: User Story 3 - 운영자와 자동화가 같은 요약을 본다 (Priority: P3)

**Goal**: Markdown and JSON sidecars expose the same diagnostic counts and next actions.

**Independent Test**: `uv run pytest tests/integration/test_candidate_result_executor_probe.py`.

- [x] T012 [US3] Add diagnostic counts to executor run JSON and Markdown in `src/auto_invest/analytics/candidate_result_executor.py`.
- [x] T013 [US3] Assert probe output contains diagnostics and workflow remains no-live in `tests/integration/test_candidate_result_executor_probe.py`.
- [x] T014 [US3] Update spec 072 quickstart if implementation output names differ in `specs/072-candidate-evidence-diagnostics/quickstart.md`.

---

## Phase 6: Polish & Cross-Cutting

- [x] T015 Update `CLAUDE.md` SPECKIT pointer to `specs/072-candidate-evidence-diagnostics/plan.md`.
- [x] T016 Run focused candidate diagnostics tests.
- [x] T017 Run `uv run pytest`.
- [x] T018 Run `uv run ruff check src tests`.
- [x] T019 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
- [ ] T020 Update handoff after merge if operating truth changed.

## Dependencies & Execution Order

- Phase 1 and Phase 2 come first.
- User Story 1 is the MVP because diagnostics must exist before downstream propagation.
- User Story 2 depends on User Story 1's result schema.
- User Story 3 depends on User Story 1's diagnostic counts.
- Polish runs after all user stories.

## Parallel Opportunities

- T001, T002, and T003 can be drafted independently.
- T009/T010 depend on T006 schema but not on Markdown formatting.
- Focused tests can run before full tests.

## Implementation Strategy

1. Implement diagnostics in the pure result executor first.
2. Preserve result counts and pass semantics with unit tests.
3. Propagate diagnostics through candidate factory only after result schema is stable.
4. Update reports and quickstart.
5. Run focused tests, full tests, lint, handoff facts, and strict harness before PR.
