# Tasks: 공개 데이터 교차 검증 확장

**Input**: Design documents from `/specs/085-public-data-cross-validation/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because this is an operating data-channel change and must preserve safety/integration invariants.

**Organization**: Tasks are grouped by independently testable user story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Point the worktree at this feature and preserve SDD context.

- [x] T001 Update `.specify/feature.json` to `specs/085-public-data-cross-validation`
- [x] T002 Update `CLAUDE.md` Speckit pointer to `specs/085-public-data-cross-validation/plan.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add source-specific request configuration before user stories use it.

- [x] T003 Add configurable user-agent mode support for public-data fetches in `src/auto_invest/market_data/public_data.py`
- [x] T004 Add focused regression for FRED `httpx-default` user-agent mode in `tests/unit/test_public_data.py`

---

## Phase 3: User Story 1 - FRED 금리 원천을 연구 채널에 추가 (Priority: P1)

**Goal**: Publish FRED DGS2 and DGS10 as validated research-only series.

**Independent Test**: `uv run pytest tests/unit/test_public_data.py -k official_sources`

- [x] T005 [US1] Add FRED DGS2/DGS10 collection config to `deploy/public-data.toml`
- [x] T006 [US1] Extend official-source mock config and handler for FRED DGS2/DGS10 in `tests/unit/test_public_data.py`
- [x] T007 [US1] Update official-source happy path expectation from 9 to 11 published items in `tests/unit/test_public_data.py`
- [x] T008 [US1] Run focused public-data tests for FRED publication

---

## Phase 4: User Story 2 - 금리 두-기관 대조를 FRED 경로까지 확장 (Priority: P2)

**Goal**: Add Treasury-vs-FRED level cross-checks and keep failures visible.

**Independent Test**: `uv run pytest tests/unit/test_public_data.py tests/unit/test_collect_public_data_workflow.py`

- [x] T009 [US2] Add Treasury-vs-FRED cross-check entries to `deploy/public-data.toml`
- [x] T010 [US2] Update cross-check assertions for five official checks in `tests/unit/test_public_data.py`
- [x] T011 [US2] Update config integrity invariant to allow FRED collection and require collected cross-check keys in `tests/unit/test_collect_public_data_workflow.py`
- [x] T012 [US2] Run focused public-data and workflow invariant tests

---

## Phase 5: User Story 3 - 라이브 매매 경로 격리 유지 (Priority: P3)

**Goal**: Keep expanded public-data scope out of live trading paths and operator-facing docs accurate.

**Independent Test**: workflow invariant tests plus SDD quickstart.

- [x] T013 [US3] Update `deploy/public-data.toml` and `.github/workflows/collect-public-data.yml` comments to state FRED graph CSV is research-only and FRED API-key endpoint remains probe-only
- [x] T014 [US3] Update `src/auto_invest/market_data/public_data.py` module comments for the new FRED posture
- [x] T015 [US3] Run `uv run pytest tests/unit/test_collect_public_data_workflow.py`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate, record completion, and prepare merge.

- [x] T016 Run `uv run pytest tests/unit/test_public_data.py tests/unit/test_collect_public_data_workflow.py`
- [x] T017 Run `uv run pytest`
- [x] T018 Run `uv run ruff check src tests`
- [x] T019 Run `uv run python scripts/check_handoff_facts.py`
- [x] T020 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T021 Add HANDOFF update for spec 085 in `HANDOFF.md` and `HANDOFF-089-PUBLIC-DATA-CROSS-VALIDATION.md`
- [x] T022 Run PR quality gate body validation before opening PR

## Dependencies & Execution Order

### Phase Dependencies

- Setup -> Foundational -> US1 -> US2 -> US3 -> Polish
- US1 must precede US2 because FRED registry keys must exist before cross-checks can reference them.
- US3 can run after US1/US2 content is known.

### Parallel Opportunities

- T001 and T002 touch different files and can be reviewed independently.
- Test-only updates in T004, T006, T010, T011 are separate from implementation/config edits but should be committed as one coherent feature.

## Implementation Strategy

1. Add the smallest request-mode extension needed for FRED.
2. Add FRED series and tests proving publication.
3. Add cross-checks and tests proving PASS/SKIPPED/FAIL visibility.
4. Preserve workflow isolation and complete full gates.
