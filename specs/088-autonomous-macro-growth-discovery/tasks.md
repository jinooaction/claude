# Tasks: Autonomous Macro Growth Discovery

**Input**: Design documents from `specs/088-autonomous-macro-growth-discovery/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and changes autonomous candidate selection.

## Phase 1: Setup

- [x] T001 Create spec 088 design artifacts in `specs/088-autonomous-macro-growth-discovery/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 088.

## Phase 2: Closed queue behavior

- [x] T003 [P] [US1] Add focused test for closed regular queue selecting `candidate-macro-growth-discovery` in `tests/unit/test_autonomous_work_execution.py`.
- [x] T004 [P] [US3] Add focused test for released bootstrap advancing to `candidate-evolution-source-diversification` in `tests/unit/test_autonomous_work_execution.py`.
- [x] T005 [P] [US2] Add focused test that operator approval candidates are not masked in `tests/unit/test_autonomous_work_execution.py`.
- [x] T006 [US1] Add deterministic macro-growth candidate synthesis to `src/auto_invest/analytics/autonomous_work_execution.py`.

## Phase 3: Probe and contract coverage

- [x] T007 [US1] Add or update probe assertions for macro-growth selection in `tests/integration/test_autonomous_work_execution_probe.py`.
- [x] T008 [US1] Run local probe reproduction from `quickstart.md` and confirm `candidate-macro-growth-discovery` is selected.
- [x] T009 [US3] Ensure `contracts/autonomous-macro-growth-discovery.md` contains `completed_candidate_id: candidate-macro-growth-discovery`.

## Phase 4: Verification and release marker

- [x] T010 Run focused pytest for autonomous work execution unit and probe tests.
- [x] T011 Run `uv run pytest`.
- [x] T012 Run `uv run ruff check src tests`.
- [x] T013 Run `git diff --check`.
- [x] T014 Run `uv run python scripts/check_handoff_facts.py`.
- [x] T015 Run `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T016 Run PR quality gate.
- [x] T017 [US3] Run `uv run python scripts/released_work_probe.py --repo-root . --run-id local-088 --commit "$(git rev-parse HEAD)" --json-out /tmp/released_work_088.json --summary-out /tmp/released_work_088.md` and confirm the candidate is released after all task checkboxes are complete.
- [x] T018 [US3] Run autonomous work execution with current repo released-work override and confirm the next macro candidate is `candidate-evolution-source-diversification`.

## Operational Closure Outside Released-Work Scan

These are required by repository operating rules, but they are not Speckit implementation checkboxes because `released-work` treats any unchecked checkbox in `tasks.md` as incomplete work.

- Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- Check post-merge deploy/sidecar status and refresh HANDOFF if operating truth changed.

## Dependencies & Execution Order

- T001-T002 before implementation.
- T003-T005 before T006.
- T006 before T007-T008.
- T009 only after implementation tasks are complete.
- T010-T018 after all behavior and documentation tasks are done.
- Operational closure runs after T018 confirms the completed candidate can be consumed.

## Parallel Opportunities

- T003, T004, and T005 are logically independent tests but touch the same test file, so final edits should be sequenced.
- Contract and quickstart validation can proceed after core behavior is stable.
- Full tests and lint can run in parallel once code is complete.

## Implementation Strategy

1. Prove closed-queue behavior with tests.
2. Add the macro-growth synthesis rule in the existing work execution core.
3. Verify probe behavior and released-work consumption.
4. Mark this candidate complete via released-work only after implementation tasks are checked off.
