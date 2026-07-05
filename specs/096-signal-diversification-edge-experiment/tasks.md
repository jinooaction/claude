# Tasks: Signal Diversification Edge Experiment

**Input**: Design documents from `specs/096-signal-diversification-edge-experiment/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/096-signal-diversification-edge-experiment/`

---

## Phase 2: Foundational

**Purpose**: Establish the no-live signal diversification report contract before implementation.

- [x] T003 [P] Add failing core report tests in `tests/unit/test_signal_diversification_edge_experiment.py`
- [x] T004 [P] Add failing probe manifest/output tests in `tests/integration/test_signal_diversification_edge_experiment_probe.py`

---

## Phase 3: User Story 1 - 신호 다양성 실험 계약을 한 곳에서 본다 (Priority: P1)

**Goal**: Emit a deterministic JSON/Markdown contract for the selected work packet.

**Independent Test**: Focused tests show stable experiment id, required inputs, signal families, proposed candidates, and safety boundary.

- [x] T005 [US1] Implement report data model and builder in `src/auto_invest/analytics/signal_diversification_edge_experiment.py`
- [x] T006 [US1] Implement probe manifest and sidecar reader in `scripts/signal_diversification_edge_experiment_probe.py`
- [x] T007 [US1] Render JSON and Markdown report outputs

---

## Phase 4: User Story 2 - 신호 겹침과 관측 부족을 정직하게 분리한다 (Priority: P2)

**Goal**: Report signal concentration, overlap, observation wait, and blockers without declaring false live readiness.

**Independent Test**: Current-style insufficient observations remain visible as wait; critical liveness failure produces `BLOCKED`.

- [x] T008 [US2] Parse forward tracks into signal families in `src/auto_invest/analytics/signal_diversification_edge_experiment.py`
- [x] T009 [US2] Compute universe overlap and diversification metrics in `src/auto_invest/analytics/signal_diversification_edge_experiment.py`
- [x] T010 [US2] Add validation gates for signal diversity, incumbent overlap, observation readiness, and no-live safety

---

## Phase 5: User Story 3 - 후보 완료 뒤 비용 차감 엣지 후보로 전진한다 (Priority: P3)

**Goal**: Close only `candidate-signal-diversification-edge-experiment` and prove autonomous-work advances.

**Independent Test**: released-work scan includes the completed candidate, then autonomous-work local replay selects `candidate-cost-adjusted-edge-experiment`.

- [x] T011 [US3] Add completion marker contract for `candidate-signal-diversification-edge-experiment`
- [x] T012 [US3] Run released-work and autonomous-work local replay from `quickstart.md`

---

## Phase 6: Validation, PR, and Handoff

- [x] T013 Run focused pytest for new unit and integration tests
- [x] T014 Run local sidecar replay from `quickstart.md`
- [x] T015 Run `uv run pytest`
- [x] T016 Run `uv run ruff check src tests`
- [x] T017 Run `git diff --check`
- [x] T018 Run `uv run python scripts/check_handoff_facts.py`
- [x] T019 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T020 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 creates the contract report.
3. User Story 2 makes signal concentration and observation readiness honest instead of overconfident.
4. User Story 3 closes this candidate and verifies next-candidate movement.
5. Phase 6 completes verification, PR, merge, deployment observation, and handoff refresh.

## Implementation Strategy

Implement MVP first: deterministic report plus probe, then add signal-family metrics and blocker/wait gates, then prove released-work closure advances the investment-edge frontier. Keep all changes read-only and use existing SDD, PR, and handoff gates.
