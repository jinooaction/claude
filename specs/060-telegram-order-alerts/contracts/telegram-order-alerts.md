# Contracts: Telegram Order Alerts

## Runtime Environment

### GitHub Actions micro GTAA notification

Optional repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

When either secret is absent or empty, the notification step must log a skip and exit 0.

### Server audit tailer

Optional `/opt/auto-invest/.env` values:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_SOURCE_LABEL=auto-invest
```

## CLI Contract

```bash
auto-invest telegram-alerts \
  --db data/auto_invest.db \
  --env-file .env \
  --state-file data/telegram_alerts_state.json \
  --follow
```

Options:

- `--once`: process one batch and exit.
- `--follow`: poll continuously.
- `--dry-run`: print messages without sending and without requiring Telegram secrets.
- `--replay-existing`: if no state file exists, start from seq 0 instead of current max seq.
- `--test-message`: send or print a test message and exit.
- `--include-paper`: include `ORDER_PAPER_FILLED`; default excludes paper events.

Exit behavior:

- Configuration errors for required non-Telegram inputs exit non-zero.
- Missing Telegram secrets in non-dry-run mode exits non-zero for CLI invocation, but the systemd unit can be disabled until secrets exist.
- Individual Telegram send failures are logged and do not modify order state or audit rows.

## Message Contract

Messages must be plain text and include:

- source label
- event type
- seq and timestamp
- symbol/rule/correlation when present
- event-specific summary
- no unmasked token, app key, app secret, authorization, or full account value

Example:

```text
auto-invest 주문 거부
event=ORDER_REJECTED_BY_BROKER seq=1234 ts=2026-06-22T15:01:02.000Z
symbol=IEF correlation=abc
broker=KIS http=500 msg_cd=APBK... msg=...
```
