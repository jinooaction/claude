# Contract: Single Execution Authority

## Allowed Effects

- Insert, delete, and inspect rows in `execution_authority_locks`.
- Call KIS broker mutation helpers from `src/auto_invest/execution/authority.py`.
- Reject an order through the existing gate-audit path when the authority lock is busy.

## Forbidden Effects

- No direct `place_order` or `cancel_order` calls outside `authority.py`.
- No real order execution during tests or this implementation session.
- No sentinel arming, capital scaling, whitelist widening, or cap increase.
- No deletion or mutation of audit log or fills.

## Required Evidence

- AST guard showing broker mutations have one owner.
- Router test showing a busy authority lock blocks before broker contact.
- Worker lifecycle test showing cancel respects the same lock.
- Full test and lint evidence before merge.
