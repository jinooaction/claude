# Tasks: Independent FX Carry and Gate Power

## Phase 1: Setup and Preregistration

- [x] T001 Freeze data universe, split, thresholds, 16-candidate grammar, and tiered verdict in `specs/155-fx-carry-gate-power/spec.md`.
- [x] T002 Record source, licensing, carry-risk, return-model, family-size, and whitelist decisions in `specs/155-fx-carry-gate-power/research.md`.
- [x] T003 Update `.specify/feature.json` and `CLAUDE.md` to spec 155.

## Phase 2: Foundational FX Data

- [x] T004 Add four H.10 spot and five OECD immediate-rate collection contracts in `deploy/public-data.toml`.
- [x] T005 Build quote-normalized point-in-time FX snapshots in `src/auto_invest/analytics/fx_carry_factory.py`.
- [x] T006 [P] Add coverage, freshness, lag, inverse-quote, and malformed-input tests in `tests/unit/test_fx_carry_factory.py` and `tests/unit/test_collect_public_data_workflow.py`.

## Phase 3: User Story 1 - Frozen FX Candidates

- [x] T007 [US1] Add `FxCarryPolicyConfig` validation in `src/auto_invest/config/rules.py`.
- [x] T008 [US1] Implement the shared long-only target-weight grammars in `src/auto_invest/strategy/rebalance.py`.
- [x] T009 [US1] Generate exactly 16 unique candidate IDs and fingerprints in `src/auto_invest/analytics/fx_carry_factory.py`.
- [x] T010 [US1] Implement foreign-cash/USD factors and 10/25/50bp costs in `src/auto_invest/analytics/fx_carry_factory.py`.
- [x] T011 [P] [US1] Add policy, deterministic weight, return-direction, and uniqueness tests in `tests/unit/test_fx_carry_factory.py`.

## Phase 4: User Story 2 - Point-in-Time Safety

- [x] T012 [US2] Enforce prior-month publication, 14/100-day freshness, and 120-month minimums in `src/auto_invest/analytics/fx_carry_factory.py`.
- [x] T013 [P] [US2] Add future-leakage, stale, zero-inverse, missing-month, and incomplete regressions in `tests/unit/test_fx_carry_factory.py`.

## Phase 5: User Story 3 - Gate Power Audit

- [x] T014 [US3] Extend deterministic calibration to family sizes 16/64 and Sharpe 0.20~0.80 in `src/auto_invest/analytics/edge_gate_calibration.py`.
- [x] T015 [US3] Add live false-acceptance and detection contracts plus paper-admission diagnostics in `src/auto_invest/analytics/edge_gate_calibration.py`.
- [x] T016 [P] [US3] Add deterministic curve, family-size, insufficient-power, and probe regressions in `tests/unit/test_edge_gate_calibration.py` and `tests/integration/test_edge_gate_calibration_probe.py`.

## Phase 6: User Story 4 - Tiered Decision

- [x] T017 [US4] Reconstruct 640 prior records and add family-local DSR/PBO, embargo, and holdout PSR in `src/auto_invest/analytics/fx_carry_factory.py`.
- [x] T018 [US4] Add live-grade and paper-only economic gates in `src/auto_invest/analytics/fx_carry_factory.py`.
- [x] T019 [US4] Emit one live candidate, one paper challenger, or no candidate without post-result tuning in `src/auto_invest/analytics/fx_carry_factory.py`.
- [x] T020 [P] [US4] Add one-gate failure, paper/live separation, synthetic all-pass, and holdout-selection tests in `tests/unit/test_fx_carry_factory.py`.

## Phase 7: User Story 5 - Research and Order Boundary

- [x] T021 [US5] Add optional FX policy to strategy fingerprints in `src/auto_invest/config/rules.py` and `src/auto_invest/portfolio/autoarm.py`.
- [x] T022 [US5] Add fail-closed optional order-preview wiring in `src/auto_invest/execution/rebalancer.py` and `src/auto_invest/cli.py`.
- [x] T023 [US5] Validate gate, candidate, data, code, freshness, target weights, verdict tier, and whitelist before broker access in `src/auto_invest/analytics/fx_carry_factory.py`.
- [x] T024 [P] [US5] Add parity, paper-tier rejection, stale rejection, whitelist rejection, and broker-not-called tests in `tests/unit/` and `tests/integration/`.

## Phase 8: Production and Verification

- [x] T025 Add the no-order probe and Korean summary in `scripts/fx_carry_factory_probe.py`.
- [x] T026 Wire data, calibration, 656-count audit, ledger, and sidecar in `.github/workflows/autonomous-strategy-factory.yml`.
- [x] T027 [P] Add probe and workflow contract tests in `tests/integration/`.
- [x] T028 Run immediate latest-data backtest and record the fixed pre-result thresholds and output.
- [x] T029 Run focused tests, full pytest, ruff, YAML, diff, strict harness, HANDOFF facts, and PR quality gate.
- [ ] T030 Commit, push, open a grade-4 PR, and auto-merge after green checks.
- [ ] T031 Verify deployment, production data, power curve, 656-trial decision, and KIS no-order smoke.
- [ ] T032 Record result, gate diagnosis, account truth, residual risk, and next family in handoff.

## Dependencies

- T004-T006 block every candidate evaluation.
- T007-T013 block return and point-in-time evaluation.
- T014-T016 block any live or paper classification.
- T017-T020 block final verdict.
- T021-T024 block order preparation but not a no-edge research report.
- T025-T032 require all implementation phases.

## Implementation Strategy

Build data and the pure no-order factory first, prove the 16-candidate family and power curve, then add optional
parity wiring. Do not change thresholds, currencies, or parameters after seeing the latest-data result.
