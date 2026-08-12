# Tasks: Validation Failure Package-Kind Expansion Contract

**Input**: Design documents from `specs/129-validation-failure-package-kind-expansion/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/129-validation-failure-package-kind-expansion/`
- [x] T002 Update active feature pointer in `.specify/feature.json`
- [x] T003 Update active plan pointer in `CLAUDE.md`

---

## Phase 2: Foundational

- [x] T004 [P] Add focused package-kind tests in `tests/unit/test_validation_failure_package_kind_expansion.py`
- [x] T005 [P] Add autonomous-work advancement test in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - 전략 실패와 포트폴리오 실패를 분리한다 (Priority: P1)

**Goal**: Produce deterministic package-kind buckets for current validation failures.

**Independent Test**: Focused package-kind tests produce two buckets from two failed packages.

- [x] T006 [US1] Implement package-kind report models in `src/auto_invest/analytics/validation_failure_package_kind_expansion.py`
- [x] T007 [US1] Join package plans, diagnostics, commands, and result evidence in `src/auto_invest/analytics/validation_failure_package_kind_expansion.py`

---

## Phase 4: User Story 2 - 다음 no-live 실험 축을 넓게 재정렬한다 (Priority: P2)

**Goal**: Record strategy, portfolio, holding-period, and evidence-output axes without proposing live action.

**Independent Test**: Focused tests prove strategy and portfolio packages get different axes.

- [x] T008 [US2] Add metric and limited text hint extraction in `src/auto_invest/analytics/validation_failure_package_kind_expansion.py`
- [x] T009 [US2] Add Markdown and JSON artifact writer in `src/auto_invest/analytics/validation_failure_package_kind_expansion.py`

---

## Phase 5: User Story 3 - 다음 child 후보로 전진할 수 있게 완료 표식을 남긴다 (Priority: P3)

**Goal**: Mark package-kind candidate complete and provide an executable probe.

**Independent Test**: Probe against current sidecars returns `CONTRACT_READY`.

- [x] T010 [US3] Add probe script in `scripts/validation_failure_package_kind_expansion_probe.py`
- [x] T011 [US3] Add completed candidate marker in `specs/129-validation-failure-package-kind-expansion/contracts/package-kind-expansion-contract.md`

---

## Phase 6: Validation, PR, and Handoff

- [x] T012 Run focused pytest for package-kind tests
- [x] T013 Run focused pytest for autonomous-work advancement tests
- [x] T014 Run current sidecar replay from `quickstart.md`
- [x] T015 Run `uv run pytest`
- [x] T016 Run `uv run ruff check src tests`
- [x] T017 Run `git diff --check`
- [x] T018 Run `uv run python scripts/check_handoff_facts.py`
- [x] T019 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T020 Prepare PR body, PR quality gate evidence, release replay evidence, and HANDOFF refresh plan

## Dependencies & Execution Order

1. Phase 1 records the operating change.
2. Phase 2 locks tests and autonomous-work progression.
3. User Story 1 creates the report.
4. User Story 2 records experiment axes and sidecar context.
5. User Story 3 makes the contract runnable and releasable.
6. Phase 6 validates, opens PR, merges, and refreshes handoff.

## Implementation Strategy

Implement the read-only contract first. Do not execute package commands. Use released-work to close this candidate and let autonomous-work choose the next child candidate.
