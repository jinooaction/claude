# Quickstart: Family Complete V3 and Fundability

```bash
uv run pytest -q \
  tests/unit/test_factory_evidence.py \
  tests/unit/test_fundability.py \
  tests/unit/test_capital_ladder.py \
  tests/unit/test_live_entry_revalidation.py \
  tests/unit/test_forward_edge_autoarm_workflow.py \
  tests/unit/test_live_entry_revalidation_workflow.py

uv run python scripts/factory_evidence_gate.py \
  --evidence /tmp/strategy_factory.json \
  --json-out /tmp/factory_evidence_v3.json

uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

The production check is read-only: rerun the strategy factory, then the capital ladder and live
preview sidecars. A correct current result remains disarmed and reports exact v3/fundability failures.
