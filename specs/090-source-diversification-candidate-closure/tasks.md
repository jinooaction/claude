# Tasks: Source Diversification Candidate Closure

**Input**: Design documents from `specs/090-source-diversification-candidate-closure/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because this is an operating automation regression.

**Organization**: Tasks are grouped by user story so each behavior can be verified independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish SDD artifacts and active feature pointers.

- [x] T001 Create spec 090 SDD artifacts in `specs/090-source-diversification-candidate-closure/`.
- [x] T002 Update `.specify/feature.json` and `CLAUDE.md` to point at spec 090.

---

## Phase 2: User Story 1 - 완료된 산출 후보를 장부로 닫기 (Priority: P1)

**Goal**: released-work records `candidate-source-diversification-sidecar-bottleneck` only after this spec is complete.

**Independent Test**: `released_work_probe.py --repo-root .` includes the candidate after tasks are complete.

- [x] T003 [US1] Add completion contract marker in `specs/090-source-diversification-candidate-closure/contracts/source-diversification-candidate-closure.md`.
- [x] T004 [US1] Run released-work reproduction from `specs/090-source-diversification-candidate-closure/quickstart.md`.

---

## Phase 3: User Story 2 - 다음 실제 후보로 전진시키기 (Priority: P2)

**Goal**: autonomous work execution skips the completed source-diversification output and selects the next macro candidate.

**Independent Test**: Focused unit test and latest sidecar replay select `candidate-autonomous-growth-objective-calibration`.

- [x] T005 [P] [US2] Add focused regression test in `tests/unit/test_autonomous_work_execution.py`.
- [x] T006 [US2] Run latest sidecar replay from `specs/090-source-diversification-candidate-closure/quickstart.md`.

---

## Phase 4: User Story 3 - 안전 경계와 인계 재현성 유지 (Priority: P3)

**Goal**: prove the closure is grade 2 and does not touch money or safety boundaries.

**Independent Test**: Full validation and PR body/handoff record the boundary and next candidate.

- [x] T007 [US3] Run focused pytest for autonomous work execution.
- [x] T008 [US3] Run full pytest, ruff, diff check, HANDOFF fact check, and strict harness.
- [x] T009 [US3] Prepare PR quality-gate body with risk grade, problem definition, safety boundary, and validation.

## Operational Closure Outside Released-Work Scan

These are required by repository operating rules, but they are not Speckit implementation checkboxes because `released-work` treats any unchecked checkbox in `tasks.md` as incomplete work.

- Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- Check post-merge deploy/sidecar status and refresh HANDOFF if operating truth changed.

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 must complete before released-work reproduction.
- User Story 1 must complete before User Story 2 can prove candidate advancement.
- User Story 3 depends on the focused behavior and reproduction checks.

### Parallel Opportunities

- T005 can be written while SDD review is happening because it touches only the unit test file.

## Implementation Strategy

1. Land the explicit completion contract and regression.
2. Mark tasks complete once the behavior is locally proven.
3. Run focused checks, then full closure checks.
4. Create and merge PR, then refresh HANDOFF in a follow-up PR.
