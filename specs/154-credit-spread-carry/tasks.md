# Tasks: Independent Credit Spread Carry

## Phase 1: Setup and Pre-registration

- [x] T001 Freeze objective, split, thresholds, 64-candidate grammar, and 640-audit contract in `specs/154-credit-spread-carry/spec.md`.
- [x] T002 Record source, licensing, return-model, and whitelist decisions in `specs/154-credit-spread-carry/research.md`.
- [x] T003 Update `.specify/feature.json` and `CLAUDE.md` to spec 154.

## Phase 2: Foundational Credit Data

- [x] T004 Add HQM 10-year and 20-year collection and monthly validation in `deploy/public-data.toml`.
- [x] T005 Build point-in-time credit snapshots and data-quality evidence in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T006 [P] Add HQM coverage, freshness, missing-data, and future-observation tests in `tests/unit/test_collect_public_data_workflow.py` and `tests/unit/test_credit_spread_factory.py`.

## Phase 3: User Story 1 - Frozen Credit Candidates

- [x] T007 [US1] Add `CreditSpreadPolicyConfig` validation in `src/auto_invest/config/rules.py`.
- [x] T008 [US1] Implement the four shared target-weight grammars in `src/auto_invest/strategy/rebalance.py`.
- [x] T009 [US1] Generate exactly 64 unique candidate IDs and fingerprints in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T010 [US1] Implement corporate/Treasury return factors and 10/25/50bp costs in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T011 [P] [US1] Add policy, family, deterministic weight, and uniqueness tests in `tests/unit/test_credit_spread_factory.py`.

## Phase 4: User Story 2 - Point-in-time Safety

- [x] T012 [US2] Enforce as-of alignment, 70-day latest freshness, and 120-month minimums in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T013 [P] [US2] Add future-leakage, stale, malformed, and incomplete regressions in `tests/unit/test_credit_spread_factory.py`.

## Phase 5: User Story 3 - Calibrated 640-Trial Decision

- [x] T014 [US3] Validate the complete prior 576 audit records in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T015 [US3] Add development-only selection, effective trials, DSR/PBO diagnostics, embargo, and holdout PSR in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T016 [P] [US3] Add exact-count, family-boundary, duplicate, and holdout-selection regressions in `tests/unit/test_credit_spread_factory.py`.

## Phase 6: User Story 4 - Research and Order Parity

- [x] T017 [US4] Add optional credit policy to strategy fingerprints in `src/auto_invest/config/rules.py` and `src/auto_invest/portfolio/autoarm.py`.
- [x] T018 [US4] Add fail-closed optional order-preview wiring in `src/auto_invest/execution/rebalancer.py`.
- [x] T019 [US4] Validate gate, candidate, data, code, freshness, and target-weight evidence in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T020 [P] [US4] Add parity, stale rejection, whitelist-not-authorized, and broker-not-called regressions in `tests/unit/` and `tests/integration/`.

## Phase 7: User Story 5 - Economic Gates

- [x] T021 [US5] Add incumbent and investment-grade ladder benchmarks in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T022 [US5] Add 80/20 blend PSR, Sharpe, drawdown, correlation, and 50bp cost gates in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T023 [US5] Emit one research candidate only on all-pass, otherwise advance to FX carry in `src/auto_invest/analytics/credit_spread_factory.py`.
- [x] T024 [P] [US5] Add one-gate-at-a-time failure and synthetic all-pass tests in `tests/unit/test_credit_spread_factory.py`.

## Phase 8: Production and Verification

- [x] T025 Add the no-order probe and Korean summary in `scripts/credit_spread_factory_probe.py`.
- [x] T026 Wire data, prior evidence, exact counts, ledger, and sidecar in `.github/workflows/autonomous-strategy-factory.yml`.
- [x] T027 [P] Add probe and workflow contract tests in `tests/integration/`.
- [x] T028 Run focused tests, full pytest, ruff, diff, strict harness, HANDOFF facts, and PR quality gate.
- [ ] T029 Commit, push, open a grade-4 PR, and auto-merge after green checks.
- [ ] T030 Verify deployment, production public data, 640-trial decision, and KIS no-order smoke.
- [ ] T031 Record production result, account truth, residual risk, and next family in `HANDOFF.md` and a detailed handoff.

## Dependencies

- T004-T006 block every candidate evaluation.
- T007-T013 block statistical evaluation.
- T014-T016 block any winner.
- T017-T020 block research eligibility but not a no-edge research report.
- T021-T024 block final promotion.
- T025-T031 require all implementation phases.

## Implementation Strategy

Implement the data and pure no-order factory first, prove the family boundary and untouched holdout, then add
optional parity wiring. Do not tune thresholds or add candidates after seeing the production result.
