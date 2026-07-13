# Implementation Plan: Order Submission Uncertainty Recovery

**Branch**: `Codex/112-order-submission-uncertainty-recovery` | **Date**: 2026-07-13 | **Spec**: `specs/112-order-submission-uncertainty-recovery/spec.md`
**Input**: Feature specification from `specs/112-order-submission-uncertainty-recovery/spec.md`

## Summary

Stop blind automatic retry for the KIS 신규 주문 `POST`, keep existing resilience for read-only calls, and make ambiguous write failures visible as `SUBMISSION_UNKNOWN` instead of `REJECTED_BY_BROKER`.

The implementation uses a small request-scoped retry policy on `ResilientClient`, applies no-retry only to `place_order`, classifies broker diagnostics in `OrderRouter`, adds an append-only audit payload, updates operator alert/read-only summaries, and locks the behavior with integration tests.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: `httpx`, `tenacity`, `pydantic`, `sqlite3`, `pytest`, `respx`, `ruff`
**Storage**: SQLite via `src/auto_invest/persistence/db.py`
**Testing**: `uv run pytest`, focused `pytest` paths, `uv run ruff check src tests`
**Target Platform**: local worker and GitHub Actions; no live broker calls during tests
**Project Type**: single Python package with CLI, worker, broker adapter, persistence, analytics
**Performance Goals**: no new network calls in normal failure path; no retry delay for order-submit failures
**Constraints**: append-only audit log, no secret leakage, no actual orders, no live sentinel/cap changes
**Scope**: broker client, overseas order adapter, order router, audit payload, notification formatting, tests, handoff

## Constitution Check

Risk grade: **4** — money-path safety behavior. The change is a contraction of live risk and does not authorize live execution.

- Principle I/II/III: position caps, whitelist, and `Backtest -> Canary -> Full` promotion are untouched.
- Principle IV: add new audit event only; do not mutate historical audit rows.
- Principle VII: external API failure handling becomes more conservative for broker writes.
- Principle VIII.A/IX/X: no constitution, kernel, live sentinels, capital, or deployment authority changes.
- Secret boundary: diagnostics continue to use existing masking helpers.

## Project Structure

### Documentation

```text
specs/112-order-submission-uncertainty-recovery/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── order-submission-boundary.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Targets

```text
src/auto_invest/broker/client.py
src/auto_invest/broker/diagnostics.py
src/auto_invest/broker/overseas.py
src/auto_invest/execution/order_router.py
src/auto_invest/persistence/audit.py
src/auto_invest/notifications/audit_tail.py
src/auto_invest/cli.py
```

### Test Targets

```text
tests/integration/test_broker_client.py
tests/integration/test_broker_order_diagnostics.py
tests/integration/test_order_router.py
tests/unit/test_audit.py
tests/unit/test_telegram_alerts.py
```

## Phase Plan

1. Ground truth: confirm current retry and router classification behavior.
2. Baseline tests: add or update focused tests that fail on existing behavior.
3. Retry policy: add no-retry request option and preserve default retries.
4. Broker adapter: call order-submit `POST` with no retry.
5. Failure classification: add explicit ambiguous-submission classifier and audit payload.
6. Operator surfaces: update alert text and read-only counters.
7. Validation: focused tests, full tests, lint, diff check, handoff/harness, PR gate.
8. Merge and handoff refresh if automatic merge conditions are satisfied.

## Complexity Tracking

No new abstraction beyond request-scoped retry policy and classification helper. No database migration is required because `orders.state` is unconstrained text and `audit_log.event_type` is unconstrained text.

## Rollback Plan

Rollback is a normal revert of the feature commit. Operationally, rollback would restore automatic retry for order submission, so it should only be used if the no-retry path prevents all order submission even in preview/canary testing. No data migration rollback is needed.

## Completion Criteria

- KIS 신규 주문 `POST` retry count is one on 5xx and transport failure.
- Read-only transient retry behavior remains unchanged.
- Ambiguous write failures persist `SUBMISSION_UNKNOWN` plus `ORDER_SUBMISSION_UNKNOWN`.
- Explicit business rejections remain `REJECTED_BY_BROKER`.
- Full repository gates and handoff checks pass.
