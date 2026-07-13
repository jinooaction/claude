# Quickstart: Degraded Execution State

Focused red/green checks:

```bash
uv run pytest tests/unit/test_execution_state.py -q
uv run pytest tests/integration/test_order_router.py::test_submit_order_blocks_buy_when_execution_state_degraded -q
uv run pytest tests/integration/test_order_router.py::test_submit_order_allows_sell_when_execution_state_degraded -q
uv run pytest tests/integration/test_worker_fill_sync.py::test_fill_sync_failure_blocks_new_buy_before_broker_submission -q
uv run pytest tests/integration/test_worker_capital_tracking.py::test_nav_fetch_failure_blocks_new_buy_before_broker_submission -q
```

Full validation:

```bash
uv run pytest -q
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

Safety diff check:

```bash
git diff --name-only origin/main...HEAD | rg 'automation/.*\.request|whitelist|caps|constitution|kernel' && exit 1 || true
```
