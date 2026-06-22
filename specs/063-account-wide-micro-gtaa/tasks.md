# Tasks: Account-Wide Micro GTAA Autonomous Rebalance

**Input**: Design documents from `specs/063-account-wide-micro-gtaa/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this feature changes a real-money operating path.

## Phase 1: Setup

- [x] T001 Update `.specify/feature.json` to point to `specs/063-account-wide-micro-gtaa`
- [x] T002 Add SDD artifacts in `specs/063-account-wide-micro-gtaa/`

---

## Phase 2: Foundational

**Purpose**: Define account-wide settings and current workflow expectations before changing live behavior.

- [x] T003 [P] Add portfolio config invariant tests for account-wide liquidation-only settings in `tests/unit/test_canary_portfolio_config.py`
- [x] T004 [P] Add workflow account-wide preview and sell-only gate tests in `tests/unit/test_micro_gtaa_canary.py`
- [x] T005 Add account-wide planning tests for broker snapshot, liquidation-only sells, and buy refusal in `tests/integration/test_spec_032_live_rebalancer.py`

---

## Phase 3: User Story 1 - 계좌 전체를 보고 판단한다 (Priority: P1) MVP

**Goal**: Live planning uses actual broker holdings and cash, while target buys remain limited to micro GTAA symbols.

**Independent Test**: Account-wide planning tests classify target, liquidation-only, and unmanaged holdings and refuse liquidation-only buys.

- [x] T006 [US1] Add account-wide settings parsing to `src/auto_invest/cli.py`
- [x] T007 [US1] Extend `src/auto_invest/execution/rebalancer.py` to accept broker-position snapshots and liquidation-only symbols without mutating the fill ledger
- [x] T008 [US1] Update `deploy/micro-gtaa-live-portfolio.toml` with explicit account-wide liquidation-only settings
- [x] T009 [US1] Preserve target-universe-only buy behavior in config and tests

---

## Phase 4: User Story 2 - 현금이 부족하면 매도부터 지속 실행한다 (Priority: P1)

**Goal**: Cash shortfall triggers an autonomous sell-only cycle, and buys wait for KIS-confirmed purchasable cash.

**Independent Test**: Low-cash snapshots with eligible sells produce zero buy submissions and at least one sell candidate.

- [x] T010 [US2] Add side filtering and cash-buffer gating to `src/auto_invest/execution/rebalancer.py`
- [x] T011 [US2] Add `--account-wide` and `--side both|sell|buy` behavior to `src/auto_invest/cli.py`
- [x] T012 [US2] Update `.github/workflows/rebalance-micro-gtaa-canary.yml` to run account-wide preview and choose sell-only when preflight requires it

---

## Phase 5: User Story 3 - 실시간 지속 운영 증거를 남긴다 (Priority: P2)

**Goal**: The sidecar and alerts explain account-wide mode, sell-only cycles, withheld buys, and next expected action.

**Independent Test**: Workflow unit tests verify sidecar sections and Telegram text include account-wide state.

- [x] T013 [US3] Extend sidecar generation in `.github/workflows/rebalance-micro-gtaa-canary.yml` with account-wide mode, effective side, cash requirement, withheld orders, and next step
- [x] T014 [US3] Extend Telegram summary in `.github/workflows/rebalance-micro-gtaa-canary.yml` with sell-only and next-step evidence

---

## Phase 6: User Story 4 - 기존 돈 경로 안전장치를 유지한다 (Priority: P2)

**Goal**: Existing K1/K2/K4/K5/K6 safety boundaries remain enforceable and visible.

**Independent Test**: Focused safety tests plus full repository tests pass without weakening existing contracts.

- [x] T015 [US4] Ensure live orders still route through existing `OrderRouter` and append-only audit behavior in `src/auto_invest/execution/rebalancer.py`
- [x] T016 [US4] Update `specs/063-account-wide-micro-gtaa/contracts/account-wide-micro-gtaa.md` if implementation changes the documented contract

---

## Phase 7: Polish & Validation

- [x] T017 Run focused tests: `uv run pytest tests/integration/test_spec_032_live_rebalancer.py tests/unit/test_canary_portfolio_config.py tests/unit/test_micro_gtaa_canary.py`
- [x] T018 Run full validation: `uv run pytest` and `uv run ruff check src tests`
- [x] T019 Run PR quality gate template check: `python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`
- [ ] T020 Update PR body and handoff if merge completes

## Dependencies & Execution Order

- Setup tasks T001-T002 are complete before implementation.
- Foundational tests T003-T005 should be written before implementation tasks.
- User Story 1 is the MVP and blocks User Story 2 because sell-first depends on broker snapshot classification.
- User Story 3 depends on User Story 2 evidence fields.
- User Story 4 is checked after implementation but must influence every earlier change.
- Polish validation runs after all implementation tasks.

## Parallel Opportunities

- T003 and T004 can be edited in parallel with different test files.
- T005 can be designed while workflow tests are added, but implementation waits for T006-T011.
- Documentation contract updates can run in parallel after the final CLI/workflow shape settles.

## Implementation Strategy

1. Add failing tests for liquidation-only classification, buy refusal, cash-shortfall sell-only behavior, and workflow gates.
2. Extend the existing rebalancer and CLI instead of creating a separate order path.
3. Update the micro workflow to preview account-wide state and choose sell-only when cash is insufficient.
4. Validate focused tests first, then full test and lint gates before PR.
