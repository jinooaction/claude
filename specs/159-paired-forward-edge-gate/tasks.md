# Tasks: Paired Forward Edge Gate

## Phase 1: Setup

- [x] T001 Register the Grade 4 feature and safety boundary in `specs/159-paired-forward-edge-gate/spec.md`
- [x] T002 Record the statistical decision and alternatives in `specs/159-paired-forward-edge-gate/research.md`
- [x] T003 Define evidence and compatibility contracts in `specs/159-paired-forward-edge-gate/data-model.md` and `specs/159-paired-forward-edge-gate/contracts/paired-forward-verdict.md`

## Phase 2: Foundational Calibration

- [x] T004 Write null, planted-edge, and determinism tests in `tests/unit/test_forward_gate_calibration.py`
- [x] T005 Implement deterministic legacy-vs-paired calibration in `src/auto_invest/analytics/forward_gate_calibration.py`
- [x] T006 Add the no-order probe and integration test in `scripts/forward_gate_calibration_probe.py` and `tests/integration/test_forward_gate_calibration_probe.py`

## Phase 3: User Story 1 - Paired Significance

- [x] T007 [US1] Add alignment, common-shock invariance, and zero-active-variance tests in `tests/unit/test_edge_verdict.py`
- [x] T008 [US1] Compute paired active PSR, DSR, and MinTRL in `src/auto_invest/portfolio/edge_verdict.py`
- [x] T009 [US1] Version and render paired evidence in `src/auto_invest/portfolio/edge_verdict.py`

## Phase 4: User Story 2 - Calibration Publication

- [x] T010 [US2] Run calibration before forward evaluation in `.github/workflows/rebalance-paper-forward.yml`
- [x] T011 [US2] Publish calibration JSON and summary beside the forward leaderboard in `.github/workflows/rebalance-paper-forward.yml`
- [x] T012 [US2] Add workflow contract tests in `tests/unit/test_forward_workflow_leaderboard_json.py`

## Phase 5: User Story 3 - Preserve Quality Evidence

- [x] T013 [US3] Keep absolute Sharpe/economic gates and add active information ratio assertions in `tests/unit/test_edge_verdict.py`
- [x] T014 [US3] Propagate significance method through `src/auto_invest/analytics/forward_tournament.py`
- [x] T015 [US3] Require paired method in `src/auto_invest/analytics/profit_evidence_engine.py` and update its tests

## Phase 6: User Story 4 - Fail-Closed Money Path

- [x] T016 [US4] Require paired evidence for live-entry revalidation in `src/auto_invest/portfolio/live_entry_revalidation.py`
- [x] T017 [US4] Reject legacy direct forward promotion in `src/auto_invest/portfolio/capital_ladder.py` and update tests
- [x] T018 [US4] Surface paired-method validity in `src/auto_invest/analytics/money_path.py` and update tests

## Phase 7: Verification and Release

- [x] T019 Run focused tests, full pytest, ruff, YAML parse, strict harness, and handoff facts
- [ ] T020 Validate the PR body, commit, push, create the PR, and merge after all gates pass
- [ ] T021 Confirm deployment, dispatch production forward replay, and verify versioned sidecar evidence
- [ ] T022 Refresh profit/capital/money evidence and KIS no-order smoke; record the actual strategy eligibility in `specs/159-paired-forward-edge-gate/production-result.md`
- [ ] T023 Refresh `HANDOFF.md`, validate, commit, push, merge, and confirm current production truth

## Dependencies

- T004-T006 establish calibration before the named strategy is replayed.
- T007-T009 implement the corrected statistic.
- T010-T012 publish only after calibration and verdict contracts exist.
- T013-T018 propagate and enforce the versioned evidence before production replay.
- T019-T023 release only after all implementation tasks pass.

## Independent Tests

- **US1**: common shocks leave active PSR unchanged; misalignment and zero active variance fail closed.
- **US2**: fixed calibration meets nominal null rates and paired detection exceeds legacy.
- **US3**: active significance cannot override negative excess or inferior absolute Sharpe.
- **US4**: legacy evidence cannot promote capital even when its verdict text says `EDGE_CONFIRMED`.
