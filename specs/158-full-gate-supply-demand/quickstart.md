# Quickstart

1. Run focused tests: `uv run pytest -q tests/unit/test_real_world_gate_controls.py tests/unit/test_commodity_supply_demand_factory.py tests/unit/test_autonomous_strategy_factory_workflow.py`.
2. Run the no-order probe with official sources and the spec-157 sidecar as prior evidence.
3. Confirm full positive/null controls, 16 candidates, 704 unique records, untouched holdout, and all failed gates.
4. Run full pytest, ruff, YAML, strict harness, HANDOFF fact check, and PR quality gate.
5. Merge only on clean gates; then verify deploy, production replay, KIS recent/open orders both zero, and money/capital paths.
