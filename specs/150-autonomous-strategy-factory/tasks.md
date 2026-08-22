# Tasks: 자동 전략 공장과 연구 캐너리

## Phase 1: Setup and Safety Contract

- [x] T001 Create full grade-4 SDD artifacts in `specs/150-autonomous-strategy-factory/`.
- [x] T002 Update `.specify/feature.json` to point at spec 150.

## Phase 2: Foundational Trial Science

- [x] T003 [P] Add PBO and full-trial DSR helpers in `src/auto_invest/analytics/backtest_overfitting.py`.
- [x] T004 [P] Add statistical regressions in `tests/unit/test_backtest_overfitting.py`.
- [x] T005 Define candidate, trial, batch, and decision models in `src/auto_invest/analytics/strategy_factory.py`.

## Phase 3: User Story 1 - Real Candidate Generation

- [x] T006 [US1] Generate four deterministic live-expressible families and 64 unique candidates in `src/auto_invest/analytics/strategy_factory.py`.
- [x] T007 [US1] Render candidate-specific TOML and exact strategy fingerprints in `src/auto_invest/analytics/strategy_factory.py`.
- [x] T008 [P] [US1] Add 64-candidate determinism and config parse tests in `tests/unit/test_strategy_factory.py`.

## Phase 4: User Story 2 - Honest Batch Evaluation

- [x] T009 [US2] Implement chronological factor replay, cost stresses, outer segments, and benchmark comparison in `src/auto_invest/analytics/strategy_factory.py`.
- [x] T010 [US2] Implement all-trial gates and deterministic winner selection in `src/auto_invest/analytics/strategy_factory.py`.
- [x] T011 [P] [US2] Add false-winner, incomplete-ledger, cost, and gate tests in `tests/unit/test_strategy_factory.py`.
- [x] T012 [US2] Add CLI probe and JSON/Markdown artifacts in `scripts/strategy_factory_probe.py`.
- [x] T013 [P] [US2] Add probe integration tests in `tests/integration/test_strategy_factory_probe.py`.

## Phase 5: User Story 4 - Autonomous Execution Loop

- [x] T014 [US4] Add `.github/workflows/autonomous-strategy-factory.yml` to execute and publish the 64-trial sidecar.
- [x] T015 [US4] Feed factory evidence into autonomous work, liveness, and next-family suppression paths.
- [x] T016 [P] [US4] Add workflow and evidence-collection regressions in `tests/integration/test_strategy_factory_workflow.py`.

## Phase 6: User Story 3 - 10 Percent Research Canary

- [x] T017 [US3] Amend constitution X.4 to add the 10% research canary while preserving existing 20% and higher gates in `.specify/memory/constitution.md`.
- [x] T018 [US3] Add research-canary evidence parsing and fail-closed first-entry revalidation in `src/auto_invest/portfolio/live_entry_revalidation.py`.
- [x] T019 [US3] Add rung 1=10% and shift existing ladder rungs without weakening downward rules in `src/auto_invest/portfolio/capital_ladder.py`.
- [x] T020 [US3] Wire factory evidence through `.github/workflows/forward-edge-autoarm.yml` and `.github/workflows/rebalance-live-canary.yml`.
- [x] T021 [P] [US3] Add capital ladder, entry revalidation, workflow, and constitution regressions in `tests/unit/`.

## Phase 7: Verification and Release

- [x] T022 Run targeted tests, full pytest, ruff, shell/YAML, diff, strict harness, HANDOFF facts, and PR quality gate.
- [ ] T023 Commit K-meta changes with `this changes the safety perimeter`, push, open grade-4 PR, and auto-merge.
- [ ] T024 Verify deploy, run the strategy factory on production data, and inspect the 64-trial decision.
- [x] T025 If and only if a complete winner exists, run hardened no-order checks and autoarm; otherwise confirm rung 0 and next independent batch.
- [ ] T026 Refresh HANDOFF with actual winner/no-winner, account state, orders, fills, and remaining risk.
