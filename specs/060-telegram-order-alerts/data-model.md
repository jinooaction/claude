# Data Model: Telegram Order Alerts

## TelegramAlertConfig

- `bot_token`: runtime secret used only for Telegram API calls. Must be registered for log redaction.
- `chat_id`: runtime destination id. Treated as sensitive operational metadata and never committed.
- `enabled`: derived boolean. False when required values are missing or `TELEGRAM_ENABLED=false`.
- `source_label`: short label used in messages, default `auto-invest`.
- `timeout_seconds`: per HTTP request timeout.
- `max_retries`: bounded retry count for one send.

Validation:

- Missing token/chat id disables sending unless a command explicitly requires delivery.
- Token is never printed in logs or messages.
- Retry count is bounded and non-negative.

## AuditAlertCursor

- `last_seq`: largest audit_log seq successfully processed or intentionally skipped.
- `updated_at_utc`: timestamp of cursor write.

Validation:

- Missing cursor defaults to current max seq unless replay is explicitly requested.
- Cursor writes are atomic replace operations.

## OrderAlertEvent

- `seq`
- `ts_utc`
- `event_type`
- `rule_id`
- `symbol`
- `correlation_id`
- `payload`
- `message`

Validation:

- Only configured event types are emitted.
- Payload is sanitized before formatting.
- Message is truncated before send.

## MicroWorkflowAlert

- `run_id`
- `event`
- `armed`
- `capital_usd`
- `preflight_status`
- `live_outcome`
- `order_summary`
- `run_url`

Validation:

- If secrets are absent, no send is attempted.
- If send fails, workflow still exits successfully.
