# Tasks: Agent Quality Redteam Harness

**Input**: Design documents from `specs/057-agent-quality-redteam/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because this feature changes operating automation and PR gates.

## Phase 1: Setup

- [x] T001 Create `.codex/harness/quality_tasks.toml` with first-response quality regression tasks.
- [x] T002 Create `.codex/harness/redteam_tasks.toml` with failure-inducing redteam tasks.
- [x] T003 Create `scripts/check_handoff_facts.py` command skeleton.

---

## Phase 2: Foundational

- [x] T004 Extend `scripts/agent_harness_probe.py` data model for quality, redteam, and handoff results.
- [x] T005 Add tests for quality and redteam suite validation in `tests/unit/test_agent_harness_probe.py`.
- [x] T006 Add tests for handoff fact validation in `tests/unit/test_check_handoff_facts.py`.

---

## Phase 3: User Story 1 - 첫 판단 품질을 평가한다 (Priority: P1)

**Goal**: The harness fails when first-response quality coverage is missing.

**Independent Test**: Temporary quality task suites missing self-deepening fail unit tests.

- [x] T007 [US1] Implement quality task parsing and coverage validation in `scripts/agent_harness_probe.py`.
- [x] T008 [US1] Include this conversation's shallow initial diagnosis as a quality task in `.codex/harness/quality_tasks.toml`.
- [x] T009 [US1] Add quality suite output to text and JSON harness reports in `scripts/agent_harness_probe.py`.

---

## Phase 4: User Story 2 - 레드팀 실패 유도 시나리오를 관리한다 (Priority: P2)

**Goal**: The harness fails when required redteam attack types are missing.

**Independent Test**: Temporary redteam task suites missing context injection fail unit tests.

- [x] T010 [US2] Implement redteam task parsing and attack coverage validation in `scripts/agent_harness_probe.py`.
- [x] T011 [US2] Add required redteam scenarios to `.codex/harness/redteam_tasks.toml`.
- [x] T012 [US2] Add redteam suite output to text and JSON harness reports in `scripts/agent_harness_probe.py`.

---

## Phase 5: User Story 3 - HANDOFF 사실 표를 자동 검증한다 (Priority: P3)

**Goal**: Stale handoff summary rows become machine-detectable.

**Independent Test**: A temporary handoff with a stale main hash fails the checker.

- [x] T013 [US3] Implement `scripts/check_handoff_facts.py` text and JSON output.
- [x] T014 [US3] Wire handoff fact validation into `scripts/agent_harness_probe.py`.
- [x] T015 [US3] Update `HANDOFF.md` summary rows to actual latest main and validation evidence.

---

## Phase 6: Operating Surface Integration

- [x] T016 Update `.github/pull_request_template.md` and `scripts/check_pr_quality_gate.py` to require quality/redteam and handoff evidence for grade 2+ PRs.
- [x] T017 Update `AGENTS.md` and `.codex/quality-gate.md` to name the expanded strict harness and handoff fact check.
- [x] T018 Align `.agents/skills/sync/SKILL.md`, `.claude/skills/sync/SKILL.md`, `CLAUDE.md`, and `HANDOFF.md` with actual repository and `Codex/*` branch naming.
- [x] T019 Update `.gitignore` to exclude local Codex config and root generated bundle artifacts.
- [x] T020 Reduce duplicate lease noise in `scripts/local_concurrency_guard.py` while preserving protections.

---

## Phase N: Polish & Validation

- [x] T021 Run `uv run pytest tests/unit/test_agent_harness_probe.py tests/unit/test_check_handoff_facts.py tests/unit/test_check_pr_quality_gate.py tests/unit/test_local_concurrency_guard.py`.
- [x] T022 Run `uv run python scripts/agent_harness_probe.py --strict`.
- [x] T023 Run `uv run python scripts/check_handoff_facts.py --expect-pytest "2205 passed, 4 skipped" --expect-ruff "All checks passed"`.
- [x] T024 Run `python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`.
- [x] T025 Run `uv run pytest`.
- [x] T026 Run `uv run ruff check src tests`.
- [ ] T027 Update PR body and handoff records after merge if required.

## Dependencies & Execution Order

- Setup tasks T001-T003 first.
- Foundational tasks T004-T006 block user-story implementation.
- User Story 1 and 2 can proceed independently after foundation.
- User Story 3 depends on the handoff checker skeleton.
- Operating surface integration runs after the harness shape is stable.

## Implementation Strategy

Deliver one strict command that keeps existing static checks, then adds quality, redteam, and handoff
truth checks without touching trading runtime.
