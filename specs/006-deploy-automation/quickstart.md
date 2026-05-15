# Quickstart — Spec 006 Deploy Automation

This is the operator's "I want my auto-invest worker to update itself
safely off-hours" walkthrough. Run-time ≤ 15 minutes on a fresh Linux
host once `uv` is installed.

## Prerequisites

- Linux with `systemd` (Ubuntu 22+, Debian 12+, Fedora 40+, etc.).
  Other supervisors are wired-but-untested in v1.
- `uv` installed and on `PATH`.
- The repo cloned at a known absolute path. The examples assume
  `/opt/auto-invest`; substitute your path.
- `.env` populated with KIS credentials (see
  `specs/001-automated-trading-mvp/quickstart.md`).
- The `auto_invest` package importable (`uv sync` already ran once).
- A user account `auto-invest` owns `/opt/auto-invest` and
  `/opt/auto-invest/data`. The systemd unit runs as this user.

## 1. Dry-run on the current branch

```bash
cd /opt/auto-invest
uv run auto-invest deploy --dry-run --branch main
```

Expected output:

```
deploy correlation_id: a1b2c3d4...
no changes to deploy (HEAD == origin/main @ ...)
```

If there ARE changes upstream:

```
deploy correlation_id: a1b2c3d4...
phase: pull (sha_before=ABC..., sha_after=DEF...)
phase: kernel_check (no touches)
phase: sync
phase: migrate (dry-run against temp DB)
phase: dry_run (config valid)
DEPLOY_COMPLETED phase=dry_run duration=4.2s
```

Verify the audit rows:

```bash
sqlite3 data/auto_invest.db \
  "SELECT event_type, json_extract(payload, '$.phase') AS phase
   FROM audit_log
   WHERE json_extract(payload, '$.correlation_id') = 'a1b2c3d4...'
   ORDER BY ts_utc;"
```

Expected: `DEPLOY_STARTED` then `DEPLOY_COMPLETED(phase=dry_run)`.

## 2. Install the systemd unit + timer

The repo ships templates at `deploy/`:

```bash
# As root:
install -m 0644 /opt/auto-invest/deploy/auto-invest.service /etc/systemd/system/auto-invest.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.timer /etc/systemd/system/auto-invest-deploy.timer

# Reload systemd so it picks up the new unit files:
systemctl daemon-reload

# Enable + start the worker:
systemctl enable --now auto-invest.service

# Enable + start the deploy timer (fires every 30 min off-hours):
systemctl enable --now auto-invest-deploy.timer
```

Verify the worker is up:

```bash
systemctl status auto-invest.service
journalctl -u auto-invest.service -n 50
```

Verify the timer is registered:

```bash
systemctl list-timers auto-invest-deploy.timer
```

You should see the next scheduled run time. The timer's calendar
expression is set to `*-*-* 00,01,02,06,07,08,09,10,11,12,13,22,23:00/30`
(half-hourly during off-US-hours UTC); the runner itself enforces
the market-hours guard regardless, so a misconfigured timer cannot
cause a market-hours deploy.

## 3. Watch a real deploy

After pushing a change to `main`:

```bash
# Wait for the timer to fire, OR trigger manually:
sudo -u auto-invest systemctl start auto-invest-deploy.service

# Watch:
journalctl -u auto-invest-deploy.service -f
```

Look for the correlation id, then:

```bash
sqlite3 data/auto_invest.db \
  "SELECT ts_utc, event_type, json_extract(payload, '$.phase') AS phase
   FROM audit_log
   WHERE json_extract(payload, '$.correlation_id') = '<id from log>'
   ORDER BY ts_utc;"
```

Expected sequence:

```
DEPLOY_STARTED
DEPLOY_KERNEL_TOUCHED   (only if kernel files changed; informational)
DEPLOY_COMPLETED(phase=live)
```

The worker's own `WORKER_STARTED` row will sit between
`start_worker` and `DEPLOY_COMPLETED`.

## 4. Test the rollback path (optional)

Push a deliberately-broken change to a test branch and deploy from
it. Example: a config file with an invalid TOML key.

```bash
sudo -u auto-invest uv run auto-invest deploy --branch test-broken
```

Expected:

```
DEPLOY_STARTED
DEPLOY_FAILED phase=health_check reason="..."
DEPLOY_ROLLED_BACK sha_before=<good> sha_after_failed=<bad>
```

The worker is now running the previous good sha. The audit log shows
the entire lineage. Exit code is 1.

## 5. Trigger an idempotent no-op

```bash
sudo -u auto-invest uv run auto-invest deploy
```

When `HEAD == origin/main`:

```
no changes to deploy (HEAD == origin/main @ <sha>)
```

Exit code 0. No audit rows. Completes in < 2 s. This is what the
timer does most of the time.

## 6. Verify market-hours guard

During US regular hours (14:30-21:00 UTC):

```bash
uv run auto-invest deploy
```

Expected:

```
deploy refused: US market is open (NYSE session 14:30Z-21:00Z). Next allowed deploy: 21:00Z.
```

Exit 2. A `DEPLOY_FAILED(phase=market_hours_guard)` row is written
so the forensic record exists.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `phase=precondition_lock` | A previous deploy crashed without releasing the PID file | Delete `data/auto_invest.deploy.pid` (only after confirming no `auto-invest deploy` is running). |
| `phase=precondition_dirty_tree` | Working tree has uncommitted changes | `git status` + commit or stash. Pass `--allow-dirty` only if you understand the risk (logged). |
| `phase=precondition_secrets` | `.env` missing keys | Check `specs/001-automated-trading-mvp/contracts/secrets.md`. |
| `phase=health_check` | Worker crashed within the first 90 s OR emitted ERROR rows | Inspect `journalctl -u auto-invest.service` and the `ERROR` audit rows for the correlation id. Rollback already restored the previous version. |
| `phase=canary_gate` (auto-tuner) | No recent `CANARY_PASSED` row matching the ruleset hash | Run the spec 007 hardened canary first; deploy retries pull the fresh `CANARY_PASSED`. |
| `phase=migrate` | Migration failed (disk full, bad SQL) | The previous worker is still running its old schema. Free disk / fix migration, then re-deploy. |

## What spec 006 does NOT do

- Multi-host deploys, blue/green, container orchestration — out of scope.
- Anything during US regular hours — refused at `market_hours_guard`.
- Touch the audit log's existing rows — append-only is enforced by DB trigger.
- Rollback further than one commit — out of scope per R-D6.
- Send Slack/email notifications — operator reads the audit log.
