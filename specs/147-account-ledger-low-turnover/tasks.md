# Tasks: 신뢰 가능한 라이브 증거와 저회전 AI 후보

## Phase 1: Setup

- [x] T001 Create grade-4 SDD artifacts in `specs/147-account-ledger-low-turnover/`.

## Phase 2: Foundational

- [x] T002 Add measurement-contract model and deterministic fingerprint in `src/auto_invest/performance/measurement_contract.py`.
- [x] T003 [P] Add contract tests in `tests/unit/test_strategy_measurement_contract.py`.

## Phase 3: User Story 1 - Trustworthy live evidence

- [x] T004 [US1] Add strategy-scope fill filtering and exclusion evidence in `src/auto_invest/performance/engine.py`.
- [x] T005 [US1] Wire verified opening-position exclusions into live performance and NAV CLI paths in `src/auto_invest/cli.py`.
- [x] T006 [US1] Add measurement contract fields and latest-contract filtering in `src/auto_invest/persistence/audit.py` and `src/auto_invest/portfolio/growth.py`.
- [x] T007 [US1] Add read-only resume readiness evaluator in `src/auto_invest/reconciliation/readiness.py`.
- [x] T008 [US1] Wire production observe commands without automatic halt release in `deploy/observe-on-instance.sh` and `deploy/live-canary-on-instance.sh`.
- [x] T009 [US1] Add unit and integration regressions in `tests/unit/` and `tests/integration/`.

## Phase 4: User Story 2 - Low-turnover AI challenger

- [x] T010 [US2] Add low-turnover allocation policy and report in `src/auto_invest/analytics/daily_cross_asset_ml.py`.
- [x] T011 [US2] Add deterministic policy and fail-closed gate tests in `tests/unit/test_low_turnover_daily_ml.py`.
- [x] T012 [US2] Add no-live CLI/workflow evidence path in `scripts/` and `.github/workflows/`.

## Phase 5: Validation and release

- [x] T013 Run targeted tests, `uv run pytest`, and `uv run ruff check src tests`.
- [x] T014 Run strict harness, HANDOFF facts, diff check, and PR quality gate.
- [x] T015 Commit, push, open and merge the PR, then verify deployment sidecars.
- [x] T016 Refresh `HANDOFF.md`, commit, push, merge, and verify final main state.
