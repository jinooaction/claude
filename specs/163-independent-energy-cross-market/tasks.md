# Tasks: Independent Energy Cross-Market Factory

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Tests**: Required because this is grade-4 money-path evidence classification.

## Phase 1: Setup and Frozen Contracts

- [x] T001 Record the frozen source, candidate, timing, model, cost, split, and objective-gate contract in `specs/163-independent-energy-cross-market/`
- [x] T002 [P] Add source parser and chronology tests in `tests/unit/test_energy_cross_market_factory.py`
- [x] T003 [P] Add command-line and fail-closed publication tests in `tests/integration/test_energy_cross_market_factory_probe.py`

## Phase 2: Foundational Data and Candidate Model

- [x] T004 Implement strict EIA monthly XLS and French industry ZIP parsers in `src/auto_invest/analytics/energy_cross_market_factory.py`
- [x] T005 Implement publication-lag alignment and cross-market feature snapshots in `src/auto_invest/analytics/energy_cross_market_factory.py`
- [x] T006 Implement exactly 16 deterministic policies and unique fingerprints in `src/auto_invest/analytics/energy_cross_market_factory.py`

## Phase 3: Direct Energy Strategy Evidence (US1)

**Goal**: Produce directly investable energy/cash candidate returns from official cross-market information.
**Independent Test**: Fixed source fixtures reproduce the same 16 candidate paths, costs, and source fingerprints.

- [x] T007 [US1] Implement three transparent rule-family target weights and 10/25/50bp candidate factors in `src/auto_invest/analytics/energy_cross_market_factory.py`
- [x] T008 [US1] Implement deterministic expanding ridge predictions with strict label chronology in `src/auto_invest/analytics/energy_cross_market_factory.py`

## Phase 4: Objective-Correct Gate Diagnosis (US2)

**Goal**: Separate standalone timing value from incumbent diversification value without lowering existing gates.
**Independent Test**: Synthetic examples can pass only the lane matching their declared objective, while real positive/null controls prove passability.

- [x] T009 [US2] Implement standalone live/paper gates and unchanged diversifier diagnostics in `src/auto_invest/analytics/energy_cross_market_factory.py`
- [x] T010 [US2] Preserve empirical positive/null controls for the diversifier lane and implement 16-family standalone holdout power diagnostics in `src/auto_invest/analytics/energy_cross_market_factory.py`

## Phase 5: Frozen Selection and Honest Machine Learning (US3)

**Goal**: Freeze one development winner and expose every holdout candidate only as prohibited post-hoc diagnosis.
**Independent Test**: Holdout mutations cannot change the selected candidate, and post-hoc winners always carry `promotion_allowed=false`.

- [x] T011 [US3] Implement development selection, one-month embargo, untouched holdout, all-candidate records, and post-hoc lock in `src/auto_invest/analytics/energy_cross_market_factory.py`

## Phase 6: Immediate Automated Verdict (US4)

**Goal**: Run current public data now and publish one reproducible decision with 736 cumulative trials.
**Independent Test**: The probe emits exact counts, hashes, both gate lanes, controls, power, and a stable summary.

- [x] T012 [US4] Implement the no-order command-line probe in `scripts/energy_cross_market_factory_probe.py`
- [x] T013 [US4] Run the first current-data replay and record the immutable result in `specs/163-independent-energy-cross-market/production-result.md`

## Phase 7: Money Boundary and Production (US5)

**Goal**: Produce canonical evidence without creating an executable XLE order path or changing capital.
**Independent Test**: The workflow requires 16/16 and 736/736, has no KIS secret, and a research pass remains live-parity blocked.

- [x] T014 [US5] Integrate the energy factory and append-only 736-trial contract in `.github/workflows/autonomous-strategy-factory.yml`
- [x] T015 [US5] Verify live-parity blockers and no broker/order/capital/whitelist changes across `src/auto_invest/analytics/energy_cross_market_factory.py` and `.github/workflows/autonomous-strategy-factory.yml`

## Phase 8: Verification and Release

- [x] T016 Run focused tests, full pytest, ruff, YAML parse, diff check, strict harness, handoff facts, and PR quality validation
- [ ] T017 Create and merge the grade-4 PR, verify deploy and production factory evidence, and run KIS read-only smoke
- [ ] T018 Refresh `HANDOFF.md` and add the detailed spec-163 handoff with the current money-path state

## Dependencies

- T001 blocks all implementation.
- T002-T003 may run in parallel after T001.
- T004-T006 block T007-T012.
- T007-T008 block T009-T011.
- T009-T011 block T012-T015.
- T012 and T014 block T013 production-shape verification.
- T001-T015 block T016; T016 blocks T017; T017 blocks T018.

## Implementation Strategy

1. Freeze contracts and tests first.
2. Build parsers, chronology, and candidate identity before evaluating returns.
3. Add transparent rules and fixed ridge learning under one exact search budget.
4. Evaluate both objective lanes, controls, and prohibited post-hoc diagnostics.
5. Publish only after exact count and chronology checks, then complete production verification and handoff.
