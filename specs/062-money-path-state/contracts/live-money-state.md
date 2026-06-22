# Contract: live_money_state

The money-path JSON output MUST contain:

```json
{
  "live_money_state": {
    "status": "REAL_ORDER_PATH_ARMED",
    "can_submit_real_orders": true,
    "path": "micro-gtaa-live-canary",
    "capital_usd": 1000,
    "max_capital_usd": 1000,
    "next_scheduled_live_utc": "2026-06-22T15:00:00Z",
    "required_gates": [
      "non-push workflow event",
      "US regular session",
      "KIS purchasable cash >= planned buys + 1% buffer",
      "micro circuit breaker clear",
      "K1 caps and K2 whitelist"
    ],
    "last_run": {
      "run_id": "27935469561",
      "timestamp_utc": "2026-06-22T07:04:12Z",
      "event": "workflow_dispatch",
      "live_step": "success",
      "preflight_ok": null,
      "preflight_reason": "preflight evidence absent",
      "breaker_reason": "within loss limits",
      "order_states": ["REJECTED_BY_BROKER", "REJECTED_BY_BROKER"],
      "accepted_or_filled_count": 0,
      "broker_rejected_count": 2
    }
  }
}
```

Rules:
- `status=REAL_ORDER_PATH_ARMED` means a non-push execution can attempt real orders after gates pass. It does not mean orders will fill.
- `can_submit_real_orders=false` when `status` is `PREVIEW_ONLY`, `BLOCKED`, or `UNKNOWN`.
- `last_run.live_step=success` is workflow-step success, not broker fill success.
- Missing sidecar sets `last_run` to null while preserving sentinel-derived `status`.
