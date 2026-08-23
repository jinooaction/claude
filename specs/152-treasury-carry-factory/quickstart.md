# Quickstart: Independent Treasury Carry Factory

## Local no-order validation

```bash
uv run auto-invest collect-public-data \
  --config deploy/public-data.toml \
  --out-dir /tmp/public-data \
  --json

uv run python scripts/treasury_carry_factory_probe.py \
  --macro-data-dir /tmp/public-data \
  --prior-factory-json /tmp/prior_strategy_factory.json \
  --prior-ledger /tmp/prior_trial_ledger.jsonl \
  --code-commit "$(git rev-parse HEAD)" \
  --json-out /tmp/treasury_strategy_factory.json \
  --summary-out /tmp/TREASURY_LAST_RUN.md
```

Expected safety result: the command may publish `FACTORY_EDGE` or `NO_FACTORY_EDGE`, but it makes
zero broker calls, orders, fills, capital changes, whitelist changes, or live-mode changes.

## Verification

```bash
uv run pytest tests/unit/test_treasury_carry_factory.py \
  tests/integration/test_treasury_carry_factory_probe.py
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
git diff --check
```

## Production evidence

After merge, run the public-data and autonomous-strategy-factory workflows, then confirm:

- all five yields are fresh and valid;
- current trials are 64 and cumulative trials are 576;
- every fingerprint is unique;
- no failed gate is hidden;
- no-order KIS smoke still reports zero recent/open orders;
- money-path remains preview-only unless a separate fully gated promotion occurred.
