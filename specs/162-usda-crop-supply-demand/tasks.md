# Tasks: USDA Crop Supply-Demand Factory

## Phase 1: Preregistration

- [x] T001 Create full grade-4 SDD and freeze the 16-candidate grammar, split, costs, and unchanged gates in `specs/162-usda-crop-supply-demand/`.
- [x] T002 Add parser and candidate identity tests in `tests/unit/test_usda_crop_supply_demand_factory.py`.

## Phase 2: Point-in-Time Data

- [x] T003 [US1] Implement official ESMIS release discovery and source lineage in `src/auto_invest/analytics/usda_crop_supply_demand_factory.py`.
- [x] T004 [US1] Implement robust corn, wheat, and soybean report parsing and same-year revisions in `src/auto_invest/analytics/usda_crop_supply_demand_factory.py`.
- [x] T005 [US1] Add malformed, duplicate, rollover, missing-month, and future-leakage regressions in `tests/unit/test_usda_crop_supply_demand_factory.py`.

## Phase 3: Frozen Backtest

- [x] T006 [US2] Implement 16 policy identities, GLD/IEF factors, costs, development selection, embargo, and holdout in `src/auto_invest/analytics/usda_crop_supply_demand_factory.py`.
- [x] T007 [US2] Add split isolation, exact 720-audit, economics, and deterministic-result tests in `tests/unit/test_usda_crop_supply_demand_factory.py`.
- [x] T008 [US3] Add unchanged gate decisions and actual-holdout power diagnosis in `src/auto_invest/analytics/usda_crop_supply_demand_factory.py`.

## Phase 4: Automation And Safety

- [x] T009 [US4] Add the no-order probe in `scripts/usda_crop_supply_demand_factory_probe.py`.
- [x] T010 [US4] Wire exact-count checks and sidecar publication in `.github/workflows/autonomous-strategy-factory.yml`.
- [x] T011 [P] [US4] Add probe and workflow contract tests in `tests/integration/test_usda_crop_supply_demand_factory_probe.py` and `tests/integration/test_strategy_factory_workflow.py`.

## Phase 5: Verification And Release

- [ ] T012 Run latest official-data replay and record immutable metrics in `specs/162-usda-crop-supply-demand/production-result.md`.
- [ ] T013 Run focused/full tests, ruff, YAML, strict harness, handoff facts, and PR body gate.
- [ ] T014 Commit, push, open and auto-merge a clean PR; verify deploy and production strategy-factory replay.
- [ ] T015 Run no-order KIS smoke and money/capital checks, then refresh `HANDOFF.md`.

## Dependencies

T001-T005 establish point-in-time inputs. T006-T008 require complete snapshots. T009-T011 require the factory contract. T012-T015 require all implementation tasks.
