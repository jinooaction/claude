# Tasks: Strategy Review Observation Health

**Input**: Design documents from `/specs/066-strategy-review-observation-health/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Required because this changes autonomous strategy-review classification.

**Organization**: Tasks are grouped by user story so the behavior can be verified independently.

## Phase 1: Setup

**Purpose**: Establish the spec and latest operational failure mode.

- [X] T001 Create SDD artifacts in `specs/066-strategy-review-observation-health/`.
- [X] T002 Confirm the latest reassignment sidecar reported `DEGRADED` because `globalfixed` lagged while all tracks were still below minimum observations.

---

## Phase 2: User Story 1 - 정상 관측 누적을 장애로 오판하지 않음 (Priority: P1)

**Goal**: All-known, all-premature tournament input remains `OK` even when observation counts differ.

**Independent Test**: Current sidecar-like seven-track input returns `observation_health=OK` and retains `lagging_keys`.

- [X] T003 [US1] Update `_observation_quality` in `src/auto_invest/analytics/forward_tournament.py`.
- [X] T004 [US1] Replace the all-premature lag regression in `tests/unit/test_forward_tournament.py`.
- [X] T005 [US1] Add a seven-track probe regression in `tests/integration/test_forward_tournament_probe.py`.

---

## Phase 3: User Story 2 - 비교 가능 구간에서 미달 후보는 계속 차단 (Priority: P1)

**Goal**: Mixed comparable and below-minimum known tracks still degrade observation quality.

**Independent Test**: Comparable incumbent plus below-minimum candidate returns `DEGRADED`.

- [X] T006 [US2] Add a mixed comparable/premature unit regression in `tests/unit/test_forward_tournament.py`.

---

## Phase 4: User Story 3 - 충분히 관측된 후보의 관측 수 차이는 설명만 함 (Priority: P2)

**Goal**: All-comparable tracks keep `OK` even when observation counts differ.

**Independent Test**: All known tracks at or above minimum observations return `OK` with `lagging_keys`.

- [X] T007 [US3] Add an all-comparable lag regression in `tests/unit/test_forward_tournament.py`.

---

## Phase 5: Validation and Handoff

**Purpose**: Prove the repair and leave the next session with current truth.

- [X] T008 Run focused forward tournament and reassignment tests.
- [X] T009 Run `uv run pytest` and `uv run ruff check src tests`.
- [ ] T010 Open, verify, and merge the pull request if gates pass.
- [ ] T011 Refresh `HANDOFF.md` after merge and validate handoff facts.
