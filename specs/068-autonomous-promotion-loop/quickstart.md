# Quickstart: Autonomous Promotion Loop

## Local Fixture Run

```bash
uv run python scripts/promotion_loop_probe.py \
  --evidence-dir tests/fixtures/promotion_loop/fresh \
  --json
```

Expected:

- JSON contains `assessments`.
- Candidates with only source backlog evidence are `BACKTEST_REQUIRED`.
- Backtest-only candidates do not become `CANARY_CANDIDATE`.

## Write Sidecar Artifacts Locally

```bash
tmpdir=$(mktemp -d)
uv run python scripts/promotion_loop_probe.py \
  --evidence-dir tests/fixtures/promotion_loop/fresh \
  --summary-out "$tmpdir/LAST_RUN.md" \
  --json-out "$tmpdir/promotion_summary.json" \
  --queue-out "$tmpdir/promotion_queue.json"
```

## Safety Check

The command must not require KIS secrets, SSH credentials, or broker access. It must not write `automation/rebalance-live.request`, portfolio TOML, caps, whitelist, or live strategy files.
