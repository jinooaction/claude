-- Migration 0001: initial schema for auto-invest v1.0.0
--
-- Mirrors specs/001-automated-trading-mvp/data-model.md.
-- Tables marked "append-only" are protected by triggers that abort
-- UPDATE / DELETE statements. The append-only invariant is non-
-- negotiable per constitution principle IV.
--
-- All DDL uses IF NOT EXISTS so a partial migration is retry-safe.

------------------------------------------------------------
-- audit_log (append-only)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc         TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    rule_id        TEXT,
    symbol         TEXT,
    payload_json   TEXT NOT NULL,
    correlation_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_ts          ON audit_log(ts_utc);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_ts    ON audit_log(event_type, ts_utc);
CREATE INDEX IF NOT EXISTS idx_audit_log_rule_ts     ON audit_log(rule_id, ts_utc);
CREATE INDEX IF NOT EXISTS idx_audit_log_correlation ON audit_log(correlation_id);

CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only (constitution IV)');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only (constitution IV)');
END;

------------------------------------------------------------
-- orders (append-only ledger; state column is a cache of the latest
-- row in order_state_history, see data-model.md)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    seq                INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id     TEXT NOT NULL UNIQUE,
    rule_id            TEXT NOT NULL,
    symbol             TEXT NOT NULL,
    side               TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    order_type         TEXT NOT NULL CHECK (order_type IN ('LIMIT','MARKET')),
    qty                INTEGER NOT NULL CHECK (qty > 0),
    limit_price_usd    TEXT,
    state              TEXT NOT NULL,
    kis_order_id       TEXT,
    submitted_at_utc   TEXT,
    final_state_at_utc TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_state  ON orders(state);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_rule   ON orders(rule_id);

------------------------------------------------------------
-- order_state_history (append-only)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_state_history (
    seq                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_correlation_id TEXT NOT NULL,
    from_state           TEXT,
    to_state             TEXT NOT NULL,
    ts_utc               TEXT NOT NULL,
    reason               TEXT
);

CREATE INDEX IF NOT EXISTS idx_order_history_corr ON order_state_history(order_correlation_id);

CREATE TRIGGER IF NOT EXISTS order_state_history_no_update
BEFORE UPDATE ON order_state_history
BEGIN
    SELECT RAISE(ABORT, 'order_state_history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS order_state_history_no_delete
BEFORE DELETE ON order_state_history
BEGIN
    SELECT RAISE(ABORT, 'order_state_history is append-only');
END;

------------------------------------------------------------
-- fills (append-only)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fills (
    seq                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_correlation_id TEXT NOT NULL,
    kis_fill_id          TEXT NOT NULL UNIQUE,
    qty                  INTEGER NOT NULL CHECK (qty > 0),
    price_usd            TEXT NOT NULL,
    executed_at_utc      TEXT NOT NULL,
    commission_usd       TEXT
);

CREATE INDEX IF NOT EXISTS idx_fills_corr ON fills(order_correlation_id);

CREATE TRIGGER IF NOT EXISTS fills_no_update
BEFORE UPDATE ON fills
BEGIN
    SELECT RAISE(ABORT, 'fills is append-only');
END;

CREATE TRIGGER IF NOT EXISTS fills_no_delete
BEFORE DELETE ON fills
BEGIN
    SELECT RAISE(ABORT, 'fills is append-only');
END;

------------------------------------------------------------
-- price_bars (insert-or-skip; "first write wins, log discrepancy")
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_bars (
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    bar_open_utc    TEXT NOT NULL,
    o               TEXT NOT NULL,
    h               TEXT NOT NULL,
    l               TEXT NOT NULL,
    c               TEXT NOT NULL,
    volume          INTEGER NOT NULL,
    ingested_at_utc TEXT NOT NULL,
    PRIMARY KEY (symbol, timeframe, bar_open_utc)
);

------------------------------------------------------------
-- current_positions (derived cache; reproducible from fills)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS current_positions (
    symbol           TEXT PRIMARY KEY,
    qty              INTEGER NOT NULL,
    avg_cost_usd     TEXT NOT NULL,
    last_updated_utc TEXT NOT NULL
);

------------------------------------------------------------
-- reconciliation_runs (mutable: started -> finished)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reconciliation_runs (
    seq                   INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at_utc        TEXT NOT NULL,
    finished_at_utc       TEXT,
    result                TEXT CHECK (result IN ('OK','MISMATCH','INCONCLUSIVE')),
    mismatch_payload_json TEXT
);

------------------------------------------------------------
-- strategy_stage_history (append-only)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_stage_history (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id    TEXT NOT NULL,
    from_stage TEXT,
    to_stage   TEXT NOT NULL,
    reason     TEXT,
    ts_utc     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stage_history_rule ON strategy_stage_history(rule_id);

CREATE TRIGGER IF NOT EXISTS strategy_stage_history_no_update
BEFORE UPDATE ON strategy_stage_history
BEGIN
    SELECT RAISE(ABORT, 'strategy_stage_history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS strategy_stage_history_no_delete
BEFORE DELETE ON strategy_stage_history
BEGIN
    SELECT RAISE(ABORT, 'strategy_stage_history is append-only');
END;
