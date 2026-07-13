# Implementation Plan: Submission Unknown Broker Lookup

## Summary

Extend the existing read-only fill synchronization path so unresolved `SUBMISSION_UNKNOWN` orders are reconciled against KIS `inquire-ccnl` history. A unique strong match attaches the broker order id and falls through to the normal fill planner. Ambiguous or missing evidence stays fail-closed.

## Technical Context

- Language: Python 3.11
- Database: existing SQLite schema; no new table required
- Existing broker read helper: `broker.overseas.get_order_executions_resolving_market`
- Existing recovery surface: `execution.fill_sync.sync_fills`
- Existing state blocker: `execution.execution_state.evaluate_execution_state`
- Testing: pytest with respx broker mocks

## Constitution and Safety

- Grade 4 money-path recovery change, no actual live execution.
- Principles I and II remain stricter: unresolved BUY uncertainty keeps blocking new exposure.
- Principle IV is preserved: recovery appends audit evidence and never mutates existing audit/fill rows.
- Principle V is preserved: no new secret surfaces or logging of credentials.
- Principle VII is preserved: all broker contact is read-only and uses the existing resilient client.
- Principle IX/Kernal high-attention files are not modified.

## Design

1. Add an `ORDER_SUBMISSION_RECOVERED` audit payload.
2. Add unknown-submission loading and strong-match planning in `execution.fill_sync`.
3. Treat symbol, side, and total quantity as the minimum safe match contract.
4. Apply recovery before fill planning inside the existing fill-sync broker poll.
5. Reuse recovered executions for normal fill planning in the same call.
6. Extend `FillSyncResult` with recovery counts and warnings.
7. Add regression tests for unique match, unfilled match, ambiguity, lookup failure, and unchanged submitted-order sync.

## Validation

- Focused fill-sync recovery tests.
- Existing fill-sync integration tests.
- Execution-state test confirming unresolved unknown still degrades.
- Live-order-path AST guard to prove no new broker mutation caller.
- Full `uv run pytest -q`.
- `uv run ruff check src tests`.
- `git diff --check`.
- `uv run python scripts/check_handoff_facts.py`.
- `uv run python scripts/agent_harness_probe.py --strict`.

