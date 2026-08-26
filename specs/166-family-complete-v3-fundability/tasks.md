# Tasks: Family Complete V3 and Fundability

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`  
**Tests**: Required because this changes grade-4 money-path entry gates.

## Phase 1: Frozen Contract and Baseline

- [x] T001 Freeze independent evidence, 752-trial correction, fundability thresholds, risk boundaries, and rollback in `specs/166-family-complete-v3-fundability/`
- [x] T002 Run the released focused gate and rebalancer tests before code changes
- [x] T003 [P] Add producer-self-report, audit-row, family-tail, parity, and legacy migration tests in `tests/unit/test_factory_evidence.py`
- [x] T004 [P] Add program-wide multiplicity tests in `tests/unit/test_factory_evidence.py`
- [x] T005 [P] Add exact lot/minimum/cap/quote/weight-error tests in `tests/unit/test_fundability.py`
- [x] T006 [P] Add ladder, first-entry, CLI, and workflow fail-closed tests in existing unit and integration test files

## Phase 2: Independent Factory Evidence

- [x] T007 [US1] Recompute audit rows, current family, uniqueness, selection identity, and parity in `src/auto_invest/portfolio/factory_evidence.py`
- [x] T008 [US2] Compute global Bonferroni error and require standardized PSR/DSR/PBO in `src/auto_invest/portfolio/factory_evidence.py`
- [x] T009 [US1] Make legacy and v2 assessments diagnostic-only in `src/auto_invest/portfolio/factory_evidence.py` and `scripts/factory_evidence_gate.py`
- [x] T010 [US1] Add the v3 production assertion and sidecar evidence to `.github/workflows/autonomous-strategy-factory.yml`

## Phase 3: Exact Fundability

- [x] T011 [US3] Implement pure projected-order and target-weight assessment in `src/auto_invest/portfolio/fundability.py`
- [x] T012 [US3] Publish fundability in dry-run rebalance output using existing planner inputs in `src/auto_invest/execution/rebalancer.py` and `src/auto_invest/cli.py`
- [x] T013 [US3] Require current-NAV 10% preview fundability before research rung entry in `src/auto_invest/cli.py`, `src/auto_invest/portfolio/capital_ladder.py`, and `.github/workflows/forward-edge-autoarm.yml`
- [x] T014 [US3] Require the same preview before first strategy fill in `src/auto_invest/portfolio/live_entry_revalidation.py`, `scripts/live_entry_revalidation_probe.py`, and `.github/workflows/rebalance-live-canary.yml`
- [x] T015 [US3] Verify demotion, halt, exits, and active-live risk paths remain unchanged

## Phase 4: Constitution and Production Proof

- [x] T016 Amend constitution X.4 to v10.0.0 in a dedicated forensic commit without changing the kernel manifest
- [x] T017 Run current 752-row production evidence through v3 and record the exact result in `specs/166-family-complete-v3-fundability/production-result.md`
- [x] T018 Run focused tests, full pytest, Ruff, YAML, strict harness, handoff facts, and PR quality validation
- [ ] T019 Create and merge the grade-4 PR, verify deploy and automatic sidecars, and confirm no order or capital change
- [ ] T020 Refresh and merge `HANDOFF.md`, then re-check current money-path truth

## Dependencies

- T001-T002 block all implementation.
- T003-T006 block T007-T015.
- T007-T010 block factory eligibility; T011-T015 block fundability eligibility.
- T007-T015 block T016-T017; T016-T017 block T018; T018 blocks T019; T019 blocks T020.

## Implementation Strategy

1. Write failing contracts before implementation.
2. Recompute rather than trust producer summaries.
3. Reuse the exact planner for fundability.
4. Add checks only to upward exposure paths.
5. Release with current production replay and unchanged order count.
