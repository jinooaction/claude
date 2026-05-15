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

```bash
install -m 0644 /opt/auto-invest/deploy/auto-invest.service /etc/systemd/system/auto-invest.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.timer /etc/systemd/system/auto-invest-deploy.timer

systemctl daemon-reload

# Worker — long-running:
systemctl enable --now auto-invest.service

# Deploy timer — fires every 30 min outside US regular hours:
systemctl enable --now auto-invest-deploy.timer
```

## 3. Verify

```bash
systemctl status auto-invest.service
journalctl -u auto-invest.service -n 50

systemctl list-timers auto-invest-deploy.timer
journalctl -u auto-invest-deploy.service -n 50
```

The timer's calendar expression intentionally OMITS hours `13..20`
(US regular session UTC); the deploy runner's
`market_hours_guard` catches edge cases (DST shifts) regardless,
refusing with `DEPLOY_FAILED(phase=market_hours_guard)`.

## 4. Trigger a deploy manually (any time, off-hours only)

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
systemctl stop auto-invest.service
```

For a full audit trail, see
`specs/006-deploy-automation/quickstart.md` § Troubleshooting.

## What this DOES NOT do

- No multi-host orchestration; v1 is single-box.
- No Slack/email notifications; the audit log is the operator's
  notification surface.
- No rollback-to-arbitrary-sha; only one commit back per R-D6.
- No deploy during US regular hours, ever — guarded both by the
  timer's calendar AND by the runner's `market_hours_guard`.
