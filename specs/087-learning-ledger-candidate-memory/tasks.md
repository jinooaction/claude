# Tasks: Learning Ledger Candidate Memory

**Input**: Design documents from `specs/087-learning-ledger-candidate-memory/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and changes autonomous candidate selection.

## Phase 1: Setup

- [x] T001 Create spec 087 design artifacts in `specs/087-learning-ledger-candidate-memory/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 087.

## Phase 2: Ledger decision application

- [x] T003 [P] [US1] Add focused tests for evidence-dependent ledger suppression in `tests/unit/test_evolution_loop.py`.
- [x] T004 [P] [US2] Add focused tests for operator-review ledger suppression in `tests/unit/test_evolution_loop.py`.
- [x] T005 [US1] Extend `apply_learning_ledger` in `src/auto_invest/analytics/evolution_loop.py` to apply held and review decisions.
- [x] T006 [US1] Preserve ledger reason, evidence package, and recheck condition in suppressed candidate next-action text in `src/auto_invest/analytics/evolution_loop.py`.

## Phase 3: Probe and workflow reproducibility

- [x] T007 [US1] Add or update integration assertions for `scripts/evolution_loop_probe.py` ledger replay in `tests/integration/test_evolution_loop_probe.py`.
- [x] T008 [US1] Run local ledger replay from `quickstart.md` and confirm `candidate-fa66202bf496` is excluded from `safe_high_leverage_work`.

## Phase 4: Completion marker and documentation

- [x] T009 [US3] Ensure `contracts/learning-ledger-candidate-memory.md` contains `completed_candidate_id: candidate-fa66202bf496`.

## Phase 5: Verification and release marker

- [x] T010 Run focused pytest for evolution loop and probe tests.
- [x] T011 Run `uv run pytest`.
- [x] T012 Run `uv run ruff check src tests`.
- [x] T013 Run `git diff --check`.
- [x] T014 Run `uv run python scripts/check_handoff_facts.py`.
- [x] T015 Run `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T016 Run PR quality gate.
- [x] T017 [US3] Run `uv run python scripts/released_work_probe.py --repo-root . --run-id local-087 --commit "$(git rev-parse HEAD)" --json-out /tmp/released_work_087.json --summary-out /tmp/released_work_087.md` and confirm the candidate is released after all task checkboxes are complete.

## Operational Closure Outside Released-Work Scan

These are required by repository operating rules, but they are not Speckit implementation
checkboxes because `released-work` treats any unchecked checkbox in `tasks.md` as incomplete
work.

- Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- Check post-merge deploy/sidecar status and refresh HANDOFF if operating truth changed.

## Dependencies & Execution Order

- T001-T002 before implementation.
- T003-T004 before T005-T006.
- T005-T006 before T007-T008.
- T009 only after implementation tasks are complete.
- T010-T017 after all behavior and documentation tasks are done.
- Operational closure runs after T017 confirms the completed candidate can be consumed.

## Parallel Opportunities

- T003 and T004 touch the same test file but can be drafted independently before final ordering.
- Documentation and PR body drafting can happen after focused behavior is stable.
- Full tests and lint can run in parallel once code is complete.

## Implementation Strategy

1. First prove the missing behavior with tests.
2. Extend the existing ledger application function; do not create a new sidecar.
3. Reproduce with the probe path.
4. Mark this candidate complete via released-work only after implementation tasks are checked off.
