# Quickstart: Broad Frontier Expansion NO_EDGE Refresh

## Focused Validation

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -k "broad_no_edge or all_released_no_edge"
```

## Full Validation

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

## Expected Result

After first-wave broad no-edge candidates are released, autonomous-work selects `candidate-broad-no-edge-cross-asset-relative-value-experiment` instead of a new broad parent candidate.
