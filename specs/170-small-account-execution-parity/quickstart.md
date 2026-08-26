# Quickstart: Small-Account Execution Parity

## Local No-Order Checks

```bash
uv run pytest tests/integration/test_canary_portfolio_cli.py tests/unit/test_execution_proxy_parity.py
uv run pytest tests/unit/test_capital_ladder.py tests/unit/test_live_entry_revalidation.py
uv run ruff check src tests
```

## Production Read-Only Checks

```bash
observe execution-proxy-parity
observe exploration-canary
observe account-nav
observe live-canary-preview <10-percent-nav>
```

All commands above use market data, stored bars, or account reads. None is allowed to place an order.

