# Quickstart: USDA Crop Supply-Demand Factory

```bash
uv run pytest -q tests/unit/test_usda_crop_supply_demand_factory.py \
  tests/integration/test_usda_crop_supply_demand_factory_probe.py \
  tests/integration/test_strategy_factory_workflow.py

uv run python scripts/usda_crop_supply_demand_factory_probe.py \
  --macro-data-dir /tmp/public-data \
  --prior-factory-json /tmp/commodity_supply_demand_factory.json \
  --calibration-json /tmp/edge_gate_calibration.json \
  --controls-json /tmp/full_gate_controls.json \
  --code-commit "$(git rev-parse HEAD)" \
  --json-out /tmp/strategy_factory.json \
  --summary-out /tmp/USDA_LAST_RUN.md
```

Before accepting the result, verify 16 complete trials, 720 unique audit records, at least 120 holdout months, unchanged threshold rows, no broker/order imports, and explicit live-parity status.
