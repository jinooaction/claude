# Quickstart: KIS Order Diagnostics

## 1. Validate KIS Payload and Diagnostics

```bash
uv run pytest tests/integration/test_broker_order_diagnostics.py
```

Expected:
- Normal buy and sell order bodies include the KIS sample fields.
- HTTP error diagnostics preserve KIS response fields.
- Account and credential material is masked.

## 2. Validate Micro Workflow Gates

```bash
uv run pytest tests/unit/test_micro_gtaa_canary.py
```

Expected:
- The micro live step is still disabled on push.
- The preflight step runs before circuit breaker and live order.
- Live order requires `steps.preflight.outputs.ok == 'true'`.
- Sidecar output includes preflight evidence.

## 3. Full Repository Gates

```bash
uv run pytest
uv run ruff check src tests
```

Expected:
- All tests and lint pass before PR merge.

## 4. Operational Reading After the Next Run

Check the sidecar:

```bash
git fetch origin automation/rebalance-micro-gtaa-last-run
git show origin/automation/rebalance-micro-gtaa-last-run:LAST_RUN.md
```

Expected:
- `라이브 전 주문 전제 확인` shows session and cash status.
- If live orders are skipped, the skip reason identifies session, cash, event, or missing evidence.
- If KIS rejects an order, live result rows include structured broker diagnostics instead of only an HTTP status string.

## 5. Explicit Non-Goal

Do not manually dispatch a live retry as part of this feature. The goal is to restore precondition checks and evidence capture first.
