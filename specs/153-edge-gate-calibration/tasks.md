# Tasks: Edge Gate Calibration

**Input**: Design documents from `specs/153-edge-gate-calibration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Record the corrected family, split, objective, and calibrated thresholds in `specs/153-edge-gate-calibration/`.
- [x] T002 [P] Add deterministic calibration probe contract tests in `tests/integration/test_edge_gate_calibration_probe.py`.
- [x] T003 [P] Add statistical helper tests in `tests/unit/test_backtest_overfitting.py`.

## Phase 2: Foundational

- [x] T004 Implement bounded effective independent trial estimation in `src/auto_invest/analytics/backtest_overfitting.py`.
- [x] T005 Add fixed-seed null and planted-edge calibration in `src/auto_invest/analytics/edge_gate_calibration.py`.
- [x] T006 Add machine-readable calibration probe in `scripts/edge_gate_calibration_probe.py`.
- [x] T007 Verify calibration false acceptance and detection targets in `tests/unit/test_edge_gate_calibration.py`.

## Phase 3: User Story 1 - Calibrated Error Rates (Priority: P1)

- [x] T008 [US1] Publish legacy-versus-revised acceptance rates in `src/auto_invest/analytics/edge_gate_calibration.py`.
- [x] T009 [US1] Fail closed when either calibration target misses in `scripts/edge_gate_calibration_probe.py`.

## Phase 4: User Story 2 - Family-local Multiplicity (Priority: P1)

- [x] T010 [US2] Separate global audit trials from family statistical trials in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T011 [US2] Compute DSR with effective family trials and PBO with exactly 64 family rows in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T012 [US2] Add heterogeneous-prior exclusion regressions in `tests/unit/test_treasury_carry_factory.py`.

## Phase 5: User Story 3 - Untouched Holdout (Priority: P1)

- [x] T013 [US3] Select the Treasury candidate from development returns only in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T014 [US3] Confirm the frozen candidate after one-month embargo in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T015 [US3] Add holdout perturbation invariance tests in `tests/unit/test_treasury_carry_factory.py`.

## Phase 6: User Story 4 - Objective-specific Economics (Priority: P2)

- [x] T016 [US4] Predeclare Treasury carry as `diversifier` in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T017 [US4] Apply only blend, drawdown, correlation, and cost hard gates while retaining replacement diagnostics in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T018 [US4] Add replacement-versus-diversifier route tests in `tests/unit/test_treasury_carry_factory.py`.

## Phase 7: User Story 5 - Safe Downstream Contract (Priority: P2)

- [x] T019 [US5] Version revised evidence and reject legacy evidence in `src/auto_invest/portfolio/live_entry_revalidation.py`.
- [x] T020 [US5] Update Treasury probe and workflow artifacts in `scripts/treasury_carry_factory_probe.py` and `.github/workflows/autonomous-strategy-factory.yml`.
- [x] T021 [US5] Verify research-only eligibility and zero-order behavior in `tests/integration/test_treasury_carry_factory_probe.py`.

## Phase 8: Verification and Release

- [x] T022 Run focused calibration and Treasury tests.
- [x] T023 Run `uv run pytest` and `uv run ruff check src tests`.
- [x] T024 Run strict harness, handoff facts, and PR quality checks.
- [ ] T025 Commit, push, open and auto-merge the quality-gated PR.
- [ ] T026 Run production calibration, Treasury replay, deployment, public-data, and KIS no-order smoke evidence.
- [ ] T027 Refresh `HANDOFF.md`, commit, push, merge, and verify final `origin/main`.

## Dependencies

- T001-T003 precede T004-T007.
- T004-T009 precede Treasury decision changes T010-T018.
- T010-T018 precede downstream contract T019-T021.
- T022-T027 run sequentially after implementation.

## Implementation Strategy

Calibrate the statistical core first. Only then alter the Treasury decision, and never activate capital or orders in this feature.
