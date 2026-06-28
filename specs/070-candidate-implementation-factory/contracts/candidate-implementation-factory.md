# Contract: Candidate Implementation Factory

## CLI

```bash
uv run auto-invest candidate-factory \
  --candidate-backlog /tmp/candidate_backlog.json \
  --promotion-summary /tmp/promotion_summary.json \
  --result-evidence /tmp/candidate_results.json \
  --summary-out /tmp/LAST_RUN.md \
  --json-out /tmp/candidate_factory.json \
  --enriched-backlog-out /tmp/candidate_backlog.enriched.json \
  --package-plan-out /tmp/candidate_packages.json \
  --run-id local
```

## Result Evidence JSON

```json
{
  "schema_version": "1.0",
  "results": [
    {
      "candidate_id": "candidate-example",
      "historical_backtest": "pass",
      "recent_oos": "pass",
      "walk_forward": "pass",
      "source_ref": "artifact://candidate-example/walk-forward.json",
      "forward_track": {
        "track_key": "example-track",
        "portfolio_path": "deploy/example.toml",
        "db_path": "data/example.db",
        "halt_path": "data/example.halt.flag"
      }
    }
  ]
}
```

## Guarantees

- Missing result evidence cannot create pass fields.
- Every source candidate appears in the enriched backlog.
- The factory does not execute generated commands.
- The factory does not call broker APIs or read secrets.
