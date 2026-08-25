# Tasks: Options Selection and Objective Repair

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Tests**: Required because this is grade-4 money-path evidence classification.

## Phase 1: Frozen Protocol and Baseline

- [x] T001 Record the frozen objectives, nested chronology, WPUT isolation, immutable candidate set, and no-promotion contract in `specs/165-options-selection-objective-repair/`
- [x] T002 Run the released spec-164 focused tests as the pre-change baseline
- [x] T003 [P] Add WPUT schema, source, freshness, and monthly-alignment tests in `tests/unit/test_options_variance_risk_premium_factory.py`
- [x] T004 [P] Add nested chronology, deterministic selection, and WPUT non-selection tests in `tests/unit/test_options_variance_risk_premium_factory.py`
- [x] T005 [P] Add separated-objective and permanent no-promotion tests in `tests/unit/test_options_variance_risk_premium_factory.py`
- [x] T006 [P] Add command-line and workflow contract tests in `tests/integration/test_options_variance_risk_premium_factory_probe.py`

## Phase 2: Independent Data and Nested Selection

- [x] T007 [US2] Implement strict Cboe WPUT parsing and aligned monthly factors in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T008 [US2] Implement expanding outer and inner folds with one-month embargoes and machine-readable chronology proof in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T009 [US2] Implement the frozen portfolio and timing lexicographic selectors using PUT only in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T010 [US3] Replay exact PUT-selected candidate IDs and weights on WPUT without re-selection in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`

## Phase 3: Objective Repair and Safe Publication

- [x] T011 [US1] Publish separate premium-existence, portfolio-adoption, and timing-value lanes in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T012 [US1] Preserve the released one-shot result under `legacy_selection` and correct the criterion questions in `src/auto_invest/analytics/options_variance_risk_premium_factory.py`
- [x] T013 [US3] Keep all historical repair results diagnostic-only and fail closed on missing WPUT or chronology evidence
- [x] T014 [US3] Add WPUT input and repaired-contract assertions to `scripts/options_variance_risk_premium_factory_probe.py` and `.github/workflows/autonomous-strategy-factory.yml`
- [x] T015 Verify the candidate count remains 16, global unique audit remains 752, and no broker/order/capital/margin/whitelist/cap file changes

## Phase 4: Whole-System Expert Review

- [x] T016 [US4] Inspect current data, research/statistics, forward evidence, execution, risk/order controls, automation, and observability truth surfaces
- [x] T017 [US4] Record severity-ranked findings, evidence, remediation, and separate order-automation/profit-edge readiness in `specs/165-options-selection-objective-repair/system-review.md`
- [x] T018 Run the current-data production replay and record immutable evidence in `specs/165-options-selection-objective-repair/production-result.md`

## Phase 5: Verification and Release

- [x] T019 Run focused tests, full pytest, Ruff, YAML parse, deterministic replay, diff check, strict harness, handoff facts, and PR quality validation
- [x] T020 Create and merge the grade-4 PR, verify deployment and production sidecars, and verify the latest KIS read-only smoke on an unchanged broker path
- [x] T021 Refresh `HANDOFF.md`, commit and merge the handoff, then re-check current money-path truth

## Dependencies

- T001-T002 block implementation.
- T003-T006 may be written in parallel after T001.
- T003-T006 block T007-T014.
- T007-T010 block T011-T014.
- T011-T015 block T016-T018.
- T001-T018 block T019; T019 blocks T020; T020 blocks T021.

## Implementation Strategy

1. Freeze the questions and chronology before observing WPUT results.
2. Add failing contracts before implementation.
3. Select on PUT inside nested folds and use WPUT only as an untouched replay construction.
4. Keep historical evidence separate from paper, canary, and live evidence.
5. Review the entire system from data to reconciled order state, then release only after full verification.
