# Quickstart: Options Selection and Objective Repair

## Focused validation

```bash
uv run pytest \
  tests/unit/test_options_variance_risk_premium_factory.py \
  tests/integration/test_options_variance_risk_premium_factory_probe.py
```

## Production probe

```bash
uv run python scripts/options_variance_risk_premium_factory_probe.py \
  --wput-file /tmp/WPUT_History.csv \
  --macro-data-dir /tmp/strategy-factory-data \
  --prior-factory-json /tmp/prior-factory.json \
  --calibration-json /tmp/calibration.json \
  --controls-json /tmp/controls.json \
  --json-out /tmp/options-selection-objective-repair/options-variance-risk-premium-latest.json
```

## Contract checks

```bash
jq '.selection_repair.protocol.independent_index_used_for_selection == false' \
  /tmp/options-selection-objective-repair/options-variance-risk-premium-latest.json
jq '[.research_canary_eligible, .paper_lane_eligible, .promotion_eligible] | all(. == false)' \
  /tmp/options-selection-objective-repair/options-variance-risk-premium-latest.json
```

## Repository validation

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```
