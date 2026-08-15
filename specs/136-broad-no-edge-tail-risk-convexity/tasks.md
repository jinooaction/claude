# Tasks: Broad No-Edge Tail-Risk Convexity

**Input**: Design documents from `specs/136-broad-no-edge-tail-risk-convexity/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/136-broad-no-edge-tail-risk-convexity/`
- [x] T002 Inspect current sidecars and existing broad no-edge contract patterns

## Phase 2: Tests

- [x] T003 [P] Add core report tests in `tests/unit/test_broad_no_edge_tail_risk_convexity.py`
- [x] T004 [P] Add probe tests in `tests/integration/test_broad_no_edge_tail_risk_convexity_probe.py`
- [x] T005 Confirm existing autonomous-work second-wave advancement coverage in `tests/unit/test_autonomous_work_execution.py`

## Phase 3: User Story 1 - 꼬리위험 방어 후보 축을 계약으로 고정한다

- [x] T006 [US1] Implement report data model and builder in `src/auto_invest/analytics/broad_no_edge_tail_risk_convexity.py`
- [x] T007 [US1] Parse forward tracks and regime tail profiles in `src/auto_invest/analytics/broad_no_edge_tail_risk_convexity.py`
- [x] T008 [US1] Emit risk-off convexity, caution drawdown, shock loss, cost drag, and broad no-edge lanes

## Phase 4: User Story 2 - 비용 부담과 체결 품질을 같이 본다

- [x] T009 [US2] Parse execution-quality cost and broker evidence
- [x] T010 [US2] Add execution-cost-awareness validation gate

## Phase 5: User Story 3 - no-live 안전 경계를 유지하고 다음 후보로 전진한다

- [x] T011 [US3] Add money-path and edge-autoarm no-live gate
- [x] T012 [US3] Add completion marker in `specs/136-broad-no-edge-tail-risk-convexity/spec.md`
- [x] T013 [US3] Expose next candidate `candidate-broad-no-edge-vol-target-drawdown-experiment`
- [x] T014 [US3] Add probe repo-root released-work override

## Phase 6: Validation

- [x] T015 Run focused tests and current sidecar replay
- [x] T016 Run lint, full tests, handoff facts, strict harness, and PR quality gate before merge

## Dependencies

- Phase 1 before Phases 2-5.
- Core module before probe output validation.
- Completion marker before repo-root replay.

## Implementation Strategy

Implement MVP first: deterministic report and lanes. Then add no-live gates and probe. Finally validate released-work completion and autonomous-work advancement.
