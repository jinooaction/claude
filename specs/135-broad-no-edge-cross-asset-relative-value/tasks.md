# Tasks: Broad No-Edge Cross-Asset Relative Value

**Input**: Design documents from `specs/135-broad-no-edge-cross-asset-relative-value/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/135-broad-no-edge-cross-asset-relative-value/`
- [x] T002 Inspect current sidecars and existing broad no-edge contract patterns

## Phase 2: Tests

- [x] T003 [P] Add core report tests in `tests/unit/test_broad_no_edge_cross_asset_relative_value.py`
- [x] T004 [P] Add probe tests in `tests/integration/test_broad_no_edge_cross_asset_relative_value_probe.py`
- [x] T005 Confirm existing autonomous-work second-wave advancement coverage in `tests/unit/test_autonomous_work_execution.py`

## Phase 3: User Story 1 - 상대가치 후보 축을 계약으로 고정한다

- [x] T006 [US1] Implement report data model and builder in `src/auto_invest/analytics/broad_no_edge_cross_asset_relative_value.py`
- [x] T007 [US1] Parse forward tracks and infer asset classes in `src/auto_invest/analytics/broad_no_edge_cross_asset_relative_value.py`
- [x] T008 [US1] Emit equity/duration, duration/commodity, cash proxy, and broad no-edge lanes in `src/auto_invest/analytics/broad_no_edge_cross_asset_relative_value.py`

## Phase 4: User Story 2 - no-live 안전 경계를 유지한다

- [x] T009 [US2] Add money-path and edge-autoarm no-live gate in `src/auto_invest/analytics/broad_no_edge_cross_asset_relative_value.py`
- [x] T010 [US2] Add safety boundary to JSON and Markdown report in `src/auto_invest/analytics/broad_no_edge_cross_asset_relative_value.py`

## Phase 5: User Story 3 - 완료 뒤 다음 broad no-edge 후보로 전진한다

- [x] T011 [US3] Add completion marker in `specs/135-broad-no-edge-cross-asset-relative-value/spec.md`
- [x] T012 [US3] Expose next candidate `candidate-broad-no-edge-tail-risk-convexity-experiment` in the report
- [x] T013 [US3] Add probe repo-root released-work override in `scripts/broad_no_edge_cross_asset_relative_value_probe.py`

## Phase 6: Validation

- [x] T014 Run focused tests and current sidecar replay
- [x] T015 Run lint, full tests, handoff facts, strict harness, and PR quality gate before merge

## Dependencies

- Phase 1 before Phases 2-5.
- Core module before probe output validation.
- Completion marker before repo-root replay.

## Implementation Strategy

Implement MVP first: deterministic report and lanes. Then add no-live gates and probe. Finally validate released-work completion and autonomous-work advancement.
