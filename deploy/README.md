# auto-invest — systemd install

Operator copy-paste install for the worker + automated deploy timer.
Run as root unless noted otherwise. Substitute `/opt/auto-invest`
with your install path.

## 1. Pre-flight (operator account + paths)

```bash
useradd --system --create-home --home-dir /opt/auto-invest auto-invest
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/data
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/logs
```

Clone the repo into `/opt/auto-invest` (as the `auto-invest` user)
and populate `.env` with KIS credentials per
`specs/001-automated-trading-mvp/quickstart.md`. The `.env` file
must define at least:

```
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ACCOUNT_NUMBER=...
AUTO_INVEST_CAPITAL=10000   # USD; the worker --capital arg
```

Run `uv sync` once as the `auto-invest` user to populate `.venv/`.

## 2. Install the units + timer

> **CI 연결 인스턴스는 보통 수동 설치 불필요.** `deploy-on-merge.yml` 이 매 머지마다
> `deploy/sync-units.sh` 를 서버에서 실행해 유닛을 설치/갱신하고 타이머를 활성화한다
> (워커는 재시작 안 함, 장중에도 안전). 아래 단계는 최초 부트스트랩이나 CI 가 없는
> 호스트를 위한 수동 절차다.

```bash
install -m 0644 /opt/auto-invest/deploy/auto-invest.service /etc/systemd/system/auto-invest.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.timer /etc/systemd/system/auto-invest-deploy.timer
install -m 0644 /opt/auto-invest/deploy/auto-invest-tune.service /etc/systemd/system/auto-invest-tune.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-tune.timer /etc/systemd/system/auto-invest-tune.timer
install -m 0644 /opt/auto-invest/deploy/auto-invest-telegram-alerts.service /etc/systemd/system/auto-invest-telegram-alerts.service

systemctl daemon-reload

# Worker — long-running:
systemctl enable --now auto-invest.service

# Deploy timer — fires every 30 min outside US regular hours:
systemctl enable --now auto-invest-deploy.timer

# Tuner timer — fires once daily at 22:00 UTC (after US close).
# Runs `auto-invest tune --apply` (spec 005 L1 autonomous tuning). Needs
# no KIS keys; fail-safe (no-op) until the worker has created the DB.
systemctl enable --now auto-invest-tune.timer
```

### Optional: Telegram mobile order alerts

Telegram alerts are disabled until the operator provides secrets and enables the service.
The service only reads `audit_log`; it does not submit, cancel, sync, or modify orders.
Telegram's developer API page describes its APIs as free of charge, and this alert path
uses the HTTPS Bot API only for text notifications. No Telegram billing account is required.

Easiest path after adding GitHub repository secrets `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`: run the GitHub Actions workflow
`Configure Telegram alerts on server`. It writes the server `.env`, sends a test
message, and enables only `auto-invest-telegram-alerts.service`.

1. In Telegram, create a bot with `@BotFather` and save the token.
2. Send one message to the bot, then open
   `https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates` to find `chat.id`.
3. Add these lines to `/opt/auto-invest/.env`:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_SOURCE_LABEL=auto-invest
```

4. Validate a mobile test message:

```bash
cd /opt/auto-invest
/usr/local/bin/uv run auto-invest telegram-alerts \
  --env-file .env --db data/auto_invest.db \
  --state-file data/telegram_alerts_state.json --test-message
```

5. Enable the observer:

```bash
systemctl enable --now auto-invest-telegram-alerts.service
```

The observer starts at the current audit seq on a fresh state file. If an
existing state file is stale, it sends only the newest 25 catch-up alerts by
default (`--max-catchup-alerts`) and suppresses identical `ERROR` alerts for
one hour by default (`--error-cooldown-seconds`).

Disable mobile alerts without touching the trading worker:

```bash
systemctl disable --now auto-invest-telegram-alerts.service
```

Without direct server SSH from the local machine, run the manual GitHub Actions
workflow `Manage Telegram alerts on server` with action `status`, `disable`,
`restart`, or `enable`. That workflow controls only
`auto-invest-telegram-alerts.service`.

## 3. Verify

```bash
systemctl status auto-invest.service
journalctl -u auto-invest.service -n 50

systemctl list-timers auto-invest-deploy.timer auto-invest-tune.timer
journalctl -u auto-invest-deploy.service -n 50
journalctl -u auto-invest-tune.service -n 50
journalctl -u auto-invest-telegram-alerts.service -n 50
```

The deploy timer's calendar expression intentionally OMITS hours
`13..20` (US regular session UTC); the deploy runner's
`market_hours_guard` catches edge cases (DST shifts) regardless,
refusing with `DEPLOY_FAILED(phase=market_hours_guard)`.

The tuner timer fires once daily at `22:00` UTC — after the US close
(`20:00` UTC EDT / `21:00` UTC EST) — and runs
`auto-invest tune --apply` (spec 005). Its own `market_hours_guard`
(constitution VIII.A) and minimum-sample gate (constitution X) make
it a no-op inside the session window or on thin data, and it is
idempotent per session date. The only L1 change it ever auto-applies
is tightening a `tier_b` KPI threshold in
`config/llm_kpi_thresholds.toml`, recorded as an `AUTO_TUNED_L1`
audit row (with the prior value, so it is reversible).

## 4. Trigger a deploy manually (ordinary path: off-hours only)

```bash
sudo -u auto-invest systemctl start auto-invest-deploy.service
journalctl -u auto-invest-deploy.service -f
```

The first stdout line is `deploy correlation_id: <hex>`. Use that to
join all rows for one deploy:

```bash
sqlite3 /opt/auto-invest/data/auto_invest.db \
  "SELECT ts_utc, event_type, json_extract(payload_json, '$.phase') AS phase
   FROM audit_log
   WHERE correlation_id = '<id>'
   ORDER BY seq;"
```

GitHub Actions에서 같은 내용을 읽기 전용으로 확인할 때는 수동
`Deploy audit log verification` 워크플로를 사용한다. 이 경로는 임의 원격 셸을 보내지 않고
forced-command gateway의 `deploy-audit [correlation_id]`만 호출한다. 서버 helper는 요청 ID를
다시 검증하고 위 데이터베이스를 `sqlite3 -readonly`로만 조회한다.

### Repository-owner one-shot emergency deploy during XNYS hours

Constitution VIII.A permits one narrow exception to the ordinary off-hours rule.
The repository owner may run `Deploy on merge to main` with
`owner_emergency=true`, the exact current 40-character main SHA, confirmation
`OWNER_EMERGENCY_LIVE_DEPLOY`, and a 12-500 character reason. The workflow issues
a short-lived, single-use request through the fixed `emergency-deploy` SSH
command; there is no arbitrary remote shell and no reusable force switch.

Before code mutation, the root helper appends `DEPLOY_EMERGENCY_AUTHORIZED`,
creates `/run/auto-invest-deploy/live-order-maintenance.lock`, and waits for
live broker writes to quiesce through the shared/exclusive
`/run/auto-invest-deploy/broker-write.lock`. It then stops and verifies the
previous scheduler timer, scheduler service, and long-running worker so the
first deployment is safe even when the old code does not know the new lock.
Only in that quiesced state does the read-only KIS smoke prove
`open_unfilled=0` before code mutation.
All ordinary deploy checks, migrations, the 90-second health gate, and rollback
remain mandatory. The interlock is removed only after `DEPLOY_COMPLETED` or a
verified `DEPLOY_ROLLED_BACK`. If neither terminal state can be proven, the file
remains with state `HALTED`, and all live broker writes fail closed. This deploy
authorization never authorizes a manual order or changes capital, strategy,
whitelist, order type, risk limits, or promotion stage.

The workflow still calls the fixed helper when the ordinary deploy has already
completed. With no stale request or interlock, this is a no-mutation no-op. If a
verified rollback request and `QUIESCED` interlock were left behind by interrupted
shell cleanup, and a later ordinary live deploy already advanced production to the
exact current main, cleanup-only recovery requires the original closed file and
ledger proofs plus Git ancestry, one later successful target deploy, an in-window
`WORKER_STARTED`, active worker and live timer, both exclusive locks, and a fresh
KIS `open_unfilled=0` result. It appends a new authorization and
`DEPLOY_EMERGENCY_RECOVERY_COMPLETED`, then removes only the stale files. It does
not restart services, mutate code, or submit/cancel an order. Missing or ambiguous
proof leaves the old interlock intact.

## 5. Rollback path (verification)

Push a deliberately-broken change to a test branch and:

```bash
sudo -u auto-invest /usr/local/bin/uv run auto-invest deploy --branch test-broken --repo /opt/auto-invest
```

Expected audit lineage on failure:

```
DEPLOY_STARTED
DEPLOY_FAILED phase=health_check
DEPLOY_ROLLED_BACK
```

The worker is then running the previous good sha. Exit code is 1.

## 6. Stop everything (operator)

```bash
systemctl disable --now auto-invest-deploy.timer
systemctl disable --now auto-invest-tune.timer
systemctl stop auto-invest.service
```

For a full audit trail, see
`specs/006-deploy-automation/quickstart.md` § Troubleshooting.

## What this DOES NOT do

- No multi-host orchestration; v1 is single-box.
- No Slack/email notifications; the audit log is the operator's
  notification surface.
- No rollback-to-arbitrary-sha; only one commit back per R-D6.
- Ordinary deploys do not run during US regular hours. The only exception is the
  repository-owner, exact-main, short-lived one-shot protocol above; it first
  halts broker writes and preserves all other deploy and trading gates.
