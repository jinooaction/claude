# Contract: run artifact directory `data/backtests/<run_id>/`

**Spec**: [../spec.md](../spec.md) (FR-B13, User Story 4) · **Plan**: [../plan.md](../plan.md) · **Date**: 2026-05-07

Every backtest produces exactly one directory under `data/backtests/<run_id>/`. The directory is the on-disk source of truth for spec 007's canary harness and for operator forensic review. It is written atomically (temp dir + rename) after `BACKTEST_COMPLETED` is appended to the audit log.

## Directory layout

```text
data/backtests/<run_id>/
├── manifest.json        # inputs + hashes
├── report.json          # headline metrics + verdict
├── daily.csv            # per-day equity / return / drawdown / exposure
├── fills.csv            # per-fill ledger
└── audit-events.json    # subset of audit_log rows scoped to this run
```

All JSON files are UTF-8, sorted-keys, indent=2, with a trailing newline. CSVs follow RFC 4180 with `\n` line endings.

## Atomicity contract

1. The engine writes to `data/backtests/.tmp-<run_id>/` first.
2. Each file is `fsync`ed before the directory is renamed.
3. The final `os.rename(.tmp-<run_id>, <run_id>)` is the atomic visibility step.

On crash mid-write, the temp directory is left behind and is cleaned up on the next successful run (the cleanup path checks for stale `.tmp-*` siblings).

## File-by-file schemas

### `manifest.json`

```json
{
  "schema_version": 1,
  "run_id": "<uuidv5>",
  "code_sha": "<sha>" or "<sha>+dirty",
  "dataset_hash": "<sha256>",
  "rules_hash": "<sha256>",
  "caps_hash": "<sha256>",
  "whitelist_hash": "<sha256>",
  "seed": 0,
  "vendor": "yfinance",
  "window": {"kind": "window", "start": "2024-01-02", "end": "2024-12-31"},
  "symbols": ["AAPL", "MSFT"],
  "opening_cash_usd": "100000.00",
  "slippage_bps_market": 5,
  "risk_free_rate_annual": "0",
  "warmup_bars": 50,
  "verdict_thresholds": {
    "total_return_pct_min": "0",
    "max_drawdown_pct_max": "10",
    "sharpe_min": "0.5"
  },
  "ohlcv_bars_consumed": 12580,
  "ohlcv_per_symbol_hash": {
    "AAPL": "<sha256>",
    "MSFT": "<sha256>"
  },
  "start_ts_utc": "2026-05-07T18:46:43Z",
  "end_ts_utc": "2026-05-07T18:46:51Z",
  "dirty": false
}
```

**FR-B12 byte-identity excludes**: `start_ts_utc`, `end_ts_utc`, `dirty`. Everything else is deterministic.

### `report.json`

```json
{
  "schema_version": 1,
  "run_id": "<uuidv5>",
  "total_return_pct": "12.34",
  "max_drawdown_pct": "4.21",
  "sharpe_annualised": "0.83",
  "risk_free_rate_annual": "0",
  "fills_count_total": 127,
  "gate_rejections_total": 3,
  "per_rule_pnl_usd": {
    "rule_a": "1234.56",
    "rule_b": "-12.45"
  },
  "per_rule_fills_count": {
    "rule_a": 47,
    "rule_b": 3
  },
  "bankruptcy_at": null,
  "verdict": {
    "promote_eligible": true,
    "reasons": [
      "total_return_pct 12.34 ≥ 0",
      "max_drawdown_pct 4.21 ≤ 10",
      "sharpe_annualised 0.83 ≥ 0.5"
    ]
  }
}
```

If `bankruptcy_at` is non-null, `sharpe_annualised` is `null` and `verdict.promote_eligible` is `false`.

### `daily.csv`

RFC 4180. UTF-8. `\n` line endings. Columns:

```text
date,cash_usd,equity_usd,daily_return_pct,cumulative_return_pct,drawdown_pct,gate_rejections,fills_count,per_symbol_exposure_pct_json
```

- `date` is ISO 8601 (`YYYY-MM-DD`).
- All numerics are stringified Decimal (e.g. `"100000.00"`); no float scientific notation, no locale-specific thousands separators.
- `per_symbol_exposure_pct_json` is a JSON object, double-quoted with embedded `"` doubled per RFC 4180. Keys sorted ascending.
- Rows sorted ascending by `date`. Header is line 1.

### `fills.csv`

RFC 4180. Columns mirror the in-memory `SimulatedFill` model:

```text
seq,bar_date,symbol,rule_id,side,order_type,requested_qty,gate_decision,gate_reason,fill_qty,fill_price_usd,fill_model_branch,slippage_bps_applied,cash_usd_after,position_qty_after
```

- `seq` starts at 1, monotonic per run.
- `gate_reason` is empty string when `gate_decision == "allow"`.
- `fill_qty == 0` when `gate_decision == "reject"` or the bar didn't straddle the limit.
- Rows sorted ascending by `seq`.

### `audit-events.json`

```json
[
  {
    "seq_id": 12891,
    "ts_utc": "2026-05-07T18:46:43Z",
    "event_type": "BACKTEST_STARTED",
    "payload": {
      "run_id": "<uuidv5>",
      "code_sha": "<sha>",
      "dataset_hash": "<sha256>",
      "rules_hash": "<sha256>",
      "caps_hash": "<sha256>",
      "whitelist_hash": "<sha256>",
      "seed": 0,
      "vendor": "yfinance",
      "window_start": "2024-01-02",
      "window_end": "2024-12-31",
      "named_dataset": null
    }
  },
  {
    "seq_id": 12892,
    "ts_utc": "2026-05-07T18:46:51Z",
    "event_type": "BACKTEST_COMPLETED",
    "payload": {
      "run_id": "<uuidv5>",
      "total_return_pct": "12.34",
      "max_drawdown_pct": "4.21",
      "sharpe": "0.83",
      "fills_count": 127,
      "gate_rejections_count": 3,
      "promote_eligible": true,
      "artifact_dir": "data/backtests/<run_id>"
    }
  }
]
```

This file is built from `audit_log` rows whose `payload.run_id == <run_id>`. It is a **convenience copy**; the canonical record is the SQLite table.

## Reproducibility contract (FR-B12, SC-B03, SC-C04)

For two runs `R1`, `R2` with identical:

- `code_sha` (excluding the `+dirty` suffix)
- `dataset_hash`
- `rules_hash`
- `caps_hash`
- `whitelist_hash`
- `seed`

The following files MUST be byte-identical:

| File | Identity |
|------|----------|
| `manifest.json` | identical except for `start_ts_utc`, `end_ts_utc`, `dirty` |
| `report.json` | byte-identical |
| `daily.csv` | byte-identical |
| `fills.csv` | byte-identical |
| `audit-events.json` | identical except for `seq_id`, `ts_utc` per row |

This is what spec 007 SC-C04 ultimately rests on.

## Cleanup

The engine never deletes a run directory. Operator runs `auto-invest backtest prune --older-than <days>` (CLI subcommand, future scope) for retention. v1 emits a warning when total `data/backtests/` exceeds 1 GB; that warning is operator-actionable, not engine-actionable.
