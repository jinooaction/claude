# Tasks: Promote Readiness Observe Gateway

**Input**: Design documents from `/specs/121-promote-readiness-observe-gateway/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This feature touches the SSH safety boundary, so focused tests are required.

**Organization**: Tasks are grouped by independently testable user story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the failing evidence and the exact files that carry the boundary.

- [x] T001 Verify `.specify/feature.json` points to `specs/121-promote-readiness-observe-gateway`.
- [x] T002 [P] Review `origin/automation/promote-readiness-last-run:LAST_RUN.md` and confirm `ssh_exit=126` refused command evidence.
- [x] T003 [P] Review `.github/workflows/promote-readiness.yml`, `deploy/repair-ssh-boundary.sh`, and `deploy/observe-on-instance.sh`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Lock the safety contract before implementation.

- [x] T004 Write the SDD spec, plan, research, data model, contract, quickstart, and checklist under `specs/121-promote-readiness-observe-gateway/`.
- [x] T005 Add or update tests proving `promote-readiness.yml` uses only `observe promote-readiness`.
- [x] T006 Add or update tests proving the forced-command gateway allows exactly `observe promote-readiness`.
- [x] T007 Add or update tests proving the observation helper exposes promotion readiness without unsafe live-money behavior.
- [x] T007a Add or update tests proving deploy refreshes root-owned gateway/helper files from `origin/main` before the deploy state machine runs.

**Checkpoint**: Tests describe the boundary before implementation.

---

## Phase 3: User Story 1 - Publish Promotion Readiness Through the Fixed Observe Gateway (Priority: P1)

**Goal**: The workflow publishes promotion readiness through a fixed observe command instead of a refused raw command.

**Independent Test**: `tests/unit/test_observation_gateway_workflows.py` proves the workflow command contract.

### Implementation for User Story 1

- [x] T008 [US1] Replace the raw SSH command in `.github/workflows/promote-readiness.yml` with `observe promote-readiness`.
- [x] T009 [US1] Preserve READY false/true sidecar publication semantics in `.github/workflows/promote-readiness.yml`.

**Checkpoint**: US1 can be tested independently with the workflow test.

---

## Phase 4: User Story 2 - Preserve the Server Safety Boundary (Priority: P1)

**Goal**: The server accepts one new fixed read-only observation command and continues refusing arbitrary commands.

**Independent Test**: `tests/unit/test_ssh_boundary_repair.py` proves the gateway/helper command contract and unsafe primitives remain absent.

### Implementation for User Story 2

- [x] T010 [US2] Add `observe promote-readiness` to the fixed allowlist in `deploy/repair-ssh-boundary.sh`.
- [x] T011 [US2] Add `promote-readiness` to the observation helper in `deploy/observe-on-instance.sh`.
- [x] T012 [US2] Ensure the helper uses fixed production paths and fixed capital, with no caller-provided arguments.

**Checkpoint**: US2 proves the repair keeps the SSH safety boundary narrow.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verify, document, and prepare merge.

- [x] T013 Update `CLAUDE.md` active plan pointer to `specs/121-promote-readiness-observe-gateway/plan.md`.
- [x] T014 Run focused tests and shell syntax checks from `quickstart.md`.
- [x] T015 Run full validation: `uv run pytest`, `uv run ruff check src tests`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, and `git diff --check`.
- [x] T016 Merge the first observe-gateway repair and verify the post-merge `promote-readiness` sidecar.
- [x] T017 Diagnose the remaining `ssh_exit=126` as installed root-owned gateway/helper drift rather than a workflow command drift.
- [x] T018 Update `deploy/auto-invest-deploy.service` to run a root pre-step that refreshes boundary helpers from `origin/main`.
- [x] T019 Add `deploy/refresh-ssh-boundary-helpers.sh` for helper-only boundary refresh.
- [x] T020 Update `deploy/repair-ssh-boundary.sh` so helper-only refresh installs gateway/helpers/sudoers from the selected repo ref without key rotation.
- [x] T021 Add tests for deploy pre-step ordering, helper-only refresh mode, and no live-money side effects.
- [x] T022 Run focused tests and shell syntax checks from the updated `quickstart.md`.
- [x] T023 Run full validation: `uv run pytest`, `uv run ruff check src tests`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, and `git diff --check`.
- [x] T024 Refresh `HANDOFF.md` and add a numbered HANDOFF note after merge-ready validation.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on setup and blocks user stories.
- **US1 (Phase 3)**: Depends on tests T005-T007.
- **US2 (Phase 4)**: Depends on tests T005-T007 and can be implemented alongside US1 if file conflicts are coordinated.
- **Polish (Phase 5)**: Depends on user story completion.

### Parallel Opportunities

- T002 and T003 can run in parallel.
- T005, T006, T007, and T007a touch different assertions but should be committed with the implementation.
- Focused tests and shell syntax checks can run in parallel.

## Implementation Strategy

### MVP First

1. Complete T005-T009.
2. Run the workflow-focused test.
3. Confirm the workflow no longer sends raw SSH commands.

### Incremental Delivery

1. Complete T010-T012 for the server boundary.
2. Run focused tests and shell syntax checks.
3. Complete T017-T021 for deploy-time helper refresh if post-merge sidecar still reports a refused fixed command.
4. Run full validation.
5. Open PR, pass quality gate, merge, then refresh HANDOFF and verify sidecars.
