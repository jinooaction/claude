# Tasks: 오래된 증거와 성과 실패 분리

**Input**: Design documents from `/specs/084-stale-evidence-failure-separation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a grade 2 autonomous operating-loop evidence and workflow change.

## Phase 1: Setup

**Purpose**: Keep SDD and active feature pointers current.

- [x] T001 Create SDD artifacts in `specs/084-stale-evidence-failure-separation/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 084.

---

## Phase 2: Foundation

**Purpose**: Preserve current capital readiness behavior while adding separation.

- [x] T003 Read current capital readiness, autonomous work execution, liveness, released-work, workflow, and tests.
- [x] T004 Confirm current sidecar shape for `capital_path_readiness.json`, `released_work.json`, and `pipeline-liveness` LAST_RUN.

---

## Phase 3: User Story 1 - 오래된 증거를 후보 실패와 분리한다 (Priority: P1)

**Goal**: Build observability issues separately from actionable candidates.

**Independent Test**: Unit tests prove released work and liveness issues do not alter money-path state.

- [x] T005 [US1] Add unit coverage for released candidate suppression.
- [x] T006 [US1] Add unit coverage for pipeline liveness observability issues.
- [x] T007 [US1] Implement `ReadinessObservabilityIssue` and report field.
- [x] T008 [US1] Update candidate routing to consume `released-work`.
- [x] T009 [US1] Update Markdown output with `## 관측 이슈`.

---

## Phase 4: User Story 2 - probe와 workflow가 새 입력을 소비한다 (Priority: P1)

**Goal**: Daily sidecar publication consumes freshness and release evidence.

**Independent Test**: Probe integration tests prove manifest and output contract.

- [x] T010 [US2] Add `released-work` and `pipeline-liveness` to probe manifest.
- [x] T011 [US2] Update probe integration tests.
- [x] T012 [US2] Update workflow path filters if needed.
- [x] T013 [US2] Confirm workflow remains read-only.

---

## Phase 5: Validation and Handoff

**Purpose**: Prove behavior and prepare PR/merge/handoff.

- [x] T014 Run focused tests from `quickstart.md`.
- [x] T015 Run `uv run pytest` and `uv run ruff check src tests`.
- [x] T016 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T017 Create PR with risk grade, problem definition, safety boundary review, validation, and handoff notes.
- [x] T018 Merge when gates pass and refresh `HANDOFF.md` after merge.

## Dependencies & Execution Order

- Phase 1 and 2 precede implementation.
- US1 must land before US2 output assertions because the probe prints the core report.
- Validation runs after all stories complete.

## Implementation Strategy

1. Add tests for released and liveness separation.
2. Update the pure analytics module.
3. Wire probe manifest and workflow path filters.
4. Run focused and full validation before PR and merge.
