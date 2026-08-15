# Tasks: Profit Evidence Engine

**Input**: Design documents from `specs/138-profit-evidence-engine/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

## Phase 1: Setup

- [x] T001 Create complete SDD artifacts in `specs/138-profit-evidence-engine/`
- [x] T002 Inspect current money-path, forward leaderboard, candidate factory/result, and long-history evidence

## Phase 2: Foundational Tests

- [x] T003 [P] Add temporal split, cost drag, deterministic selection, holdout gate, and neighbor robustness tests in `tests/unit/test_profit_evidence_engine.py`
- [x] T004 [P] Add CLI/public-data/leaderboard integration tests in `tests/integration/test_profit_evidence_engine_probe.py`
- [x] T005 [P] Add mixed-horizon evidence-axis tests in `tests/unit/test_candidate_result_executor.py`
- [x] T006 [P] Add `globalfixed` history manifest coverage in `tests/unit/test_candidate_history_support.py`

## Phase 3: User Story 1 - 실제 수익 후보를 시간 분리로 찾기

- [x] T007 [US1] Implement candidate and report models in `src/auto_invest/analytics/profit_evidence_engine.py`
- [x] T008 [US1] Implement the 12-candidate pre-registered factor set and 50bp annual cost drag in `src/auto_invest/analytics/profit_evidence_engine.py`
- [x] T009 [US1] Implement fixed pre-2007 development selection and post-2007 holdout evaluation in `src/auto_invest/analytics/profit_evidence_engine.py`
- [x] T010 [US1] Implement CAGR, Sharpe, drawdown, and neighboring-window gates in `src/auto_invest/analytics/profit_evidence_engine.py`

## Phase 4: User Story 2 - 혼합 증거를 보존하기

- [x] T011 [US2] Classify strategy validation commands by historical and recent evidence roles in `src/auto_invest/analytics/candidate_result_executor.py`
- [x] T012 [US2] Preserve per-axis status and route mixed results to pending in `src/auto_invest/analytics/candidate_result_executor.py`
- [x] T013 [US2] Include per-command metrics and mixed-evidence diagnostics in `src/auto_invest/analytics/candidate_result_executor.py`

## Phase 5: User Story 3 - 자동 관찰 경로 연결

- [x] T014 [US3] Implement public-data and forward-leaderboard probe in `scripts/profit_evidence_engine_probe.py`
- [x] T015 [US3] Add `global-trend-fixed` history mapping in `src/auto_invest/analytics/candidate_history_support.py`
- [x] T016 [US3] Allow the `global-trend-fixed` history export in `.github/workflows/candidate-result-executor.yml`
- [x] T017 [US3] Add read-only scheduled sidecar workflow in `.github/workflows/profit-evidence-engine.yml`

## Phase 6: Validation and Release

- [x] T018 Run focused tests and real public-data replay from `specs/138-profit-evidence-engine/quickstart.md`
- [x] T019 Run `uv run pytest`, `uv run ruff check src tests`, and `git diff --check`
- [x] T020 Run `scripts/check_handoff_facts.py`, strict agent harness, and PR quality gate
- [x] T021 Commit, push, open the quality-gated PR, merge it, and verify deploy/read-only sidecar workflows
- [x] T022 Refresh `HANDOFF.md` and add the milestone handoff through the `handoff` skill

## Dependencies

- T001-T002 precede all implementation.
- T003-T006 are written before T007-T017.
- T007-T010 complete the pure engine before T014 workflow integration.
- T011-T013 are independent of T007-T010 after tests exist.
- T015 precedes T016.
- T018 precedes full validation and release.

## Parallel Opportunities

- T003-T006 touch separate test files.
- T007-T010 and T011-T13 affect separate modules.
- T014, T015, and T017 affect separate files after core contracts stabilize.

## Independent Test Criteria

- **US1**: Fixed fixture data yields exactly 12 trials, zero split overlap, deterministic selection, and explicit holdout gates.
- **US2**: Historical pass plus recent fail yields `pending` while all three evidence axes retain their values.
- **US3**: The probe fuses the `globalfixed` forward row and the workflow contains no broker/order/live mutation surface.

## Implementation Strategy

Build the pure held-out engine first. Then repair mixed evidence aggregation. Finally wire the already-existing `globalfixed` paper candidate into repeatable history collection and a read-only sidecar. Promotion remains outside this feature and requires the unchanged forward/canary gates.
