# Tasks: Forward Paper DB Writability

**Input**: Design documents from `/specs/122-forward-paper-db-writability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature touches a root-installed observe helper, so focused tests are required.

**Organization**: Tasks are grouped by independently testable user story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the live blocker and lock the active feature pointer.

- [x] T001 Verify latest money-path and capital-path-readiness report `PREVIEW_ONLY` / `NO_EDGE_YET`.
- [x] T002 [P] Verify latest forward paper sidecar has `prep ssh_exit=1` for all tracks.
- [x] T003 [P] Extract the concrete failure: `OperationalError: attempt to write a readonly database`.
- [x] T004 Create SDD artifacts under `specs/122-forward-paper-db-writability/`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add safety-boundary tests before relying on the helper repair.

- [x] T005 Add tests proving paper storage repair is limited to forward paper DB/WAL/SHM and track halt files in `tests/unit/test_forward_workflow_halt_isolation.py`.
- [x] T006 Add tests proving the observe helper repair excludes `data/auto_invest.db` and `data/halt.flag` in `tests/unit/test_ssh_boundary_repair.py`.

---

## Phase 3: User Story 1 - Keep Forward Paper Observations Accumulating (Priority: P1)

**Goal**: `observe paper-track-run` restores writability for the selected paper DB before paper prep.

**Independent Test**: Focused helper tests and `bash -n deploy/observe-on-instance.sh`.

- [x] T007 [US1] Add `ensure_paper_track_storage` in `deploy/observe-on-instance.sh`.
- [x] T008 [US1] Call `ensure_paper_track_storage` after track validation and repo selection but before `backfill-bars`.

---

## Phase 4: User Story 2 - Preserve Live-Money Safety Boundaries (Priority: P1)

**Goal**: The repair does not widen live-money authority.

**Independent Test**: `tests/unit/test_ssh_boundary_repair.py` continues to prove no live order, live arming, service control, eval, or live capital mutation appears in the observe helper.

- [x] T009 [US2] Fail closed on unsafe storage paths before ownership repair.
- [x] T010 [US2] Keep the workflow command shape unchanged: `observe paper-track-run <track> <capital>`.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Validate, merge, deploy, and verify sidecar truth.

- [x] T011 Run focused tests and shell syntax checks from `quickstart.md`.
- [x] T012 Run full validation: `uv run pytest`, `uv run ruff check src tests`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, and `git diff --check`.
- [x] T013 Update PR body with risk grade 3, problem definition, safety boundary, validation, and handoff facts.
- [ ] T014 Merge after required checks pass and PR is mergeable.
- [ ] T015 Verify deploy helper refresh installs the updated observe helper on the server.
- [ ] T016 Rerun `rebalance-paper-forward.yml` and confirm the readonly database failure is gone.
- [ ] T017 Refresh `money-path`, `capital-path-readiness`, and `autonomous-work-execution` sidecars after forward evidence refresh.
- [ ] T018 Refresh `HANDOFF.md` if the operating truth changes.

## Dependencies & Execution Order

- Setup tasks can complete immediately.
- T005 and T006 must exist before relying on T007-T010.
- T011-T018 must run in order because post-merge sidecars depend on deployed code.

## Implementation Strategy

1. Restore paper DB writability narrowly.
2. Prove the live-money surface is untouched.
3. Merge only after full validation.
4. Verify the actual forward paper sidecar, because local tests cannot prove server file permissions.
