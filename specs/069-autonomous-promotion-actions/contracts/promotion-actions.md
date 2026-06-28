# Contract: Promotion Actions

## CLI

```bash
uv run auto-invest promotion-actions \
  --promotion-summary /tmp/promotion_summary.json \
  --forward-registry automation/promotion-forward-registry.json \
  --canary-submissions automation/promotion-canary-submissions.json \
  --summary-out /tmp/LAST_RUN.md \
  --json-out /tmp/promotion_actions.json \
  --forward-registry-out /tmp/promotion-forward-registry.json \
  --canary-submissions-out /tmp/promotion-canary-submissions.json
```

## Probe

```bash
uv run python scripts/promotion_action_probe.py \
  --promotion-summary /tmp/promotion_summary.json \
  --forward-registry automation/promotion-forward-registry.json \
  --canary-submissions automation/promotion-canary-submissions.json \
  --summary-out /tmp/LAST_RUN.md \
  --json-out /tmp/promotion_actions.json \
  --forward-registry-out /tmp/promotion-forward-registry.json \
  --canary-submissions-out /tmp/promotion-canary-submissions.json
```

## Output JSON

```json
{
  "schema_version": "1.0",
  "run_id": "123",
  "commit": "abc123",
  "timestamp_utc": "2026-06-29T00:00:00Z",
  "overall_status": "ok",
  "counts": {
    "registered": 1,
    "submitted": 1,
    "blocked": 0,
    "reported": 0
  },
  "actions": [],
  "blocked": []
}
```

## Safety Contract

- The command must not call broker APIs.
- The action workflow must not use SSH or KIS secrets.
- Promotion forward workflow may use server SSH but every rebalance command must be `--mode paper`.
- Promotion canary workflow may run `canary-portfolio` but must not edit `rebalance-live.request`, live strategy config, or capital ladder sentinel files.
- No workflow in this feature may contain `--mode live` or `--confirm-live`.
