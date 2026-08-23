# Tasks: 독립 거시 레짐 전략군

## Phase 1: Setup and Pre-registration

- [x] T001 Freeze the four-family 64-candidate grammar in `src/auto_invest/analytics/macro_strategy_factory.py`.
- [x] T002 Freeze the three 64-trial exploratory replay grammars in `src/auto_invest/analytics/macro_strategy_factory.py`.
- [x] T003 Update `.specify/feature.json` and SDD pointers for spec 151.

## Phase 2: Foundational Macro Data

- [x] T004 [P] Add FRED `CPIAUCNS` and `SAHMREALTIME` collection and BLS/Cboe cross-checks in `deploy/public-data.toml` and `src/auto_invest/market_data/public_data.py`.
- [x] T005 Build deep 10y-2y spread and point-in-time macro snapshots in `src/auto_invest/market_data/macro_regime.py`.
- [x] T006 [P] Add publication-lag, real-time-labor, stale-data, and coverage tests in `tests/unit/test_macro_regime.py` and `tests/unit/test_public_data.py`.

## Phase 3: User Story 1 - Four Independent Families

- [x] T007 [US1] Implement curve-cycle, inflation-direction, labor-growth-shock, and VIX-shock-recovery policies in `src/auto_invest/analytics/macro_strategy_factory.py`.
- [x] T008 [US1] Generate exactly 64 unique live-expressible candidates and policy fingerprints in `src/auto_invest/analytics/macro_strategy_factory.py`.
- [x] T009 [P] [US1] Add determinism, uniqueness, and family-coverage tests in `tests/unit/test_macro_strategy_factory.py`.

## Phase 4: User Story 2 - Point-in-time Data Safety

- [x] T010 [US2] Apply next-period market signals and 45-day macro publication lag in `src/auto_invest/analytics/macro_strategy_factory.py`.
- [x] T011 [US2] Add source freshness, cross-check, and vintage-safety gates in `src/auto_invest/analytics/macro_strategy_factory.py`.
- [x] T012 [P] [US2] Add future-leakage and malformed-source regressions in `tests/unit/test_macro_strategy_factory.py`.

## Phase 5: User Story 3 - Honest Trial Accounting

- [x] T013 [US3] Reproduce all 192 observed exploratory trials with stable IDs and segment scores in `src/auto_invest/analytics/macro_strategy_factory.py`.
- [x] T014 [US3] Merge 256 production, 192 exploratory, and 64 current trials into a 512-trial DSR/PBO decision in `src/auto_invest/analytics/macro_strategy_factory.py`.
- [x] T015 [P] [US3] Add missing-replay, duplicate-fingerprint, and exact-512 regressions in `tests/unit/test_macro_strategy_factory.py`.

## Phase 6: User Story 4 - Research and Live Parity

- [x] T016 [US4] Add optional macro policy config and fingerprint fields in `src/auto_invest/config/rules.py` and `src/auto_invest/portfolio/autoarm.py`.
- [x] T017 [US4] Implement one shared macro target-weight function in `src/auto_invest/strategy/rebalance.py`.
- [x] T018 [US4] Wire validated snapshots through `src/auto_invest/execution/rebalancer.py` and `src/auto_invest/cli.py` with no-order stale blocking.
- [x] T019 [US4] Fetch and validate macro sidecar evidence before preview/live execution in `deploy/live-canary-on-instance.sh`.
- [x] T020 [P] [US4] Add research/live parity and broker-not-called-on-stale tests in `tests/unit/` and `tests/integration/`.

## Phase 7: Autonomous Factory and Production

- [x] T021 Add macro inputs, 192 replay, sequence advance, and sidecar fields in `scripts/macro_strategy_factory_probe.py` and `.github/workflows/autonomous-strategy-factory.yml`.
- [x] T022 [P] Add probe and workflow contract tests in `tests/integration/test_macro_strategy_factory_probe.py` and `tests/integration/test_strategy_factory_workflow.py`.
- [x] T023 Run targeted tests, full pytest, ruff, YAML/shell checks, strict harness, HANDOFF facts, and PR quality gate using `scripts/agent_harness_probe.py` and `scripts/check_handoff_facts.py`.
- [x] T024 Add and run a 15-minute upper-bound performance regression for 192 replay plus 64 official trials in `tests/integration/test_macro_strategy_factory_probe.py`.
- [ ] T025 Commit, push, open the grade-4 PR with `.github/pull_request_template.md`, and auto-merge only when all gates pass.
- [ ] T026 Verify deployment, refresh public-data, execute `.github/workflows/autonomous-strategy-factory.yml`, and inspect the 512-trial production decision.
- [ ] T027 If and only if a full winner exists, run hardened no-order parity through `.github/workflows/forward-edge-autoarm.yml`; otherwise prove rung 0 and orders 0.
- [ ] T028 Refresh `HANDOFF.md` with the actual macro winner/no-winner, data coverage, account state, orders, and next independent family.

## Dependencies

- T004~T006 block T007~T015 because point-in-time macro inputs are required.
- T007~T015 block live parity work because a frozen policy contract is required.
- T016~T020 block production eligibility but not no-live factory execution.
- T021~T028 require all prior phases.

## Implementation Strategy

1. Complete point-in-time data and no-live 512-trial accounting first.
2. Prove policy determinism and research/live parity with no orders.
3. Release the production factory before considering any 10% research canary.
4. Never weaken a gate to manufacture a winner.
