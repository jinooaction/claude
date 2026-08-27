# Tasks: Parallel Regime Edge Challenger

**Tests**: Required because this work changes production evidence liveness and creates a possible future first-capital strategy input.

## Phase 1: Preregister Before Results

- [x] T001 Record the root-cause split, non-goals, safety boundary, and measurable completion criteria in `spec.md`
- [x] T002 Freeze the 16 candidates, data split, costs, selection order, gates, and multiplicity budget in `contracts/preregistered-challenger.json`
- [x] T003 Record official token guidance and strategy research basis in `research.md`
- [x] T004 Commit and push the preregistration before downloading or evaluating production data

## Phase 2: Test-First Token Liveness Repair

- [x] T005 [US1] Add a CLI test proving explicit token cache overrides the temporary DB-adjacent default
- [x] T006 [US1] Add observer contract tests requiring temporary bars DB plus shared `data/kis_token.json`
- [x] T007 [US1] Implement `--token-cache` and wire only the parity observer to the shared token cache
- [x] T008 [US1] Verify token refresh failure remains closed and no token value is printed or persisted to the temporary directory

## Phase 3: Test-First Challenger

- [x] T009 [US2] Add exact-grid, fingerprint, no-look-ahead, weight-sum, turnover, and stress-trigger tests
- [x] T010 [US2] Add fixed-split, deterministic-selection, PBO/PSR, recent-segment, and cost symmetry tests
- [x] T011 [US3] Add result-contract mutation tests and invariant no-promotion/no-order assertions
- [x] T012 [US2] Implement the deterministic 16-candidate evaluator in `src/auto_invest/analytics/regime_adaptive_challenger.py`
- [x] T013 [US3] Implement the no-order JSON/Markdown probe and committed-contract validator

## Phase 4: Evidence and Controls

- [x] T014 Run the preregistered production-data probe once and record the complete result
- [x] T015 Run negative, planted-positive, one-month-shift, and higher-cost controls
- [x] T016 Explain whether failure comes from family PBO, holdout evidence, economics, recency, turnover, data, or implementation
- [x] T017 Re-run the production proxy-parity observer with the shared token and confirm no orders/capital changes

## Phase 5: Verification and Release

- [x] T018 Run full pytest, Ruff, JSON/YAML checks, strict harness, HANDOFF facts, and PR quality checks
- [ ] T019 Create and merge the grade-4 PR, then verify guarded dry-run deployment and current sidecars
- [ ] T020 Refresh `HANDOFF.md` with current strategy verdict, token liveness, and next observation through the normal merge path

## Phase 6: Post-Merge Zero-Capital Truthfulness

- [x] T021 Record the successful proxy-parity production rerun and the unrelated zero-capital error discovered in its log
- [x] T022 Add a regression contract requiring a positive numeric capital before live strategy performance observation
- [x] T023 Implement the zero-capital no-op without changing ladder decisions, capital, or order behavior
- [x] T024 Re-run zero-capital production autoarm and record the missing stderr file and leaked RETURN trap failures
- [x] T025 Add regression contracts for skipped-probe evidence files and success-path trap cleanup
- [x] T026 Implement both lifecycle fixes without changing ladder decisions, capital, or order behavior
- [ ] T027 Re-run production autoarm through decision and sidecar publication with no false errors or orders
- [ ] T028 Complete the final production evidence and HANDOFF closeout through the normal merge path

## Dependencies

- T001-T004 block all production-data evaluation.
- T005-T006 block T007-T008.
- T009-T011 block T012-T013.
- T012-T013 block T014-T016.
- T014-T018 block merge; T019 blocks handoff.
- T021 blocks T022-T023; T023 blocks T024; T024 blocks T025-T026; T026 blocks T027; T027 blocks T028.
