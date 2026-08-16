# Tasks: Uncertainty-Aware ML Edge Ensemble

**Input**: Design documents from `/specs/145-ml-edge-ensemble/`

## Phase 1: Setup

- [x] T001 Create full SDD artifacts and point `.specify/feature.json` at spec 145.
- [x] T002 Add the pinned machine-learning dependency in `pyproject.toml` and `uv.lock`.

## Phase 2: Foundational

- [x] T003 [P] Add chronology, feature, uncertainty, and weight contract tests in `tests/unit/test_ml_edge_ensemble.py`.
- [x] T004 [P] Add CLI, report-shape, workflow, and no-live boundary tests in `tests/integration/test_ml_edge_ensemble_probe.py`.

## Phase 3: User Story 1 - 비용 차감 AI 후보 검증

- [x] T005 [US1] Implement lagged pooled panel features and chronology guards in `src/auto_invest/analytics/ml_edge_ensemble.py`.
- [x] T006 [US1] Implement annual expanding walk-forward ridge/boosting training and uncertainty estimates in `src/auto_invest/analytics/ml_edge_ensemble.py`.
- [x] T007 [US1] Implement capped lower-confidence allocations, turnover costs, benchmarks, significance, regimes, and gates in `src/auto_invest/analytics/ml_edge_ensemble.py`.
- [x] T008 [US1] Prove predictable synthetic data can pass while shuffled/noise data cannot in `tests/unit/test_ml_edge_ensemble.py`.

## Phase 4: User Story 2 - 자동 주기 연구

- [x] T009 [US2] Add public-data loading and JSON/Markdown output in `scripts/ml_edge_ensemble_probe.py`.
- [x] T010 [US2] Add scheduled/manual no-live sidecar workflow in `.github/workflows/ml-edge-ensemble.yml`.

## Phase 5: User Story 3 - 증거 기반 자동 후보 등록

- [x] T011 [US3] Emit a replayable `strategy_backtest` candidate package only on full gate success.
- [x] T012 [US3] Wire ML evidence into the autonomous research input map without live mutation.

## Phase 6: Validation and Delivery

- [x] T013 Run focused and full pytest, ruff, YAML, diff, strict harness, and HANDOFF checks.
- [ ] T014 Refresh HANDOFF, commit, push, open a grade-2 PR, pass quality gate, merge, and verify deployment.
- [ ] T015 Run the no-live workflow and report the real historical verdict before any live strategy change.

## Dependencies

- T002 precedes T003-T012.
- T003-T004 precede their implementation tasks.
- T005-T007 precede T009-T012.
- T013-T015 follow all implementation tasks.
