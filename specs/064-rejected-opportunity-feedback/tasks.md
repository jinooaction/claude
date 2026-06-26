# Tasks: Rejected Opportunity Feedback Loop

**Input**: Design documents from `specs/064-rejected-opportunity-feedback/`  
**Prerequisites**: spec.md, plan.md

**Tests**: Required because this changes operational workflow evidence and autonomous reassignment inputs.

## Phase 1: Setup

- [x] T001 Update `.specify/feature.json` to point to `specs/064-rejected-opportunity-feedback`
- [x] T002 Add SDD artifacts for rejected opportunity feedback

## Phase 2: Foundational

- [x] T003 Add rolling opportunity monitor module and sidecar helper script
- [x] T004 Add CLI command and safety registry entry

## Phase 3: User Story 1 - 누적 전략 의도 손익을 본다

- [x] T005 Add monitor unit tests for intended gain/loss, insufficient data, strategy review, execution review, and history capping
- [x] T006 Add CLI integration tests for history update and monitor output

## Phase 4: User Story 2 - 자동 실행 루프가 같은 증거를 계속 갱신한다

- [x] T007 Update micro GTAA workflow to fetch previous history, publish `opportunity_history.json` and `opportunity_monitor.json`
- [x] T008 Update sidecar markdown and Telegram message with cumulative verdict
- [x] T009 Extend workflow unit tests for sidecar and Telegram wiring

## Phase 5: User Story 3 - 자율 재지정 루프가 신호를 입력으로 본다

- [x] T010 Add execution feedback input to `reassign-decide` JSON without changing action semantics
- [x] T011 Update `reassign-on-tournament.yml` to fetch and pass latest opportunity monitor summary
- [x] T012 Add reassign decision and workflow tests for feedback evidence

## Phase 6: Polish & Validation

- [x] T013 Run focused tests
- [x] T014 Run full `uv run pytest`
- [x] T015 Run full `uv run ruff check src tests`
- [x] T016 Run handoff fact check and strict agent harness
- [ ] T017 Open/merge PR and refresh handoff
