# Quickstart: Research Canary Evidence Parity

## Focused validation

```bash
uv run pytest -q \
  tests/unit/test_factory_evidence.py \
  tests/integration/test_factory_evidence_gate.py \
  tests/unit/test_ladder_decide_cli.py \
  tests/unit/test_live_entry_revalidation.py
```

## Static workflow validation

```bash
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/forward-edge-autoarm.yml", aliases: true)'
uv run python -m py_compile scripts/factory_evidence_gate.py
git diff --check
```

## Production acceptance

1. Deploy the merged commit.
2. Refresh the strategy factory sidecar.
3. Run the capital ladder gate.
4. With the current `NO_FACTORY_EDGE`, verify `WAIT_EDGE`, rung `0 -> 0`, no sentinel change, no PR, and zero orders.
5. Confirm first-entry revalidation and money-path reports consume the same completeness result.
