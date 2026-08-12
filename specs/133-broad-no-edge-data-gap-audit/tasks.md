# Tasks: Broad NO_EDGE Data Gap Audit

**Input**: Design documents from `specs/133-broad-no-edge-data-gap-audit/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/133-broad-no-edge-data-gap-audit/`
- [x] T002 Update active feature pointer in `.specify/feature.json`
- [x] T003 Update active plan pointer in `CLAUDE.md`

---

## Phase 2: Foundational

**Purpose**: Establish the no-live data-gap audit contract before implementation.

- [x] T004 [P] Add failing core report tests in `tests/unit/test_broad_no_edge_data_gap_audit.py`
- [x] T005 [P] Add failing probe manifest/output tests in `tests/integration/test_broad_no_edge_data_gap_audit_probe.py`

---

## Phase 3: User Story 1 - 데이터 결측 원인을 한 곳에서 분리한다 (Priority: P1)

**Goal**: Emit a deterministic JSON/Markdown contract for public-data gaps and regime indicator gaps.

**Independent Test**: Focused tests show stable audit id, required inputs, CPI gap classification, cross-check skip classification, and safety boundary.

- [x] T006 [US1] Implement report data model and builder in `src/auto_invest/analytics/broad_no_edge_data_gap_audit.py`
- [x] T007 [US1] Parse public-data summary and regime indicator evidence
- [x] T008 [US1] Render JSON and Markdown report outputs

---

## Phase 4: User Story 2 - 레짐 타임라인 결측이 NO_EDGE 판정에 끼친 영향을 본다 (Priority: P2)

**Goal**: Report timeline label and column missingness without invalidating usable no-live evidence.

**Independent Test**: Current-style timeline evidence shows canonical labels present, inflation column missing, sparse stratified labels, and no-live money alignment.

- [x] T009 [US2] Parse regime timeline CSV and summarize missing columns
- [x] T010 [US2] Parse regime-stratify sections and forward paper rows
- [x] T011 [US2] Add causal findings and validation gates for data impact, money posture, liveness, and release closure

---

## Phase 5: User Story 3 - 후보 완료 뒤 같은 broad no-edge 후보를 반복하지 않는다 (Priority: P3)

**Goal**: Close `candidate-broad-no-edge-data-gap-audit` and prove autonomous-work exits this broad no-edge child sequence.

**Independent Test**: released-work scan includes the completed candidate, then autonomous-work local replay marks all broad no-edge entries released and selects `wait-for-fresh-evidence`.

- [x] T012 [US3] Add completion marker contract for `candidate-broad-no-edge-data-gap-audit`
- [x] T013 [US3] Add autonomous-work local replay assertion in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 6: Validation, PR, and Handoff

- [x] T014 Run focused pytest for new unit and integration tests
- [x] T015 Run local sidecar replay from `quickstart.md`
- [x] T016 Run `uv run pytest`
- [x] T017 Run `uv run ruff check src tests`
- [x] T018 Run `git diff --check`
- [x] T019 Run `uv run python scripts/check_handoff_facts.py`
- [x] T020 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T021 Prepare PR body, PR quality gate evidence, release replay evidence, and HANDOFF refresh

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 creates the public-data and regime indicator gap contract.
3. User Story 2 adds timeline, stratified join, forward no-edge, and causal impact assessment.
4. User Story 3 closes this candidate and verifies broad no-edge repetition stops.
5. Phase 6 completes verification, PR, merge, deployment observation, and handoff refresh.

## Implementation Strategy

Implement MVP first: deterministic report plus probe, then add gap impact and timeline metrics, then prove released-work closure stops the broad no-edge child sequence. Keep all changes read-only and use existing SDD, PR, and handoff gates.
