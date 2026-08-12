# Tasks: Broad NO_EDGE Multi-Horizon Signal

**Input**: Design documents from `specs/131-broad-no-edge-multi-horizon-signal/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/131-broad-no-edge-multi-horizon-signal/`
- [x] T002 Update active feature pointer in `.specify/feature.json`
- [x] T003 Update active plan pointer in `CLAUDE.md`

---

## Phase 2: Foundational

**Purpose**: Establish the no-live multi-horizon signal report contract before implementation.

- [x] T004 [P] Add failing core report tests in `tests/unit/test_broad_no_edge_multi_horizon_signal.py`
- [x] T005 [P] Add failing probe manifest/output tests in `tests/integration/test_broad_no_edge_multi_horizon_signal_probe.py`

---

## Phase 3: User Story 1 - 보유 기간과 신호군 후보를 한 곳에서 본다 (Priority: P1)

**Goal**: Emit a deterministic JSON/Markdown contract for the selected work packet.

**Independent Test**: Focused tests show stable experiment id, required inputs, current signal/horizon coverage, proposed candidates, excluded duplicates, and safety boundary.

- [x] T006 [US1] Implement report data model and builder in `src/auto_invest/analytics/broad_no_edge_multi_horizon_signal.py`
- [x] T007 [US1] Implement probe manifest and sidecar reader in `scripts/broad_no_edge_multi_horizon_signal_probe.py`
- [x] T008 [US1] Render JSON and Markdown report outputs

---

## Phase 4: User Story 2 - 돈 경계와 실험 설계를 분리한다 (Priority: P2)

**Goal**: Report no-live candidate design without declaring live readiness.

**Independent Test**: `PREVIEW_ONLY` and `WAIT_EDGE` remain visible as safety posture; missing evidence produces `BLOCKED`.

- [x] T009 [US2] Parse money-path, edge-autoarm, public-data, regime-stratify, and pipeline evidence in `src/auto_invest/analytics/broad_no_edge_multi_horizon_signal.py`
- [x] T010 [US2] Compute signal-family and holding-period coverage metrics in `src/auto_invest/analytics/broad_no_edge_multi_horizon_signal.py`
- [x] T011 [US2] Add validation gates for money posture, evidence support, candidate separation, and no-live safety

---

## Phase 5: User Story 3 - 후보 완료 뒤 다음 broad no-edge 후보로 전진한다 (Priority: P3)

**Goal**: Close only `candidate-broad-no-edge-multi-horizon-signal-experiment` and prove autonomous-work advances.

**Independent Test**: released-work scan includes the completed candidate, then autonomous-work local replay exposes `candidate-broad-no-edge-regime-cost-robustness-experiment` as the next open broad no-edge entry.

- [x] T012 [US3] Add completion marker contract for `candidate-broad-no-edge-multi-horizon-signal-experiment`
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
2. User Story 1 creates the contract report.
3. User Story 2 makes no-live safety and evidence quality honest instead of overconfident.
4. User Story 3 closes this candidate and verifies next-candidate movement.
5. Phase 6 completes verification, PR, merge, deployment observation, and handoff refresh.

## Implementation Strategy

Implement MVP first: deterministic report plus probe, then add signal/horizon metrics and blocker/wait gates, then prove released-work closure advances the broad no-edge frontier. Keep all changes read-only and use existing SDD, PR, and handoff gates.
