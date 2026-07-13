-- Migration 0004: account-scoped execution authority locks.
--
-- One row means one live broker-write scope currently owns the account.
-- Expired rows may be reclaimed by a later authority instance.

CREATE TABLE IF NOT EXISTS execution_authority_locks (
    account_no      TEXT PRIMARY KEY,
    owner           TEXT NOT NULL,
    context         TEXT NOT NULL,
    acquired_at_utc TEXT NOT NULL,
    expires_at_utc  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_authority_locks_expires
    ON execution_authority_locks(expires_at_utc);
