# Tasks: Evolution Source Diversification

**Input**: Design documents from `specs/089-evolution-source-diversification/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and changes autonomous candidate generation.

## Phase 1: Setup

- [x] T001 Create spec 089 design artifacts in `specs/089-evolution-source-diversification/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 089.

## Phase 2: Closed static candidate signal

- [x] T003 [P] [US1] Add unit test for closed static candidate set producing an evidence-derived source diversification candidate in `tests/unit/test_evolution_loop.py`.
- [x] T004 [P] [US1] Add unit test that an existing safe static candidate remains ahead of synthesized candidates in `tests/unit/test_evolution_loop.py`.
- [x] T005 [P] [US2] Add unit test that ledger decisions, promotion failures, and sidecar bottlenecks appear in the synthesized candidate evidence and Korean reason text in `tests/unit/test_evolution_loop.py`.

## Phase 3: Candidate synthesis implementation

- [x] T006 [US1] Add closed static candidate detection helpers in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T007 [US1] Add deterministic evidence-derived source diversification candidate synthesis in `src/auto_invest/analytics/evolution_loop.py`.
- [x] T008 [US2] Include ledger decision counts, promotion failure counts, stale/missing sidecar keys, released-work saturation, and capital-path observability signals in the candidate reason/action text in `src/auto_invest/analytics/evolution_loop.py`.

## Phase 4: Probe and contract coverage

- [x] T009 [US1] Add or update probe assertions for synthesized candidate output in `tests/integration/test_evolution_loop_probe.py`.
- [x] T010 [US1] Run local quickstart probe reproduction and confirm the new candidate is present.
- [x] T011 [US3] Ensure `contracts/evolution-source-diversification.md` contains `completed_candidate_id: candidate-evolution-source-diversification`.

## Phase 5: Verification and release marker

- [x] T012 Run focused pytest for evolution loop unit and probe tests.
- [x] T013 Run `uv run pytest`.
- [x] T014 Run `uv run ruff check src tests`.
- [x] T015 Run `git diff --check`.
- [x] T016 Run `uv run python scripts/check_handoff_facts.py`.
- [x] T017 Run `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T018 Run PR quality gate.
- [x] T019 [US3] Run `uv run python scripts/released_work_probe.py --repo-root . --run-id local-089 --commit "$(git rev-parse HEAD)" --json-out /tmp/released_work_089.json --summary-out /tmp/released_work_089.md` and confirm the candidate is released after all task checkboxes are complete.
- [x] T020 [US1] Run autonomous evolution quickstart against current sidecars and confirm the synthesized candidate appears in `candidate_backlog.json`.

## Operational Closure Outside Released-Work Scan

These are required by repository operating rules, but they are not Speckit implementation checkboxes because `released-work` treats any unchecked checkbox in `tasks.md` as incomplete work.

- Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- Check post-merge deploy/sidecar status and refresh HANDOFF if operating truth changed.

## Dependencies & Execution Order

- T001-T002 before implementation.
- T003-T005 before T006-T008.
- T006 before T007-T008.
- T009-T011 after core behavior is stable.
- T012-T020 after all behavior and documentation tasks are done.
- Operational closure runs after T020 confirms the completed candidate can be consumed.

## Parallel Opportunities

- T003, T004, and T005 are logically independent tests but touch the same test file, so final edits should be sequenced.
- T009 can be done after T006-T008 without waiting for release marker validation.
- Full tests, lint, and diff checks can run in parallel once focused tests pass.

## Implementation Strategy

1. Prove closed static candidate behavior with tests.
2. Add the source diversification synthesis rule in the existing evolution loop core.
3. Verify probe behavior and released-work consumption.
4. Mark this candidate complete via released-work only after implementation tasks are checked off.
