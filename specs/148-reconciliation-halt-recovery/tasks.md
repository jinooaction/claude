# Tasks: 정합성 중지의 조건부 자동 복구

## Phase 1: Specification

- [x] T001 Create grade-4 SDD artifacts and safety contracts.

## Phase 2: Recovery Core

- [x] T002 Add fail-closed recovery decision/service and audit payload.
- [x] T003 Add `reconcile-recover` CLI with structured JSON output.
- [x] T004 Add recovery core and CLI tests.

## Phase 3: Production Automation

- [x] T005 Add root-owned fixed SSH helper and boundary wiring.
- [x] T006 Add automatic production recovery workflow and sidecar.
- [x] T007 Add workflow and SSH boundary regression tests.

## Phase 4: Money Path Truth

- [x] T008 Consume recovery sidecar in money-path probe and workflow.
- [x] T009 Make halt evidence the highest-priority live money gate.
- [x] T010 Add money-path unit and integration regressions.

## Phase 5: Validation and Release

- [x] T011 Run targeted and full validation, lint, harness, and quality gates.
- [ ] T012 Commit, push, open and auto-merge the PR.
- [ ] T013 Verify deployment, execute fresh recovery, and verify sidecars.
- [ ] T014 Refresh and merge HANDOFF with final production truth.
