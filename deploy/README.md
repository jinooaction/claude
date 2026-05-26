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

## 3. Verify

```bash
systemctl status auto-invest.service
journalctl -u auto-invest.service -n 50

systemctl list-timers auto-invest-deploy.timer auto-invest-tune.timer
journalctl -u auto-invest-deploy.service -n 50
journalctl -u auto-invest-tune.service -n 50
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
- No deploy during US regular hours, ever — guarded both by the
  timer's calendar AND by the runner's `market_hours_guard`.
