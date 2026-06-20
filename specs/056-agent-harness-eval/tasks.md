# Tasks: Agent Harness Evaluation

**Input**: Design documents from `specs/056-agent-harness-eval/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because the feature changes operating automation and PR gates.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create `.codex/harness/evaluation_tasks.toml` with representative harness tasks.
- [x] T002 Create `scripts/agent_harness_probe.py` command skeleton and output contract.
- [x] T003 Add unit test loader for `scripts/agent_harness_probe.py` in `tests/unit/test_agent_harness_probe.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 Implement task-suite parsing and validation in `scripts/agent_harness_probe.py`.
- [x] T005 Implement static control checks for Codex hooks, PR quality workflow, SDD pointer, and quality gate in `scripts/agent_harness_probe.py`.
- [x] T006 Add strict exit-code behavior and JSON/text output in `scripts/agent_harness_probe.py`.
- [x] T007 Add tests for passing and failing probe cases in `tests/unit/test_agent_harness_probe.py`.

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - 하네스 상태를 한 번에 판정한다 (Priority: P1) MVP

**Goal**: One local command reports current harness health.

**Independent Test**: `uv run python scripts/agent_harness_probe.py --json --strict` exits 0 and reports `OK`.

- [x] T008 [US1] Wire all required control checks into `scripts/agent_harness_probe.py`.
- [x] T009 [US1] Verify current repository passes strict probe.

---

## Phase 4: User Story 2 - 하네스 회귀 과제 묶음을 유지한다 (Priority: P2)

**Goal**: Representative scenarios cover risk grades and control categories.

**Independent Test**: Tests fail when a temporary task suite misses required coverage.

- [x] T010 [US2] Add coverage tests for risk grades and required control categories in `tests/unit/test_agent_harness_probe.py`.
- [x] T011 [US2] Document task-suite contract in `specs/056-agent-harness-eval/contracts/harness-probe.md`.

---

## Phase 5: User Story 3 - 등급 2 이상 변경은 하네스 검증 증거를 남긴다 (Priority: P3)

**Goal**: Operating-system PRs cannot omit harness verification evidence.

**Independent Test**: A grade 2 PR body without strict harness evidence fails.

- [x] T012 [US3] Add `## 하네스 검증` to `.github/pull_request_template.md`.
- [x] T013 [US3] Extend `scripts/check_pr_quality_gate.py` to require harness evidence for grade 2+.
- [x] T014 [US3] Add PR body checker tests in `tests/unit/test_check_pr_quality_gate.py`.
- [x] T015 [US3] Update `AGENTS.md` and `.codex/quality-gate.md` to name the harness probe for grade 2+ changes.

---

## Phase N: Polish & Cross-Cutting Concerns

- [x] T016 Run `uv run pytest tests/unit/test_agent_harness_probe.py tests/unit/test_check_pr_quality_gate.py`.
- [x] T017 Run `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T018 Run `python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`.
- [x] T019 Run `uv run pytest`.
- [x] T020 Run `uv run ruff check src tests`.
- [ ] T021 Update PR body and handoff records after merge if required.

---

## Dependencies & Execution Order

- Setup tasks T001-T003 first.
- Foundational tasks T004-T007 block user stories.
- User Story 1 must pass before using the probe as PR evidence.
- User Story 3 depends on the probe command existing.
- Full validation T019-T020 runs after all stories.

## Implementation Strategy

MVP first: build the probe and task-suite validation, prove strict mode passes, then wire PR body evidence.
