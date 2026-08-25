# Tasks: Research Canary Evidence Parity

## Phase 1: Specification and safety contract

- [x] T001 Record the Grade 4 defect and acceptance contract in `specs/161-research-canary-evidence-parity/spec.md`
- [x] T002 Record decisions, alternatives, and rollback in `specs/161-research-canary-evidence-parity/research.md`
- [x] T003 Define shared evidence entities and versioned contract in `specs/161-research-canary-evidence-parity/data-model.md` and `specs/161-research-canary-evidence-parity/contracts/factory-evidence.md`

## Phase 2: User Story 1 - Shared completeness validator

- [x] T004 [US1] Add legacy, v2 dynamic-count, missing-audit, failed-blocking-gate, and malformed-evidence tests in `tests/unit/test_factory_evidence.py`
- [x] T005 [US1] Implement the pure versioned completeness assessment in `src/auto_invest/portfolio/factory_evidence.py`
- [x] T006 [US1] Add the thin workflow probe and contract tests in `scripts/factory_evidence_gate.py` and `tests/integration/test_factory_evidence_gate.py`

## Phase 3: User Story 2 - Consumer parity

- [x] T007 [US2] Replace ladder CLI hardcoded counts with the shared assessment in `src/auto_invest/cli.py` and update `tests/unit/test_ladder_decide_cli.py`
- [x] T008 [US2] Replace first-entry hardcoded counts with the shared assessment in `src/auto_invest/portfolio/live_entry_revalidation.py` and update `tests/unit/test_live_entry_revalidation.py`
- [x] T009 [US2] Replace zero-capital assignment hardcoded counts and stale PR text in `.github/workflows/forward-edge-autoarm.yml`

## Phase 4: User Story 3 - Safety perimeter preservation

- [x] T010 [US3] Update capital-ladder documentation without changing rung percentages or higher gates in `src/auto_invest/portfolio/capital_ladder.py`
- [x] T011 [US3] Amend constitution X.4 and version history in `.specify/memory/constitution.md`
- [x] T012 [US3] Add regression tests proving a v2 16/16 winner reaches only rung 1 and current no-edge evidence stays at rung 0

## Phase 5: Verification and release

- [x] T013 Run focused tests, full pytest, ruff, YAML, diff check, strict harness, and handoff facts
- [x] T014 Validate the Grade 4 PR body, commit with the safety-perimeter marker, push, open PR, and merge
- [x] T015 Confirm deployment and rerun factory, autoarm, live-entry, money, capital, KIS, and reconciliation evidence
- [ ] T016 Record production results and refresh HANDOFF through a follow-up PR

## Dependencies

- T004-T006 define the shared contract before any money-path consumer changes.
- T007-T011 must land atomically because partial consumer parity is unsafe.
- T013-T016 depend on every functional and safety regression test passing.

## Independent Tests

- **US1**: dynamic 16/16 v2 evidence passes completeness only when every required audit and blocking gate passes.
- **US2**: assignment, ladder, and first-entry consumers return the same completeness result.
- **US3**: complete evidence opens at most rung 1; current production no-edge evidence remains rung 0.
