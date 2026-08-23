# Tasks: Independent Treasury Carry Factory

## Phase 1: Setup and Pre-registration

- [x] T001 Freeze the 64-candidate grammar and 576-trial accounting in `specs/152-treasury-carry-factory/spec.md`.
- [x] T002 Record official-source, return-approximation, missing-data, and live-expression decisions in `specs/152-treasury-carry-factory/research.md`.
- [x] T003 Update `.specify/feature.json` and `CLAUDE.md` to point at spec 152.

## Phase 2: Foundational Treasury Data

- [x] T004 [P] Add FRED DGS3MO, DGS5, and DGS30 collection and maturity-specific validation in `deploy/public-data.toml` and `src/auto_invest/market_data/public_data.py`.
- [x] T005 Build point-in-time monthly and latest Treasury curve snapshots in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T006 [P] Add five-maturity coverage, staleness, 30-year-gap, and future-observation tests in `tests/unit/test_treasury_carry_factory.py` and `tests/unit/test_public_data.py`.

## Phase 3: User Story 1 - Independent Treasury Candidates

**Goal**: Generate and evaluate exactly 64 deterministic maturity-rotation candidates.

**Independent test**: Candidate generation returns 64 unique IDs and fingerprints across all four families.

- [x] T007 [US1] Add `TreasuryCarryPolicyConfig` validation in `src/auto_invest/config/rules.py`.
- [x] T008 [US1] Implement carry-roll, carry-rate-trend, defensive-curve, and curve-barbell scores in `src/auto_invest/strategy/rebalance.py`.
- [x] T009 [US1] Implement five-sleeve rolling-par return approximation and cost accounting in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T010 [US1] Generate exactly 64 unique live-expressible candidates in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T011 [P] [US1] Add policy validation, family coverage, deterministic weights, and candidate uniqueness tests in `tests/unit/test_treasury_carry_factory.py`.

## Phase 4: User Story 2 - Point-in-time Data Safety

**Goal**: Use only yields observable by each decision date and reject unsafe latest evidence.

**Independent test**: A future-dated, stale, or missing maturity causes the relevant gate to fail before broker contact.

- [x] T012 [US2] Apply month-end observation and next-month decision alignment in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T013 [US2] Add completeness, publication-safety, latest-freshness, and explicit-gap gates in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T014 [P] [US2] Add future-leakage, malformed CSV, stale latest data, and missing maturity regressions in `tests/unit/test_treasury_carry_factory.py`.

## Phase 5: User Story 3 - Honest 576-Trial Accounting

**Goal**: Preserve all 512 previous trials and penalize the 64 new trials together.

**Independent test**: Only 512 prior plus 64 current unique fingerprints produces a complete multiplicity decision.

- [x] T015 [US3] Parse and validate the prior factory's 512 records and segment scores in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T016 [US3] Compute DSR, PBO, PSR, segment stability, benchmark, cost, and drawdown gates over 576 trials in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T017 [P] [US3] Add exact-count, missing-prior, duplicate-fingerprint, and partial-trial regressions in `tests/unit/test_treasury_carry_factory.py`.

## Phase 6: User Story 4 - Research and Order Parity

**Goal**: Make research and order preview consume the same Treasury target-weight function and bound evidence.

**Independent test**: The same policy and snapshot yield byte-equivalent weights; mismatches fail before broker access.

- [x] T018 [US4] Add optional Treasury carry policy to portfolio fingerprints in `src/auto_invest/config/rules.py` and `src/auto_invest/portfolio/autoarm.py`.
- [x] T019 [US4] Wire validated Treasury evidence through `src/auto_invest/execution/rebalancer.py` and `src/auto_invest/cli.py` without changing default portfolios.
- [x] T020 [US4] Add candidate, data, code, freshness, and target-weight digest validation in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T021 [P] [US4] Add research/order parity, long-only bounds, stale rejection, and broker-not-called regressions in `tests/unit/` and `tests/integration/`.

## Phase 7: User Story 5 - Promotion and Diversification Gates

**Goal**: Promote only an economically useful independent edge.

**Independent test**: Any single failed benchmark, diversification, cost, or risk gate removes the selected candidate and deploy config.

- [x] T022 [US5] Add equal Treasury ladder and existing three-asset incumbent benchmarks in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T023 [US5] Add 80/20 blend Sharpe, drawdown, and correlation gates in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T024 [US5] Emit exactly one selected candidate only on all-pass and the next independent family otherwise in `src/auto_invest/analytics/treasury_carry_factory.py`.
- [x] T025 [P] [US5] Add one-gate-at-a-time fail-closed and synthetic all-pass tests in `tests/unit/test_treasury_carry_factory.py`.

## Phase 8: Autonomous Production and Verification

- [x] T026 Add the no-order probe and Korean summary in `scripts/treasury_carry_factory_probe.py`.
- [x] T027 Wire prior evidence, five yield inputs, exact-count checks, deduplication, and sidecar publication in `.github/workflows/autonomous-strategy-factory.yml`.
- [x] T028 [P] Add probe, workflow contract, and 15-minute performance tests in `tests/integration/test_treasury_carry_factory_probe.py` and `tests/integration/test_strategy_factory_workflow.py`.
- [x] T029 Run focused tests, full pytest, ruff, YAML/shell checks, strict harness, HANDOFF facts, and diff check.
- [x] T030 Commit, push, open a grade-4 PR with full quality evidence, and auto-merge only after all gates pass.
- [x] T031 Verify deployment, refresh public data, run the production factory, and inspect the 576-trial no-order decision.
- [x] T032 If and only if a full winner exists, run hardened no-order parity and existing canary eligibility; otherwise prove rung 0, capital 0, orders 0, and fills 0.
- [x] T033 Refresh `HANDOFF.md` with production data, decision, account state, and the next independent strategy family.

## Dependencies

- T004-T006 block all candidate evaluation because the five-maturity point-in-time curve is foundational.
- T007-T014 block multiplicity and promotion because current trials must be complete and leakage-free.
- T015-T017 block any winner because exact prior accounting is mandatory.
- T018-T021 block canary eligibility but do not block research-only no-winner publication.
- T022-T025 block final promotion.
- T026-T033 require every implementation phase.

## Parallel Opportunities

- T004 and the initial T006 collector tests can proceed together.
- T011, T014, T017, T021, and T025 are isolated test groups after their corresponding contracts exist.
- T028 workflow/probe contract tests can be prepared while T026-T027 are being completed.

## Implementation Strategy

1. Finish official point-in-time data and the pure no-order factory first.
2. Prove exact 576-trial accounting and all promotion gates before execution integration.
3. Add optional parity wiring with default behavior unchanged.
4. Never relax a failed threshold or add a post-result candidate to manufacture a winner.
