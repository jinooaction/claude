# Quickstart: Submission Unknown Broker Lookup

## Focused Regression

```bash
uv run pytest tests/integration/test_fill_sync.py -q -k "submission_unknown or full_fill_recorded or idempotent_resync"
```

## Adjacent Checks

```bash
uv run pytest tests/integration/test_fill_sync.py tests/unit/test_execution_state.py tests/unit/test_live_order_path.py -q
```

## Full Validation

```bash
uv run pytest -q
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

## Safety Boundary Check

```bash
git diff --name-only origin/main...HEAD | rg 'automation/.*\.request|deploy/.*portfolio|whitelist|caps|constitution|kernel' && exit 1 || true
rg -n "place_order|cancel_order|order-rvsecncl" src/auto_invest/execution src/auto_invest/broker tests/unit/test_live_order_path.py
```

