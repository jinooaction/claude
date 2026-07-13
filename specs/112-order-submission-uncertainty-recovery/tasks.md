# Tasks: Order Submission Uncertainty Recovery

**Input**: Design documents from `specs/112-order-submission-uncertainty-recovery/`
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Risk grade**: 4 — money-path safety behavior; no live execution authorized
**Tests**: Required. No KIS, Anthropic, SSH, Telegram, or paid external call is allowed in tests.

## Phase 1: Setup and Ground Truth

- [x] T001 Create SDD package under `specs/112-order-submission-uncertainty-recovery/`
- [x] T002 Update `.specify/feature.json` to point to spec 112
- [x] T003 Confirm branch, HEAD, worktree isolation, `origin/main` relationship, and open PR state
- [x] T004 Read current broker client, overseas order adapter, order router, audit payloads, notifications, CLI summaries, and focused tests
- [x] T005 Record current unsafe behavior and target behavior in the PR body `## 탐색 근거`
- [x] T006 Capture protected-file scope and prove live sentinels, caps, whitelist, constitution, and kernel are untouched

## Phase 2: Baseline and Failing Tests

- [x] T007 Add broker-client test proving per-request no-retry sends one transient-failing request
- [x] T008 Preserve broker-client tests proving default read-only retry still works
- [x] T009 Add order adapter test proving 신규 주문 5xx is one `POST` attempt
- [x] T010 Add order adapter test proving 신규 주문 transport failure is one `POST` attempt
- [x] T011 Update router 5xx test to expect `SUBMISSION_UNKNOWN` and `ORDER_SUBMISSION_UNKNOWN`
- [x] T012 Add router transport failure test for `SUBMISSION_UNKNOWN`
- [x] T013 Add router test proving HTTP 200 KIS business rejection remains `REJECTED_BY_BROKER`
- [x] T014 Add audit payload test for `ORDER_SUBMISSION_UNKNOWN`
- [x] T015 Add notification formatting test for unknown submission wording
- [x] T016 Confirm the baseline failure shape by pre-change code/test expectations where practical, then run focused tests after implementation

## Phase 3: Retry Policy

- [x] T017 Add request-scoped retry policy or equivalent no-retry option to `ResilientClient.request`
- [x] T018 Ensure no-retry still uses rate limiter and circuit breaker preflight
- [x] T019 Ensure transient no-retry failures still record circuit-breaker failure
- [x] T020 Preserve default retry behavior for existing callers

## Phase 4: Broker Adapter

- [x] T021 Apply no-retry policy to `place_order` 신규 주문 `POST`
- [x] T022 Preserve request diagnostics and masking for HTTP errors
- [x] T023 Preserve successful order-id parsing and `OrderResult`
- [x] T024 Keep explicit business rejection diagnostics available to the router

## Phase 5: Router Classification and Audit

- [x] T025 Add `ORDER_SUBMISSION_UNKNOWN` to audit event types and payload union
- [x] T026 Add a deterministic classifier for ambiguous submission errors
- [x] T027 Transition ambiguous failures `INTENT -> SUBMISSION_UNKNOWN`
- [x] T028 Append `ORDER_SUBMISSION_UNKNOWN` with diagnostics and next action
- [x] T029 Preserve explicit broker rejection path and payload
- [x] T030 Ensure no `kis_order_id` is set on unknown submissions
- [x] T031 Update docstrings/comments that currently say all broker errors become `REJECTED_BY_BROKER`

## Phase 6: Operator Surfaces

- [x] T032 Add `ORDER_SUBMISSION_UNKNOWN` to audit-tail default event types
- [x] T033 Add Korean alert title/status/details for unknown submission
- [x] T034 Include unknown submissions in read-only error counters where broker errors are counted
- [x] T035 Avoid classifying unknown submissions as confirmed rejected in user-facing text

## Phase 7: Focused Validation and Safety Review

- [x] T036 Run focused broker/order/audit/notification tests
- [x] T037 Run static search for retry policy, new state, new event, and old rejection wording
- [x] T038 Confirm no live sentinel, cap, whitelist, loss budget, constitution, or kernel manifest change
- [x] T039 Review the diff as implementer, reviewer, safety owner, and handoff owner

## Phase 8: Full Repository Gates

- [x] T040 Run `uv run pytest`
- [x] T041 Run `uv run ruff check src tests`
- [x] T042 Run `git diff --check`
- [x] T043 Run `uv run python scripts/check_handoff_facts.py`
- [x] T044 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T045 Prepare PR body and run `python3 scripts/check_pr_quality_gate.py /tmp/pr-body-112.md`
- [x] T046 Confirm no actual KIS, Anthropic, SSH, Telegram, live workflow dispatch, or server command was executed

## Phase 9: Merge and Handoff

- [x] T047 Update `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md` with spec 112 result and remaining risks
- [x] T048 Mark this task file complete only after all required gates pass
- [x] T049 Push branch and open PR
- [x] T050 Merge using repository `merge` policy when automatic merge conditions are satisfied
- [x] T051 Verify the `main` merge commit and relevant post-merge workflows
- [x] T052 Refresh root `HANDOFF.md` in the repository-standard follow-up PR
- [x] T053 Name `113-atomic-fill-ledger` as the next execution-safety work item unless new evidence changes priority

## Dependencies & Execution Order

1. Phase 1 establishes truth and protected-scope boundaries.
2. Phase 2 locks failing behavior.
3. Phase 3 adds request policy.
4. Phase 4 applies it to broker order submission.
5. Phase 5 records unknown submissions.
6. Phase 6 exposes the state to operators.
7. Phases 7-9 validate, merge, observe, and hand off.

## Completion Rule

This feature is complete only when:

```text
order POST no blind retry
AND ambiguous write failure is not broker rejection
AND operators can see the unknown state
```

## Explicitly Forbidden During This Task

- Placing or cancelling a real order
- Triggering live workflows
- Changing live sentinels, capital, caps, whitelist, or loss budget
- Changing constitution or kernel manifest
- Adding blind automatic recovery that guesses broker acceptance
