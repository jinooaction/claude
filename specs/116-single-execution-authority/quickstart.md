# Quickstart: Single Execution Authority

1. Run focused red tests:

```bash
uv run pytest tests/unit/test_execution_authority.py tests/unit/test_live_order_path.py tests/integration/test_order_router.py::test_submit_order_rejected_when_execution_authority_locked tests/integration/test_worker_order_lifecycle.py::test_ttl_cancel_respects_execution_authority_lock -q
```

2. Implement authority and rerun focused tests.

3. Run adjacent suites:

```bash
uv run pytest tests/integration/test_order_router.py tests/integration/test_worker_order_lifecycle.py tests/integration/test_spec_032_live_rebalancer.py -q
```

4. Run full validation:

```bash
uv run pytest -q
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
