# Tasks: Broad No-Edge Vol-Target Drawdown

**Input**: Design documents from `specs/137-broad-no-edge-vol-target-drawdown/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/137-broad-no-edge-vol-target-drawdown/`
- [x] T002 Inspect current sidecars and existing broad no-edge contract patterns

## Phase 2: Tests

- [x] T003 [P] Add core report tests in `tests/unit/test_broad_no_edge_vol_target_drawdown.py`
- [x] T004 [P] Add probe tests in `tests/integration/test_broad_no_edge_vol_target_drawdown_probe.py`
- [x] T005 Confirm existing autonomous-work second-wave advancement coverage in `tests/unit/test_autonomous_work_execution.py`

## Phase 3: User Story 1 - 변동성 목표 후보 축을 계약으로 고정한다

- [x] T006 [US1] Implement report data model and builder in `src/auto_invest/analytics/broad_no_edge_vol_target_drawdown.py`
- [x] T007 [US1] Parse forward tracks, PSR, Calmar, and drawdown context in `src/auto_invest/analytics/broad_no_edge_vol_target_drawdown.py`
- [x] T008 [US1] Emit volatility target, drawdown overlay, PSR sensitivity, live exclusion, and broad no-edge lanes

## Phase 4: User Story 2 - live drawdown과 자본 사다리 제외 조건을 같이 본다

- [x] T009 [US2] Parse money-path rung and drawdown budgets
- [x] T010 [US2] Parse edge-autoarm live drawdown and forward verdict evidence
- [x] T011 [US2] Add money-path and edge-autoarm no-live gate

## Phase 5: User Story 3 - 후보를 완료 처리하고 반복을 막는다

- [x] T012 [US3] Add completion marker in `specs/137-broad-no-edge-vol-target-drawdown/spec.md`
- [x] T013 [US3] Expose next candidate `wait-for-fresh-evidence`
- [x] T014 [US3] Add probe repo-root released-work override

## Phase 6: Validation

- [x] T015 Run focused tests and current sidecar replay
- [x] T016 Run lint, full tests, handoff facts, strict harness, and PR quality gate before merge

## Dependencies

- Phase 1 before Phases 2-5.
- Core module before probe output validation.
- Completion marker before repo-root replay.

## Implementation Strategy

Implement MVP first: deterministic report and lanes. Then add no-live money gates and probe. Finally validate released-work completion and autonomous-work advancement.
