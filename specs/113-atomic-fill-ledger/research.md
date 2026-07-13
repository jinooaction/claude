# Research: Atomic Fill Ledger

## Decision: Use an explicit SQLite `BEGIN IMMEDIATE` transaction in fill application

**Rationale**: Repository connections run in autocommit mode by default. That is appropriate for append-only audit events but unsafe for a multi-table fill application. `BEGIN IMMEDIATE` acquires the writer lock before changing `fills`, `audit_log`, `current_positions`, and `orders`, so concurrent local writers cannot interleave a partial view.

**Alternatives considered**:

- Use `with conn:` only: rejected because autocommit connections do not make the transaction boundary obvious enough for this money-path invariant.
- Add a new database wrapper: rejected because one localized transaction in `fill_sync.py` is sufficient.

## Decision: Insert `fills` first, then append audit and update position only if insert succeeds

**Rationale**: `kis_fill_id` is the idempotency key. If the insert is ignored, the fill is already represented in the ledger and must not create another `FILL` audit or move the cache. If a later audit/cache step fails, the transaction rolls back the inserted fill too.

**Alternatives considered**:

- Keep audit first and inspect `rowcount` afterward: rejected because duplicate fills would still create duplicate audit events.
- Replace `INSERT OR IGNORE` with a pre-read: rejected because it is more race-prone and still needs unique-key enforcement.

## Decision: Keep negative-position policy out of this PR

**Rationale**: Some account-wide liquidation paths can sell externally held positions that are not represented by local buy fills. Blocking that in the atomicity PR could change trading behavior beyond the requested accounting invariant.

**Alternatives considered**:

- Add `qty >= 0` DB constraint now: rejected because it requires a schema migration and a broader external-holdings design decision.

## Decision: Leave `SUBMISSION_UNKNOWN` recovery for a later feature

**Rationale**: Broker order lookup recovery and account degraded state are distinct safety problems. Mixing them with fill ledger atomicity would expand the blast radius and make validation less precise.

**Alternatives considered**:

- Implement recovery lookup now: rejected because it needs broker semantics and new execution-state policy beyond this PR.
