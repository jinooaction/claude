# Quickstart: Order Submission Uncertainty Recovery

## Focused Checks

```bash
uv run pytest \
  tests/integration/test_broker_client.py \
  tests/integration/test_broker_order_diagnostics.py \
  tests/integration/test_order_router.py \
  tests/unit/test_audit.py \
  tests/unit/test_telegram_alerts.py
```

## Full Gates

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
python3 scripts/check_pr_quality_gate.py /tmp/pr-body-112.md
```

## Manual Search

```bash
rg -n "retry=False|retry_transient|SUBMISSION_UNKNOWN|ORDER_SUBMISSION_UNKNOWN|ORDER_REJECTED_BY_BROKER" src tests specs/112-order-submission-uncertainty-recovery
rg -n "automation/(rebalance-live|rebalance-micro-gtaa|go-live-canary)|armed: true|global_exposure_pct|per_trade_pct" .
```

## Expected Behavior

- `GET` transient failures still retry.
- 신규 주문 `POST` transient failures do not retry.
- 5xx and transport failures become `SUBMISSION_UNKNOWN`.
- Explicit KIS business rejection remains `REJECTED_BY_BROKER`.
- No real broker, SSH, Anthropic, Telegram, or paid external service call occurs.
