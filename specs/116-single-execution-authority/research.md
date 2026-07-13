# Research: Single Execution Authority

## Decision: SQLite account lock instead of a daemon

The repo already shares a SQLite database between worker and rebalance commands. A lock table can serialize broker write attempts across processes without adding a new service or external dependency.

Rejected alternative: a long-running authority service. It is a larger deployment change and would mix process management into this safety contraction.

## Decision: Acquire before gate evaluation

The stale-snapshot bug is not closed if the lock is held only around the HTTP `POST`. The lock must cover open-order reservation and gate evaluation so the second process sees the first process's committed state.

Rejected alternative: wrap only `place_order`. That serializes broker calls but allows two processes to pass K1 gates from the same old snapshot.

## Decision: Fail closed when busy

A live order that cannot acquire authority quickly becomes a gate rejection. The next scheduled tick or manual run can retry from fresh state. This keeps the account from running overlapping write decisions.

## Decision: Leave paper and dry-run lock-free

Paper and dry-run do not mutate the broker. Locking them would make read-only previews interfere with live safety without improving broker write control.
