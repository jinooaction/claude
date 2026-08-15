# Quickstart: Profit Evidence Engine

## Focused Tests

```bash
uv run pytest \
  tests/unit/test_profit_evidence_engine.py \
  tests/integration/test_profit_evidence_engine_probe.py \
  tests/unit/test_candidate_result_executor.py \
  tests/unit/test_candidate_history_support.py -q
```

## Real Public-Data Replay

```bash
git show origin/automation/rebalance-paper-forward-last-run:leaderboard.json \
  > /tmp/profit-engine-leaderboard.json

uv run python scripts/profit_evidence_engine_probe.py \
  --leaderboard /tmp/profit-engine-leaderboard.json \
  --json-out /tmp/profit-evidence.json \
  --json
```

Expected current shape:

- `trial_count=12`
- `split.overlap_months=0`
- selected allocation is expected to be `three_asset_fixed` from development evidence
- historical verdict may be `HOLDOUT_EDGE`
- overall status remains `FORWARD_VALIDATION` while `globalfixed` forward PSR is below 0.95
- no broker, order, capital, live strategy, whitelist/caps, or secret mutation

## Mixed Evidence Replay

Run the candidate-result unit case where deep history passes and recent portfolio walk-forward fails. The expected result is:

```json
{
  "status": "pending",
  "historical_backtest": "pass",
  "recent_oos": "fail",
  "walk_forward": "fail"
}
```
