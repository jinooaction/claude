# Contract: `auto-invest efficiency` CLI

## Synopsis

```
auto-invest efficiency [--window <duration>] [--as-of <YYYY-MM-DD>] [--db <path>] [--prices <path>] [--thresholds <path>]
```

## Options

| flag | default | meaning |
|------|---------|---------|
| `--window` | `7d` | window size; supports `Nd` (days) or `Nh` (hours) |
| `--as-of` | now (UTC) | window end (exclusive); window start = `as_of - window` |
| `--db` | `data/auto_invest.db` | SQLite path |
| `--prices` | `config/llm_prices.toml` | price-table path |
| `--thresholds` | `config/llm_kpi_thresholds.toml` | tier-table path |

## Output

Emits a single JSON document on stdout. Exit code: 0 on success, 2 on configuration error, 1 on unexpected runtime error.

```jsonc
{
  "window_start_utc": "2026-04-29T00:00:00.000Z",
  "window_end_utc":   "2026-05-06T00:00:00.000Z",
  "call_count": 42,
  "kpis": [
    {
      "name": "cache_hit_rate",
      "value": 0.83,
      "tier": "B",
      "direction": "higher_is_better",
      "threshold_used": {"tier_c": 0.40, "tier_b": 0.70, "tier_a": 0.90}
    },
    {
      "name": "tokens_per_decision_p95",
      "value": 2310,
      "tier": "B",
      "direction": "lower_is_better",
      "threshold_used": {"tier_c": 8000, "tier_b": 3000, "tier_a": 1500}
    }
    // ... one entry per declared KPI
  ],
  "per_decision_class": {
    "(unclassified)": {"count": 3, "tokens_total": 4200, "cost_usd": "0.012345", "p95_tokens": 1800},
    "news_screen":    {"count": 39, "tokens_total": 88_400, "cost_usd": "0.245678", "p95_tokens": 2400}
  },
  "top_n_calls": [
    {"seq": 1024, "ts_utc": "2026-05-05T13:01:22.451Z", "model": "claude-opus-4-7",
     "decision_class": "news_screen", "tokens_total": 14200, "cost_usd": "0.214000"}
    // ... up to 5 entries by cost_usd descending
  ]
}
```

## Empty-window behavior

When the window contains zero rows, `call_count` is 0, every KPI reports `value = 0` and `tier = "N/A"`, `per_decision_class` is `{}`, `top_n_calls` is `[]`. Exit code 0 (not an error).

## Stability

The output is byte-stable for the same input data plus `--as-of` value (SC-T04). JSON keys are emitted in sorted order; floats are formatted via `Decimal.quantize` to avoid `1.0` vs `1` drift.
