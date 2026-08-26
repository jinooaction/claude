# Tasks: Calibrated Research Entry

**Tests**: Required because this changes a grade-4 10% capital-entry gate.

## Phase 1: Frozen Contract

- [x] T001 Record the overlapping-gate root cause, thresholds, 17-family ledger, non-goals, and rollback
- [x] T002 Freeze fixed-seed calibration requirements before implementation
- [x] T003 Amend constitution X.4 to v10.1.0 in a dedicated forensic commit

## Phase 2: Test-first Contracts

- [x] T004 Add deterministic family-classification and full-ledger tests
- [x] T005 Add 16/64 family null-acceptance and planted-edge detection tests
- [x] T006 Add v3.1 consumer positive, mutation, legacy, and current-no-edge regression tests

## Phase 3: Implementation

- [x] T007 Implement shared research-family classification and audit summaries
- [x] T008 Publish v3.1 family ledger and calibrated thresholds from the options factory
- [x] T009 Recompute v3.1 family ledger, DSR, PBO, calibration, and program budget in the consumer
- [x] T010 Keep raw Bonferroni and DSR threshold as non-blocking diagnostics
- [x] T011 Update factory workflow assertions and sidecar contract

## Phase 4: Verification and Release

- [x] T012 Replay the current 752-row production evidence and record 17 families, PBO, verdict, and no-order state
- [x] T013 Run focused tests, full pytest, Ruff, YAML, strict harness, handoff facts, and PR quality checks
- [x] T014 Create and merge the grade-4 PR, verify the guarded deploy outcome and automatic sidecars, and confirm no order/capital change
- [x] T015 Refresh HANDOFF with post-merge money-path truth and send it through the normal merge path

## Dependencies

- T001-T003 block code changes.
- T004-T006 block T007-T011.
- T007-T011 block production replay and full verification.
- T012-T013 block PR merge; T014 blocks handoff.
