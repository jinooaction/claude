# Tasks: Forward Paper Ledger Integrity

## Phase 1: Setup and evidence

- [x] T001 Register the Grade 3 feature and clean epoch contract in `specs/160-forward-paper-ledger-integrity/spec.md`
- [x] T002 Record the production defect, decisions, alternatives, and rollback in `specs/160-forward-paper-ledger-integrity/research.md`
- [x] T003 Define measurement, epoch, and promotion contracts in `specs/160-forward-paper-ledger-integrity/data-model.md` and `specs/160-forward-paper-ledger-integrity/contracts/clean-forward-ledger.md`

## Phase 2: User Story 1 - Negative-cash interlock

- [x] T004 [US1] Add valid and negative-cash CLI tests in `tests/integration/test_forward_verdict_cli.py`
- [x] T005 [US1] Reject invalid paper snapshots before audit append and expose valid measurement metadata in `src/auto_invest/cli.py`

## Phase 3: User Story 2 - Clean epoch

- [x] T006 [P] [US2] Add seven-track producer/consumer path assertions in `tests/unit/test_security_workflow_hardening.py` and `tests/integration/test_candidate_result_executor_probe.py`
- [x] T007 [P] [US2] Update candidate history path expectations in `tests/unit/test_candidate_history_support.py`
- [x] T008 [US2] Move all observation-helper producers and consumers to v2 paths in `deploy/observe-on-instance.sh`
- [x] T009 [US2] Move candidate history and cross-asset defaults to v2 paths in `src/auto_invest/analytics/candidate_history_support.py`, `scripts/daily_cross_asset_ml_probe.py`, and `src/auto_invest/analytics/daily_cross_asset_ml.py`

## Phase 4: User Story 3 - Production truth

- [x] T010 [US3] Add clean epoch labeling and contract tests in `.github/workflows/rebalance-paper-forward.yml` and `tests/unit/test_forward_workflow_leaderboard_json.py`
- [ ] T011 [US3] Record legacy forward invalidation and exact historical evidence separation in `specs/160-forward-paper-ledger-integrity/production-result.md`

## Phase 5: Verification and release

- [x] T012 Run focused tests, full pytest, ruff, YAML, shell syntax, diff check, strict harness, and handoff facts
- [ ] T013 Validate PR body, commit, push, create PR, and merge after all gates pass
- [ ] T014 Confirm deployment and run a clean production forward replay
- [ ] T015 Refresh profit, capital, money, and KIS evidence and record actual eligibility
- [ ] T016 Refresh HANDOFF, validate, commit, push, merge, and confirm production truth

## Dependencies

- T004-T005 block publication of new invalid observations.
- T006-T010 must move as one atomic epoch switch; partial path migration is forbidden.
- T011-T016 depend on production replay from the clean epoch.

## Independent Tests

- **US1**: negative cash exits nonzero and appends no snapshot; valid cash appends one.
- **US2**: all seven tracks and named consumers resolve only to v2 paths.
- **US3**: production reports insufficient clean data and never reuses legacy PSR or counts.
