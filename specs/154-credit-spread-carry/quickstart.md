# Quickstart: Independent Credit Spread Carry

```bash
uv run auto-invest collect-public-data --config deploy/public-data.toml --out-dir /tmp/public-data --json
uv run python scripts/edge_gate_calibration_probe.py --seed 60000 --repetitions 500 --code-commit local --json-out /tmp/calibration.json
uv run python scripts/credit_spread_factory_probe.py \
  --macro-data-dir /tmp/public-data \
  --prior-factory-json /tmp/treasury_factory.json \
  --macro-factory-json /tmp/macro_factory.json \
  --prior-ledger /tmp/trial_ledger.jsonl \
  --calibration-json /tmp/calibration.json \
  --code-commit local --json
```

Expected safety properties:

- Exactly 64 current candidates, 640 global audit trials, and 64 family trials.
- A fixed development winner and no holdout reselection.
- Failure emits no selected candidate or deploy config.
- A pass remains research-only because the active whitelist is unchanged.
