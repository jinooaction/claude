# Tasks: Atomic Fill Ledger

**Input**: Design documents from `specs/113-atomic-fill-ledger/`
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Risk grade**: 4 — money-path accounting safety behavior; no live execution authorized
**Tests**: Required. No KIS, Anthropic, SSH, Telegram, or paid external call is allowed in tests.

## Phase 1: Setup and Ground Truth

- [x] T001 Create SDD package under `specs/113-atomic-fill-ledger/`
- [x] T002 Update `.specify/feature.json` to point to spec 113
- [x] T003 Confirm branch, worktree isolation, `origin/main` relationship, and open PR state
- [x] T004 Read current fill sync, positions cache, audit writer, migration schema, and focused tests
- [x] T005 Record scope boundaries: no live arming, no broker writes, no capital/whitelist/caps/loss-budget changes

## Phase 2: Baseline and Failing Tests

- [x] T006 Add duplicate planned fill test in `tests/integration/test_fill_sync.py`
- [x] T007 Add injected position-cache failure rollback test in `tests/integration/test_fill_sync.py`
- [x] T008 Confirm focused tests fail or would fail on the old implementation shape

## Phase 3: Atomic Fill Application

- [x] T009 Wrap `apply_fill_plan` writes in `BEGIN IMMEDIATE` transaction in `src/auto_invest/execution/fill_sync.py`
- [x] T010 Insert into `fills` before appending `FILL` audit in `src/auto_invest/execution/fill_sync.py`
- [x] T011 Skip audit and position update when `INSERT OR IGNORE` inserts zero rows
- [x] T012 Count only inserted fills in `fills_applied` and `qty_applied`
- [x] T013 Roll back the transaction on any apply exception
- [x] T014 Preserve existing order transition and cancel audit behavior inside the transaction

## Phase 4: Focused Validation

- [x] T015 Run `uv run pytest tests/integration/test_fill_sync.py`
- [x] T016 Run `uv run pytest tests/integration/test_worker_fill_sync.py`
- [x] T017 Run focused position/audit/performance tests if touched behavior suggests risk
- [x] T018 Search diff for forbidden live sentinel, capital, caps, whitelist, loss budget, constitution, and kernel changes

## Phase 5: Full Repository Gates

- [x] T019 Run `git diff --check`
- [x] T020 Run `uv run pytest`
- [x] T021 Run `uv run ruff check src tests`
- [x] T022 Run `uv run python scripts/check_handoff_facts.py`
- [x] T023 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T024 Prepare PR body and run `python3 scripts/check_pr_quality_gate.py`
- [x] T025 Confirm no actual KIS, Anthropic, SSH, Telegram, live workflow dispatch, or server command was executed

## Phase 6: Merge and Handoff

- [x] T026 Update `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md` with spec 113 result and remaining risks
- [x] T027 Mark this task file complete only after all required gates pass
- [ ] T028 Push branch and open PR
- [ ] T029 Merge using repository `merge` policy when automatic merge conditions are satisfied
- [ ] T030 Verify the `main` merge commit and relevant post-merge workflows
- [ ] T031 Refresh root `HANDOFF.md` in the repository-standard follow-up PR if main operating truth changed
- [ ] T032 Name `114-account-exposure-reservation` as the next execution-safety work item unless new evidence changes priority

## Dependencies & Execution Order

1. Phase 1 establishes truth and protected-scope boundaries.
2. Phase 2 locks the failure shape.
3. Phase 3 changes the accounting write path.
4. Phase 4 validates focused behavior.
5. Phase 5 validates repository-wide safety.
6. Phase 6 publishes, observes, and hands off.

## Completion Rule

This feature is complete only when:

```text
new fill + audit + position + state commit together
AND duplicate fill does not move position cache
AND partial apply failure leaves no partial ledger facts
```

## Explicitly Forbidden During This Task

- Placing or cancelling a real order
- Triggering live workflows
- Changing live sentinels, capital, caps, whitelist, or loss budget
- Changing constitution or kernel manifest
- Implementing `SUBMISSION_UNKNOWN` automatic recovery in this PR
