# Data Model: Single Execution Authority

## `execution_authority_locks`

One row per locked account.

| Column | Type | Meaning |
|---|---|---|
| `account_no` | TEXT PRIMARY KEY | KIS account identifier. |
| `owner` | TEXT NOT NULL | Unique process-local authority owner id. |
| `context` | TEXT NOT NULL | Human-readable action context. |
| `acquired_at_utc` | TEXT NOT NULL | Lock acquisition time. |
| `expires_at_utc` | TEXT NOT NULL | Stale-lock expiry time. |

## Invariants

- At most one live broker write scope exists per account.
- Expired locks may be reclaimed.
- Release deletes only the row owned by the releasing authority.
- Paper and dry-run paths do not create lock rows.
