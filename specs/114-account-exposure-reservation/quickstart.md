# Quickstart: Account Exposure Reservation

## Focused Red Tests

```bash
uv run pytest tests/integration/test_order_router.py::test_submit_order_counts_open_buy_orders_as_reserved_global_exposure -q
uv run pytest tests/integration/test_spec_032_live_rebalancer.py::test_rebalance_reserves_successful_buys_before_next_buy -q
```

## Focused Green Tests

```bash
uv run pytest tests/integration/test_order_router.py tests/integration/test_spec_032_live_rebalancer.py -q
```

## Full Validation

```bash
uv run pytest -q
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

## Safety Confirmation

- Confirm no live sentinel file is armed.
- Confirm no KIS order workflow is dispatched.
- Confirm PR text states this is a K1 safety contraction, not a live-money action.
