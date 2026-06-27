# Tasks: Micro GTAA Intent-Loss Gate

**Input**: Design documents from `/specs/065-micro-gtaa-intent-loss-gate/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Required because this is a grade 4 live-money path reduction.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup

**Purpose**: Establish the safety spec and current evidence baseline.

- [X] T001 Create SDD artifacts in `specs/065-micro-gtaa-intent-loss-gate/`.
- [X] T002 Confirm latest micro GTAA sidecar has `latest_signal=INTENT_LOSS` in `origin/automation/rebalance-micro-gtaa-last-run`.

---

## Phase 2: Foundational

**Purpose**: Implement reusable intent-loss gate semantics before workflow wiring.

- [X] T003 [P] Add live-gate assessment function in `src/auto_invest/analytics/opportunity_monitor.py`.
- [X] T004 [P] Add GitHub Actions helper script in `scripts/opportunity_live_gate.py`.
- [X] T005 [P] Add gate unit tests in `tests/unit/test_opportunity_monitor.py`.

---

## Phase 3: User Story 1 - 즉시 실주문 중단 (Priority: P1)

**Goal**: Ensure the next micro GTAA run cannot submit real broker orders by default.

**Independent Test**: Sentinel static test proves `armed:false`; money path classifies it as preview-only when read.

- [X] T006 [US1] Set `armed:false` and update the reason in `automation/rebalance-micro-gtaa.request`.
- [X] T007 [US1] Update sentinel tests in `tests/unit/test_micro_gtaa_canary.py`.

---

## Phase 4: User Story 2 - 손실 의도 신호 기반 자동 차단 (Priority: P1)

**Goal**: Make the workflow refuse live submission whenever the previous monitor carries loss-intent evidence.

**Independent Test**: Workflow static tests prove the intent-loss gate runs before preflight/live and live depends on its `ok` output.

- [X] T008 [US2] Add `Pre-live strategy-intent gate` step to `.github/workflows/rebalance-micro-gtaa-canary.yml`.
- [X] T009 [US2] Gate preflight, breaker, live, and effective side output on `steps.intent_gate.outputs.ok == 'true'` in `.github/workflows/rebalance-micro-gtaa-canary.yml`.
- [X] T010 [US2] Publish the intent-loss gate decision in `LAST_RUN.md` and Telegram text from `.github/workflows/rebalance-micro-gtaa-canary.yml`.
- [X] T011 [US2] Add workflow static tests in `tests/unit/test_micro_gtaa_canary.py` and `tests/unit/test_micro_gtaa_telegram_alerts.py`.

---

## Phase 5: User Story 3 - 차단 실행이 손실 신호를 지우지 않음 (Priority: P2)

**Goal**: Preserve previous opportunity history when live did not run.

**Independent Test**: Workflow static tests prove `opportunity_monitor_sidecar.py` appends only when live result JSON exists.

- [X] T012 [US3] Update `.github/workflows/rebalance-micro-gtaa-canary.yml` so no-live runs summarize prior history without appending fallback opportunity records.
- [X] T013 [US3] Add workflow static regression test in `tests/unit/test_micro_gtaa_canary.py`.

---

## Phase 6: Validation and Handoff

**Purpose**: Prove the money-path reduction and leave the next session with current truth.

- [X] T014 Run focused tests for opportunity monitor, micro GTAA workflow, Telegram, and opportunity CLI.
- [X] T015 Run `uv run pytest` and `uv run ruff check src tests`.
- [X] T016 Update `HANDOFF.md` and add a milestone file if the PR merges.
- [X] T017 Run `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`.
