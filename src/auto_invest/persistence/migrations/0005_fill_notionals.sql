CREATE TABLE IF NOT EXISTS fill_notionals (
    kis_fill_id TEXT PRIMARY KEY REFERENCES fills(kis_fill_id),
    notional_usd TEXT NOT NULL,
    cumulative_qty INTEGER NOT NULL CHECK (cumulative_qty > 0),
    cumulative_avg_price_usd TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS fill_notionals_no_update
BEFORE UPDATE ON fill_notionals BEGIN
    SELECT RAISE(ABORT, 'fill notionals are append-only');
END;
CREATE TRIGGER IF NOT EXISTS fill_notionals_no_delete
BEFORE DELETE ON fill_notionals BEGIN
    SELECT RAISE(ABORT, 'fill notionals are append-only');
END;
