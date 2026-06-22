# Quickstart: Micro GTAA Live Canary

## 1. Confirm Default Safety

```bash
uv run pytest tests/unit/test_micro_gtaa_canary.py tests/unit/test_canary_portfolio_config.py
```

Expected:
- The 2026-06-22 operator-approved sentinel is `armed: true`.
- `capital_usd` is no more than `1000`.
- The micro portfolio is limited to `SPYM`, `IEF`, `GLDM`.

## 2. Preview Without Real Orders

Push-triggered merges still preview only, even when the sentinel is armed.

Expected:
- The workflow publishes `automation/rebalance-micro-gtaa-last-run`.
- The live step is skipped on `push`.
- The preview section shows planned orders or a clear reason no order is planned.

## 3. Arm for a Micro Live Run

Only after reviewing the preview:

```yaml
armed: true
capital_usd: 1000
```

Expected:
- A push-triggered arming run still previews only.
- The next scheduled or manual-dispatch run can submit real limit orders only if
  the pre-live circuit breaker is clear and all order guards pass.

## 4. Stop Further Real Orders

Set:

```yaml
armed: false
```

Expected:
- Future runs become preview-only.
- Existing audit history and sidecar records remain intact.

If the pre-live breaker trips, `data/halt.flag` is set on the live instance and
the live order step fails before submitting new orders.

## 5. Validation Before Merge

```bash
uv run pytest tests/unit/test_micro_gtaa_canary.py tests/unit/test_canary_portfolio_config.py
uv run pytest
uv run ruff check src tests
```
