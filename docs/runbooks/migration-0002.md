# Runbook: Apply migration 0002 (token_usage) and roll out spec 002/003

**When to run**: outside US regular trading hours (NYSE/NASDAQ
09:30–16:00 ET) — constitution VIII.

**Estimated time**: 5–10 minutes hands-on plus a 60-second smoke
window.

**Reversibility**: forward-only. The migration is `IF NOT EXISTS`-
guarded so a partial apply is retry-safe. Rollback steps below cover
the deploy itself, not the schema (you do not need to drop
`token_usage` to revert; it stays inert until 004 ships).

---

## 0. Pre-flight (≤ 1 min)

On your host:

```bash
cd <your auto-invest checkout>
date -u +'%Y-%m-%d %H:%M UTC'           # verify off-hours
git status                              # working tree must be clean
ps -ef | grep '[a]uto-invest run'       # note PID if a worker is up
ls -lh data/auto_invest.db              # note size for sanity
```

Abort and reschedule if:
- US regular session is currently open (>= 13:30 UTC and < 20:00 UTC
  on a NYSE trading day; check `exchange_calendars` if uncertain).
- Working tree has uncommitted changes you care about.
- The host shows two `auto-invest run` processes (split-brain;
  reconcile manually first).

## 1. Backup (≤ 1 min)

The audit log is the source of truth. Snapshot it:

```bash
mkdir -p backups
cp data/auto_invest.db "backups/auto_invest.$(date -u +%Y%m%dT%H%M%SZ).db"
ls -lh backups | tail -3
```

The cp is safe under WAL because SQLite uses a single file plus a
`.wal` sidecar; if the worker is running, also copy
`data/auto_invest.db-wal` and `data/auto_invest.db-shm` so the snapshot
is consistent.

## 2. Stop the worker (≤ 30 s)

If a worker is running:

```bash
# Preferred: SIGTERM, lets the asyncio loop close audit writes.
kill -TERM <pid>
# Wait for the WORKER_STOPPED audit row to land (≤ 5 s).
sqlite3 data/auto_invest.db \
  "SELECT ts_utc, event_type FROM audit_log
   WHERE event_type IN ('WORKER_STARTED','WORKER_STOPPED')
   ORDER BY seq DESC LIMIT 2;"
```

You should see `WORKER_STOPPED` as the most recent row before continuing.

## 3. Update code (≤ 1 min)

```bash
git fetch origin
git checkout claude/optimize-token-efficiency-uYiKk
git pull --ff-only
git log --oneline -3                    # last commit should match HANDOFF-002-003.md
```

## 4. Sync deps + apply migration (≤ 2 min)

```bash
uv sync
uv run auto-invest db migrate           # applies 0002_token_usage
# Expected: "Applied migrations: 0002_token_usage"
```

## 5. Validate config (no live broker contact) (≤ 30 s)

```bash
uv run auto-invest run --dry-run \
    --config config/rules.toml \
    --db data/auto_invest.db
# Expected exit 0 with a "Dry run successful." summary.
```

If you keep a separate `--config` per environment, repeat against
each.

## 6. Smoke-test the new surface (≤ 30 s)

```bash
# Empty-state JSON. Should exit 0 with all KPIs at tier "N/A".
uv run auto-invest efficiency --window 7d --as-of "$(date -u +%Y-%m-%d)"

# Daily report should render the Token Efficiency section
# (with "(no LLM calls today)" since v1 makes none).
uv run auto-invest report --date "$(date -u +%Y-%m-%d)"
cat data/reports/$(date -u +%Y-%m-%d)/daily-report.md | grep -A3 "Token Efficiency"
```

If the empty-state JSON returns non-zero or omits the four KPIs, **do
not start the worker**; jump to "Rollback" below.

## 7. Verify SessionStart hook (≤ 30 s, optional but recommended)

If you use Claude Code on this host:

```bash
.claude/hooks/session_context.py < /dev/null | python -m json.tool | head -5
# Expect: keys "hookSpecificOutput" and "systemMessage"; the
# systemMessage line includes "session-context fingerprint: <hex>".
```

Open a fresh Claude Code session and confirm the fingerprint appears
once at the start.

## 8. Restart the worker (≤ 30 s)

```bash
# Use whatever supervisor you normally use. Without one:
nohup uv run auto-invest run \
    --config config/rules.toml \
    --db data/auto_invest.db \
    --capital <N> \
    > logs/auto-invest.$(date -u +%Y%m%dT%H%M%SZ).log 2>&1 &
echo $! > data/auto_invest.pid

# Confirm WORKER_STARTED lands.
sleep 3
sqlite3 data/auto_invest.db \
  "SELECT ts_utc, event_type FROM audit_log
   ORDER BY seq DESC LIMIT 1;"
# Expected: WORKER_STARTED with a fresh ts_utc.
```

## 9. Post-deploy smoke (≤ 60 s)

Watch for one full loop tick:

```bash
sleep 60
uv run auto-invest status               # JSON; halt should be null
tail -50 logs/auto-invest.*.log
```

Look for:
- No tracebacks
- Exactly one `WORKER_STARTED` row newer than the deploy timestamp
- No `DATA_QUALITY_ISSUE` rows referencing `token_usage_audit_mismatch`
  (FR-T12 startup integrity check should be silent on a fresh deploy)

If anything fails, jump to "Rollback".

## Rollback

The deploy itself is rollback-safe; the schema is forward-only but
inert.

To revert the worker to the pre-deploy commit:

```bash
# Stop the worker again.
kill -TERM $(cat data/auto_invest.pid)

# Switch back to the prior tag/branch (note this BEFORE step 3).
git checkout <previous-ref>             # e.g., dd81fa0 or main
uv sync

# The schema migration stays applied (the new table is empty and
# unreferenced by old code). Restart:
uv run auto-invest run --config config/rules.toml --db data/auto_invest.db --capital <N>
```

If you need to restore the audit log itself (not normally required —
the migration is non-destructive):

```bash
mv data/auto_invest.db data/auto_invest.broken.db
cp backups/auto_invest.<TS>.db data/auto_invest.db
```

## Verification checklist (paste into your runbook log)

- [ ] Off-hours confirmed at start
- [ ] Backup created at `backups/auto_invest.<TS>.db`
- [ ] Worker stopped cleanly (`WORKER_STOPPED` audit row present)
- [ ] Branch `claude/optimize-token-efficiency-uYiKk` checked out at
      commit `edfc97b` or later
- [ ] `auto-invest db migrate` reported `0002_token_usage` applied
- [ ] `auto-invest run --dry-run` succeeded
- [ ] `auto-invest efficiency --window 7d` returned valid JSON
- [ ] `auto-invest report --date <today>` rendered Token Efficiency section
- [ ] SessionStart hook returned a stable fingerprint (optional)
- [ ] Worker restarted; new `WORKER_STARTED` audit row present
- [ ] 60-second smoke window: no tracebacks, no integrity mismatches
- [ ] Logged this run in your operations journal
