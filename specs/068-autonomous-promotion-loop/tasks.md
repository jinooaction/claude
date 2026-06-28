# Tasks: Autonomous Promotion Loop

**Input**: Design documents from `/specs/068-autonomous-promotion-loop/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md, contracts/

**Tests**: Required because this creates a new autonomous operating workflow touching money-path interpretation.

## Phase 1: Setup

- [x] T001 Create promotion-loop fixtures in `tests/fixtures/promotion_loop/fresh/`.
- [x] T002 Create pure promotion models and constants in `src/auto_invest/analytics/promotion_loop.py`.
- [x] T003 Create probe skeleton with JSON/text/artifact outputs in `scripts/promotion_loop_probe.py`.

## Phase 2: Foundational Safety

- [x] T004 [P] Implement evidence-layer classification in `src/auto_invest/analytics/promotion_loop.py`.
- [x] T005 [P] Implement backtest-vs-canary explanation and secret masking in `src/auto_invest/analytics/promotion_loop.py`.
- [x] T006 [P] Add safety and explanation tests in `tests/unit/test_promotion_loop.py`.

## Phase 3: User Story 1 - Growth Candidate Promotion Classification

- [x] T007 [US1] Parse autonomous-evolution candidate backlog in `src/auto_invest/analytics/promotion_loop.py`.
- [x] T008 [US1] Implement deterministic stage classification and queue ordering in `src/auto_invest/analytics/promotion_loop.py`.
- [x] T009 [P] [US1] Add deterministic classification tests in `tests/unit/test_promotion_loop.py`.

## Phase 4: User Story 2 - Backtest and Small-Live Separation

- [x] T010 [US2] Encode evidence-layer rules so backtest-only candidates cannot become live/canary-ready in `src/auto_invest/analytics/promotion_loop.py`.
- [x] T011 [P] [US2] Add tests proving backtest pass does not complete broker execution validation in `tests/unit/test_promotion_loop.py`.

## Phase 5: User Story 3 - Sidecar and Liveness

- [x] T012 [US3] Add Korean markdown, summary JSON, and queue JSON rendering in `src/auto_invest/analytics/promotion_loop.py`.
- [x] T013 [US3] Add `promotion-scan` CLI command in `src/auto_invest/cli.py`.
- [x] T014 [US3] Add `.github/workflows/autonomous-promotion-loop.yml`.
- [x] T015 [US3] Add `autonomous-promotion` to `src/auto_invest/analytics/pipeline_liveness.py`.
- [x] T016 [P] [US3] Add probe and workflow integration tests in `tests/integration/test_promotion_loop_probe.py`.
- [x] T017 [P] [US3] Add liveness registry regression in `tests/unit/test_pipeline_liveness.py`.

## Phase 6: Validation and Handoff

- [x] T018 Run focused tests for promotion loop and liveness.
- [x] T019 Run full `uv run pytest` and `uv run ruff check src tests`.
- [x] T020 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T021 Open PR with grade 2 risk and complete quality gate body.
- [ ] T022 Merge when green and refresh HANDOFF.

## Dependencies & Execution Order

- Setup before all implementation.
- Foundational safety before classification.
- Classification before reporting/workflow.
- Workflow before liveness validation.

## Implementation Strategy

Deliver the read-only sidecar loop first. Defer automatic forward-track registration to a follow-up spec after the promotion queue is proven.
