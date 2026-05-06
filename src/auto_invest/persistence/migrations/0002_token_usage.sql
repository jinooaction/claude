-- Migration 0002: token_usage telemetry table for spec 002.
--
-- Append-only per FR-T04 / constitution IV. Triggers reject any
-- UPDATE / DELETE. All DDL uses IF NOT EXISTS so a partial migration
-- is retry-safe.

CREATE TABLE IF NOT EXISTS token_usage (
    seq                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc             TEXT NOT NULL,
    model              TEXT NOT NULL,
    decision_class     TEXT,
    input_tokens       INTEGER NOT NULL DEFAULT 0,
    output_tokens      INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens  INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd           TEXT,
    latency_ms         INTEGER NOT NULL DEFAULT 0,
    error_class        TEXT,
    correlation_id     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_token_usage_ts          ON token_usage(ts_utc);
CREATE INDEX IF NOT EXISTS idx_token_usage_class_ts    ON token_usage(decision_class, ts_utc);
CREATE INDEX IF NOT EXISTS idx_token_usage_model_ts    ON token_usage(model, ts_utc);
CREATE INDEX IF NOT EXISTS idx_token_usage_correlation ON token_usage(correlation_id);

CREATE TRIGGER IF NOT EXISTS token_usage_no_update
BEFORE UPDATE ON token_usage
BEGIN
    SELECT RAISE(ABORT, 'token_usage is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS token_usage_no_delete
BEFORE DELETE ON token_usage
BEGIN
    SELECT RAISE(ABORT, 'token_usage is append-only (constitution IV)');
END;
