-- Migration 0002: data infrastructure + backtest engine schema (spec 002).
--
-- Mirrors specs/002-data-and-backtest/data-model.md.
-- All new tables are append-only with revisions; UPDATE/DELETE are
-- blocked by triggers (constitution principle IV).
--
-- All DDL uses IF NOT EXISTS so a partial migration is retry-safe.

------------------------------------------------------------
-- historical_bars (append-only with revisions via as_of_ts_utc)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historical_bars (
    asset_class       TEXT NOT NULL,
    venue             TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    kind              TEXT NOT NULL,
    vendor            TEXT NOT NULL,
    bar_open_ts_utc   TEXT NOT NULL,
    as_of_ts_utc      TEXT NOT NULL,
    open              TEXT NOT NULL,
    high              TEXT NOT NULL,
    low               TEXT NOT NULL,
    close             TEXT NOT NULL,
    volume            TEXT NOT NULL,
    is_adjusted       INTEGER NOT NULL DEFAULT 0,
    frozen            INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (asset_class, venue, symbol, kind, vendor, bar_open_ts_utc, as_of_ts_utc, is_adjusted)
);

CREATE INDEX IF NOT EXISTS idx_historical_bars_read
    ON historical_bars(asset_class, venue, symbol, kind, bar_open_ts_utc);
CREATE INDEX IF NOT EXISTS idx_historical_bars_revisions
    ON historical_bars(as_of_ts_utc);

CREATE TRIGGER IF NOT EXISTS historical_bars_no_update
BEFORE UPDATE ON historical_bars
WHEN OLD.frozen = 1
BEGIN
    SELECT RAISE(ABORT, 'historical_bars is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS historical_bars_no_delete
BEFORE DELETE ON historical_bars
WHEN OLD.frozen = 1
BEGIN
    SELECT RAISE(ABORT, 'historical_bars is append-only (constitution IV)');
END;

------------------------------------------------------------
-- event_series (append-only with revisions; non-OHLCV time series)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_series (
    asset_class    TEXT,
    venue          TEXT,
    symbol         TEXT,
    kind           TEXT NOT NULL,
    vendor         TEXT NOT NULL,
    event_ts_utc   TEXT NOT NULL,
    as_of_ts_utc   TEXT NOT NULL,
    payload_json   TEXT NOT NULL,
    frozen         INTEGER NOT NULL DEFAULT 1
);

-- SQLite cannot include nullable columns in a primary key cleanly;
-- a unique-with-COALESCE index reproduces the (NULL-aware) key.
CREATE UNIQUE INDEX IF NOT EXISTS idx_event_series_pk
    ON event_series(
        kind, vendor, event_ts_utc, as_of_ts_utc,
        COALESCE(asset_class, ''),
        COALESCE(venue, ''),
        COALESCE(symbol, '')
    );
CREATE INDEX IF NOT EXISTS idx_event_series_read
    ON event_series(kind, symbol, event_ts_utc);

CREATE TRIGGER IF NOT EXISTS event_series_no_update
BEFORE UPDATE ON event_series
WHEN OLD.frozen = 1
BEGIN
    SELECT RAISE(ABORT, 'event_series is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS event_series_no_delete
BEFORE DELETE ON event_series
WHEN OLD.frozen = 1
BEGIN
    SELECT RAISE(ABORT, 'event_series is append-only (constitution IV)');
END;

------------------------------------------------------------
-- corporate_actions (append-only with revisions)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS corporate_actions (
    asset_class       TEXT NOT NULL,
    venue             TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    vendor            TEXT NOT NULL,
    action_kind       TEXT NOT NULL,
    effective_ts_utc  TEXT NOT NULL,
    as_of_ts_utc      TEXT NOT NULL,
    payload_json      TEXT NOT NULL,
    frozen            INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (asset_class, venue, symbol, vendor, action_kind, effective_ts_utc, as_of_ts_utc)
);

CREATE INDEX IF NOT EXISTS idx_corporate_actions_read
    ON corporate_actions(asset_class, venue, symbol, effective_ts_utc);

CREATE TRIGGER IF NOT EXISTS corporate_actions_no_update
BEFORE UPDATE ON corporate_actions
WHEN OLD.frozen = 1
BEGIN
    SELECT RAISE(ABORT, 'corporate_actions is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS corporate_actions_no_delete
BEFORE DELETE ON corporate_actions
WHEN OLD.frozen = 1
BEGIN
    SELECT RAISE(ABORT, 'corporate_actions is append-only (constitution IV)');
END;

------------------------------------------------------------
-- data_quality_events (append-only)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_quality_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_ts_utc  TEXT NOT NULL,
    asset_class   TEXT NOT NULL,
    venue         TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    kind          TEXT NOT NULL,
    vendor        TEXT,
    payload_json  TEXT NOT NULL,
    severity      TEXT NOT NULL CHECK (severity IN ('info','warn','block'))
);

CREATE INDEX IF NOT EXISTS idx_data_quality_read
    ON data_quality_events(asset_class, venue, symbol, event_ts_utc);
CREATE INDEX IF NOT EXISTS idx_data_quality_severity
    ON data_quality_events(severity);

CREATE TRIGGER IF NOT EXISTS data_quality_events_no_update
BEFORE UPDATE ON data_quality_events
BEGIN
    SELECT RAISE(ABORT, 'data_quality_events is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS data_quality_events_no_delete
BEFORE DELETE ON data_quality_events
BEGIN
    SELECT RAISE(ABORT, 'data_quality_events is append-only (constitution IV)');
END;

------------------------------------------------------------
-- backtest_runs (append-only — terminal state once written)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id              TEXT PRIMARY KEY,
    created_ts_utc      TEXT NOT NULL,
    rule_snapshot_hash  TEXT NOT NULL,
    config_hash         TEXT NOT NULL,
    instruments_json    TEXT NOT NULL,
    window_from_utc     TEXT NOT NULL,
    window_to_utc       TEXT NOT NULL,
    as_of_ts_pin_utc    TEXT NOT NULL,
    mode                TEXT NOT NULL CHECK (mode IN ('single','walkforward','oos')),
    result_status       TEXT NOT NULL,
    frozen              INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_rule
    ON backtest_runs(rule_snapshot_hash);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_created
    ON backtest_runs(created_ts_utc);

CREATE TRIGGER IF NOT EXISTS backtest_runs_no_update
BEFORE UPDATE ON backtest_runs
BEGIN
    SELECT RAISE(ABORT, 'backtest_runs is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS backtest_runs_no_delete
BEFORE DELETE ON backtest_runs
BEGIN
    SELECT RAISE(ABORT, 'backtest_runs is append-only (constitution IV)');
END;

------------------------------------------------------------
-- promotion_seals (append-only — revoke writes a NEW row)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promotion_seals (
    seal_id              TEXT PRIMARY KEY,
    issued_ts_utc        TEXT NOT NULL,
    rule_snapshot_hash   TEXT NOT NULL,
    backtest_run_id      TEXT NOT NULL,
    oos_metrics_json     TEXT NOT NULL,
    thresholds_json      TEXT NOT NULL,
    revoked              INTEGER NOT NULL DEFAULT 0,
    frozen               INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_promotion_seals_rule
    ON promotion_seals(rule_snapshot_hash);
CREATE INDEX IF NOT EXISTS idx_promotion_seals_run
    ON promotion_seals(backtest_run_id);

CREATE TRIGGER IF NOT EXISTS promotion_seals_no_update
BEFORE UPDATE ON promotion_seals
BEGIN
    SELECT RAISE(ABORT, 'promotion_seals is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS promotion_seals_no_delete
BEFORE DELETE ON promotion_seals
BEGIN
    SELECT RAISE(ABORT, 'promotion_seals is append-only (constitution IV)');
END;

------------------------------------------------------------
-- divergence_events (append-only)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS divergence_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_ts_utc    TEXT NOT NULL,
    seal_id         TEXT NOT NULL,
    metric_kind     TEXT NOT NULL,
    live_value      TEXT NOT NULL,
    backtest_value  TEXT NOT NULL,
    divergence_pct  TEXT NOT NULL,
    breached        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_divergence_seal
    ON divergence_events(seal_id, event_ts_utc);

CREATE TRIGGER IF NOT EXISTS divergence_events_no_update
BEFORE UPDATE ON divergence_events
BEGIN
    SELECT RAISE(ABORT, 'divergence_events is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS divergence_events_no_delete
BEFORE DELETE ON divergence_events
BEGIN
    SELECT RAISE(ABORT, 'divergence_events is append-only (constitution IV)');
END;
