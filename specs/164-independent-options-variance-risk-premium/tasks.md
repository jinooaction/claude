# Tasks: Independent Options Variance Risk Premium

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Tests**: Required because this is grade-4 money-path evidence classification.

## Phase 1: Setup and Frozen Contracts

- [x] T001 Record the frozen source, candidate, timing, cost, split, objective, and tail-gate contract in `specs/164-independent-options-variance-risk-premium/`
- [x] T002 [P] Add source, chronology, cost, tail-metric, gate-routing, and candidate-count tests in `tests/unit/test_options_variance_risk_premium_factory.py`
- [x] T003 [P] Add command-line, prior-adoption, and fail-closed publication tests in `tests/integration/test_options_variance_risk_premium_factory_probe.py`

## Phase 2: Foundational Data and Candidate Identity

- [x] T004 Implement strict Cboe PUT/VIX, French daily factor, and FRED cash parsers in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T005 Implement monthly implied-realized variance alignment and month-next target chronology in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T006 Implement exactly 16 deterministic policies and unique fingerprints in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`

## Phase 3: Direct Options Premium Evidence (US1)

**Goal**: Produce direct cash-secured put-writing/cash candidate returns from official benchmark data.
**Independent Test**: Fixed source fixtures reproduce the same monthly returns, allocations, cost cases, and hashes.

- [x] T007 [US1] Implement passive PUT and positive variance-premium target weights in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T008 [US1] Implement annual implementation haircuts and allocation-turnover cost cases in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`

## Phase 4: Objective and Tail-Risk Gates (US2)

**Goal**: Judge standalone premium harvesting separately from optional timing enhancement.
**Independent Test**: Always-on premium and dynamic timing examples route independently while drawdown and expected shortfall remain blocking.

- [x] T009 [US2] Implement standalone live/paper gates and 95% expected-shortfall metrics in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T010 [US2] Implement the non-blocking timing-enhancement lane against matching passive PUT allocations in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`

## Phase 5: Transparent and Adaptive Timing (US3)

**Goal**: Compare tail guards and fixed expanding ridge predictions without future labels.
**Independent Test**: Every feature and label predates its target month, and holdout changes cannot alter the frozen winner.

- [x] T011 [US3] Implement tail-guarded policy weights and shock chronology in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T012 [US3] Implement deterministic expanding ridge predictions with fixed features and 60-label warm-up in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T013 [US3] Implement development selection, one-month embargo, untouched holdout, and prohibited post-hoc ranks in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`

## Phase 6: Gate and Prior-Adoption Audit (US4)

**Goal**: Prove whether the objective gate recognizes the real reference and explain prior non-adoption without rewriting history.
**Independent Test**: Reference, null, planted-signal, and prior-family fixtures emit stable classifications with retroactive promotion always false.

- [x] T014 [US4] Implement PUT reference/null controls and 16-candidate selection-power calibration in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T015 [US4] Implement released-family adoption classification with immutable original verdicts in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`

## Phase 7: Immediate Verdict and Money Boundary (US5)

**Goal**: Publish one reproducible 752-trial verdict without creating an executable options path.
**Independent Test**: The probe emits exact counts, hashes, gates, tail metrics, controls, audit, and mandatory live-parity blockers.

- [x] T016 [US5] Implement the no-order command-line probe in `scripts/options_variance_risk_premium_factory_probe.py`
- [x] T017 [US5] Run the first current-data replay and record the immutable result in `specs/164-independent-options-variance-risk-premium/production-result.md`
- [x] T018 [US5] Integrate the 16-trial options factory and append-only 752-trial contract in `.github/workflows/autonomous-strategy-factory.yml`
- [x] T019 [US5] Verify no broker/order/capital/margin/whitelist changes across the module, probe, and workflow

## Phase 8: Verification and Release

- [x] T020 Run focused tests, full pytest, ruff, YAML parse, diff check, strict harness, handoff facts, and PR quality validation
- [x] T021 Create and merge the grade-4 PR, verify deploy and production evidence, and run KIS read-only smoke
- [x] T022 Refresh `HANDOFF.md` and add the detailed spec-164 handoff with the current money-path state

## Dependencies

- T001 blocks all implementation.
- T002-T003 may run in parallel after T001.
- T004-T006 block T007-T016.
- T007-T008 block T009-T013.
- T009-T013 block T014-T016.
- T014-T016 block T017-T019.
- T001-T019 block T020; T020 blocks T021; T021 blocks T022.

## Implementation Strategy

1. Freeze contracts and tests before downloading candidate returns.
2. Build parsers, chronology, tail metrics, and candidate identity before selection.
3. Compare passive premium, transparent timing, tail guards, and fixed ridge under one bounded family.
4. Keep prior adoption audit descriptive and non-promoting.
5. Publish only after exact counts, controls, chronology, and safety checks, then complete production and handoff verification.
