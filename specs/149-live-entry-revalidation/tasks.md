# Tasks: 최신 엣지 재검증과 병렬 탐색

## Phase 1: Specification

- [x] T001 Create grade-4 SDD artifacts in specs/149-live-entry-revalidation/.

## Phase 2: First-Entry Safety

- [x] T002 [P] [US1] Add live-entry revalidation core and probe in src/auto_invest/portfolio/live_entry_revalidation.py and scripts/live_entry_revalidation_probe.py.
- [x] T003 [P] [US1] Add fail-closed revalidation tests in tests/unit/test_live_entry_revalidation.py.
- [x] T004 [US1] Wire pre-order revalidation into .github/workflows/rebalance-live-canary.yml.
- [x] T005 [US1] Auto-demote unfilled rung 1 when current exploration evidence fails in src/auto_invest/portfolio/capital_ladder.py.
- [x] T006 [US1] Add ladder and workflow regressions in tests/unit/test_capital_ladder.py and tests/unit/test_live_entry_revalidation_workflow.py.

## Phase 3: Monitoring and Parallel Research

- [x] T007 [P] [US2] Add targeted sidecar ref retry in .github/workflows/pipeline-liveness.yml and regression test.
- [x] T008 [P] [US3] Emit evidence-fingerprinted no-live challenger beside forward observation wait in src/auto_invest/analytics/autonomous_work_execution.py.
- [x] T009 [US3] Add autonomous-work challenger selection regressions in tests/integration/test_autonomous_work_execution_probe.py.

## Phase 4: Post-Trade Closure

- [x] T010 [US4] Add post-trade reconciliation result to .github/workflows/rebalance-live-canary.yml and its sidecar.
- [x] T011 [US4] Add workflow closure assertions in tests/unit/test_live_entry_revalidation_workflow.py.

## Phase 5: Validation and Release

- [x] T012 Run targeted and full tests, ruff, shell/YAML, harness, handoff, and PR quality gates.
- [x] T013 Commit with safety-perimeter marker, push, open PR, and auto-merge.
- [ ] T014 Verify deploy and no-order production preflight, then refresh HANDOFF.
- [x] T015 Fix the observed profit-evidence liveness false MISSING at the producer timestamp contract and add a regression.
- [x] T016 Feed strategy-scope live performance into the capital ladder so zero-fill stale entry approval demotes automatically.
