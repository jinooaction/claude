# Implementation Plan: Single Execution Authority

## Summary

Create one authority object for broker writes, backed by an SQLite account lock. Route `OrderRouter` live submissions and worker lifecycle cancels through that object. Keep paper and dry-run behavior unchanged.

## Technical Context

- Language: Python 3.11
- Database: existing SQLite migration system
- Existing broker write helpers: `broker.overseas.place_order`, `broker.overseas.cancel_order`
- Existing live order gate: `OrderRouter.submit_order`
- Existing cancel path: `Worker._execute_lifecycle_action`

## Constitution and Safety

- Grade 4 money-path shape change, no actual live execution.
- Kernel behavior is contracted: fewer broker write callers, no widened capability.
- Audit log remains append-only; no destructive DB operations.
- Existing live sentinels and capital settings stay untouched.

## Design

1. Add `execution_authority_locks` migration.
2. Add `ExecutionAuthority` with:
   - account-scoped async lock context
   - broker submit wrapper
   - broker cancel wrapper
3. Construct one authority per live worker/router.
4. Acquire authority lock inside `OrderRouter.submit_order` before open-order reservation and gates.
5. Use authority cancel wrapper in lifecycle management.
6. Strengthen AST guard tests so broker mutations are allowed only in `authority.py`.

## Validation

- Focused authority tests.
- Router live lock rejection tests.
- Lifecycle cancel lock rejection tests.
- Existing router, worker lifecycle, and rebalancer tests.
- Full `uv run pytest -q`.
- `uv run ruff check src tests`.
- `uv run python scripts/check_handoff_facts.py`.
- `uv run python scripts/agent_harness_probe.py --strict`.
