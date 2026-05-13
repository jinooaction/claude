-- Migration 0003: BACKTEST_* event types (spec 008)
--
-- Adds NO new columns to audit_log. The append-only invariants from
-- 0001_initial.sql (constitution principle IV) continue to apply
-- unchanged: the existing audit_log_no_update / audit_log_no_delete
-- triggers protect every event_type, including the three new ones.
--
-- This migration ONLY adds a partial index optimised for SC-B06:
-- "answer 'show me every backtest run in the last 30 days, its
-- verdict, and its dataset hash' using a single SQL query".
--
-- The partial index is small (event_type cardinality is low and
-- BACKTEST_* rows are a minority) and turns SC-B06 from a table
-- scan into a seek.
--
-- This migration is a Kernel file: it is registered in
-- .specify/memory/kernel.toml group [K4_append_only_audit].

CREATE INDEX IF NOT EXISTS idx_audit_log_backtest_events
    ON audit_log (event_type, ts_utc)
    WHERE event_type IN (
        'BACKTEST_STARTED',
        'BACKTEST_COMPLETED',
        'BACKTEST_FAILED'
    );
