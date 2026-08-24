# Tasks: Commodity Positioning and Real-World Gate Controls

## Phase 1 - Preregistration

- [x] T001 Freeze controls, sources, contract codes, lags, candidates, costs, split, thresholds, and safety boundaries in `specs/157-commodity-positioning-gate-controls/`.
- [x] T002 Record source revision risk, basis risk, empirical-control role, alternatives, and rollback in `specs/157-commodity-positioning-gate-controls/research.md`.
- [x] T003 Point `.specify/feature.json` and `CLAUDE.md` at spec 157.

## Phase 2 - Tests First

- [x] T004 [P] [US1] Add failing parser, actual-control, demeaned-control, isolation, and fail-closed tests in `tests/unit/test_real_world_gate_controls.py`.
- [x] T005 [P] [US2] Add failing CFTC/EIA parser, lag, candidate, split, cost, and holdout-isolation tests in `tests/unit/test_commodity_positioning_factory.py`.
- [x] T006 [P] [US3] Add failing no-broker probe and workflow contract tests in `tests/integration/test_commodity_positioning_factory_probe.py`.

## Phase 3 - Real-World Gate Audit

- [x] T007 [US1] Implement Fama-French ZIP and AQR XLSX parsing in `src/auto_invest/analytics/real_world_gate_controls.py`.
- [x] T008 [US1] Implement fixed-window actual and demeaned PSR controls with deterministic evidence in `src/auto_invest/analytics/real_world_gate_controls.py`.
- [x] T009 [US1] Bind empirical controls to promotion eligibility without adding them to candidate trials in `src/auto_invest/analytics/commodity_positioning_factory.py`.

## Phase 4 - Commodity Positioning Factory

- [x] T010 [US2] Add `xlrd` and implement CFTC JSON and EIA XLS parsers in `src/auto_invest/analytics/commodity_positioning_factory.py`.
- [x] T011 [US2] Implement publication lags, normalized rolling signals, and exactly 16 policies in `src/auto_invest/analytics/commodity_positioning_factory.py`.
- [x] T012 [US2] Implement development-only selection, embargo, untouched holdout, costs, tiered gates, parity, and 688-record audit in `src/auto_invest/analytics/commodity_positioning_factory.py`.

## Phase 5 - Automation and Production

- [x] T013 [US3] Implement the no-order CLI and Korean summary in `scripts/commodity_positioning_factory_probe.py`.
- [x] T014 [US3] Wire source collection, controls, factory, ledger, audit catalog, and sidecar into `.github/workflows/autonomous-strategy-factory.yml`.
- [x] T015 Run the binding latest-data replay without changing the preregistration.
- [x] T016 Run focused and full tests, ruff, YAML, diff, strict harness, handoff facts, and PR gate.
- [x] T017 Commit, push, open the grade-4 PR, and auto-merge after green checks.
- [x] T018 Verify deployment, production replay, 688-trial audit, and KIS no-order smoke.
- [x] T019 Refresh HANDOFF with empirical gate proof, strategy result, account truth, and next action.
