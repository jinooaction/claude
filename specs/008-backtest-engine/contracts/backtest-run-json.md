# Contract — `backtest-run.json` Schema

The top-level artefact written under `data/backtest/<run_id>/backtest-run.json`.
Spec 007's hardened-canary verifier reads this file as one of its inputs.

## Schema

```json
{
  "run_id": "0193b8c4-7e1a-7b3c-8f4d-...",
  "invoker": "cli",
  "ruleset_path": "/abs/path/rules.toml",
  "ruleset_sha256": "3f1e9b...",
  "dataset_version": "7a8d2c...",
  "date_start": "2024-05-13",
  "date_end": "2025-05-13",
  "replay_seed": 0,
  "fill_model": "pessimistic_zero_slip",
  "judgment_mode": "stub",
  "synthetic_shock": false,
  "start_ts": "2026-05-13T14:32:01.123Z",
  "end_ts": "2026-05-13T14:34:17.882Z",
  "status": "completed",
  "summary": {
    "aggregate_return_pct": "3.142500",
    "aggregate_max_drawdown_pct": "1.870000",
    "aggregate_sharpe": "0.812000",
    "total_orders": 47,
    "total_fills": 41,
    "total_gate_rejections": 6,
    "data_quality_warnings": [],
    "per_rule": [
      {
        "rule_id": "buy_spy_open_below_50d",
        "symbol": "SPY",
        "total_return_pct": "2.140000",
        "max_drawdown_pct": "1.110000",
        "sharpe_ratio": "0.640000",
        "order_count": 12,
        "fill_count": 11,
        "gate_rejection_count_by_gate": {"per_trade_cap": 1},
        "notional_traded_usd": "55432.180000",
        "slippage_assumption": "zero"
      },
      ...
    ]
  },
  "kernel_guard_report": {
    "touched": false,
    "checked_paths": [".specify/memory/kernel.toml", "src/auto_invest/risk/gates.py", "..."],
    "manifest_sha256": "<hex64 of kernel.toml at run start>"
  }
}
```

## Field-level invariants

| Field | Volatility | Determinism contract |
|-------|------------|---------------------|
| `run_id` | volatile | excluded from byte-identical check (FR-B15) |
| `start_ts` | volatile | excluded |
| `end_ts` | volatile | excluded |
| `ruleset_sha256` | stable per ruleset content | included (a different ruleset MUST hash differently) |
| `dataset_version` | stable per ingest content | included |
| `fill_model` | locked literal | included |
| `judgment_mode` | locked literal | included |
| `summary.*` | stable for same inputs | INCLUDED — byte-identical across runs |
| `kernel_guard_report.manifest_sha256` | stable for same kernel.toml | included |

## Decimal serialisation

All monetary / pct values are JSON strings (not numbers) to preserve decimal precision and avoid float drift across machines. Format: fixed 6 decimal places with trailing zeros. Examples: `"3.142500"`, `"-0.012000"`, `"1000.000000"`. Implementation MUST use Python `Decimal.quantize(Decimal("0.000001"))` and `str()`, NOT `f"{x:.6f}"` (which can round differently for half-to-even).

## `kernel_guard_report` block

`backtest-run.json` is the operator's single forensic artefact for "what state was the repo in when this ran". Its `kernel_guard_report` block records:

- `touched`: whether any Kernel path had uncommitted modifications at run start. If `true`, the run is rejected (exit 78) and `summary` is null — but the JSON is still written so the operator can see why.
- `checked_paths`: the full list of paths checked against the manifest.
- `manifest_sha256`: the hash of `.specify/memory/kernel.toml` AT THE TIME OF THE RUN. This pins the run to a specific kernel-perimeter snapshot, so future kernel changes do not retroactively invalidate forensic claims.

## Spec-007 consumption

Spec 007's canary verifier:

1. Loads two `backtest-run.json` files (baseline + candidate).
2. Asserts that `dataset_version`, `fill_model`, `judgment_mode`, `replay_seed`, `synthetic_shock`, `date_start`, `date_end` all match.
3. Compares `summary.aggregate_*` and `summary.per_rule[*]` against the canary's metric bands.
4. Asserts `kernel_guard_report.touched == false` for both.

The byte-identical-determinism check (FR-B15 / SC-B02) runs separately on `metrics.csv` and `per-rule/*.json` (not on this top-level file, because its volatile fields are expected to differ).
