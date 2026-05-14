# Contract: `auto-invest deploy`

CLI surface for spec 006 deploy automation. This is the operator-facing
contract; deviations are breaking changes that require an update to
this file before the implementation lands.

## Synopsis

```
auto-invest deploy
    [--branch <name>]
    [--dry-run]
    [--allow-dirty]
    [--health-window-s <int>]
    [--triggered-by manual|auto-tuner]
    [--ruleset-sha256 <hex>]
    [--db <path>]
    [--repo <path>]
    [--supervisor systemd|dryrun]
    [--worker-unit <name>]
```

## Flags

| Flag | Default | Effect |
|------|---------|--------|
| `--branch` | `main` | The remote branch to deploy from. Sets the target sha via `origin/<branch>`. |
| `--dry-run` | off | Run preconditions + pull + migrate-against-temp-DB + config-validate. No worker restart. Emit `DEPLOY_COMPLETED(phase=dry_run)`. |
| `--allow-dirty` | off | Permit a dirty working tree. The dirty flag is recorded in `DEPLOY_STARTED.allow_dirty=true`. Disabled by default per FR-D05. |
| `--health-window-s` | 90 | Seconds to wait for `WORKER_STARTED` + zero errors after restart. Minimum 90 per constitution VIII.B-3; passing < 90 is a CLI parse error. |
| `--triggered-by` | `manual` | Routing tag. `manual` bypasses the spec 007 canary gate (operator instruction is the approval surface, per IX.D). `auto-tuner` enforces the canary gate (FR-D14). |
| `--ruleset-sha256` | none | Required when `--triggered-by=auto-tuner`. Used to match the `CANARY_PASSED` audit row's ruleset hash. Ignored for manual deploys. |
| `--db` | `data/auto_invest.db` | SQLite DB path the audit log lives on. Must already exist. |
| `--repo` | `.` (cwd) | Git repository root. Useful when invoking from systemd unit where cwd is set explicitly. |
| `--supervisor` | `systemd` | Backend for stop/start. `dryrun` is integration-test-only; `systemd` is production. |
| `--worker-unit` | `auto-invest.service` | The systemd unit name that runs the worker. Passed to `systemctl restart`. Ignored when `--supervisor=dryrun`. |

## Exit codes

| Code | Meaning |
|------|---------|
| **0** | Success (live deploy completed, dry-run completed, OR no-op idempotent exit). |
| **1** | Runtime error after `DEPLOY_STARTED` was emitted (e.g. health-check failed but rollback also failed). Audit log carries the cause. |
| **2** | Precondition failure before `DEPLOY_STARTED` could be emitted (market hours, dirty tree, missing secrets, lock held, idempotency-without-noop branch, CLI parse error). For some precondition failures (market hours, dirty tree, secrets) a `DEPLOY_FAILED` row is still written; for lock contention no row is written (the holder owns the audit story). |

## Standard output

First line on success or failure (after CLI parsing, before any audit
row): `deploy correlation_id: <32-hex>`. This is the join key for
forensic queries.

No-op (HEAD already matches origin/branch):

```
no changes to deploy (HEAD == origin/<branch> @ <sha>)
```

Exit 0, no audit row.

## Standard error

Failure phases print a single line describing the cause and the
next allowed action. Example for `phase=market_hours_guard`:

```
deploy refused: US market is open (NYSE session 14:30Z-21:00Z). Next allowed deploy: 21:00Z.
```

## Behavioural contract

### Order of phases

```
1.  cli_parse              (no audit; exit 2 on bad args)
2.  load_secrets           (no audit if missing — exit 2 + DEPLOY_FAILED(phase=precondition_secrets))
3.  acquire_lock           (no audit on contention — exit 2 only)
4.  idempotency_check      (no audit if HEAD==origin — exit 0)
5.  market_hours_guard     (audit row if blocked — exit 2 + DEPLOY_FAILED(phase=market_hours_guard))
6.  dirty_tree_check       (audit row if blocked — exit 2 + DEPLOY_FAILED(phase=precondition_dirty_tree))
7.  emit DEPLOY_STARTED
8.  pull                   (audit on failure)
9.  kernel_check           (audit DEPLOY_KERNEL_TOUCHED if touches; continues)
10. canary_gate            (only if --triggered-by=auto-tuner; audit on failure)
11. sync                   (uv sync; audit on failure)
12. migrate                (live DB; audit on failure)
13. dry_run_check          (config dry-run; audit on failure)
14. IF --dry-run: emit DEPLOY_COMPLETED(phase=dry_run); exit 0
15. stop_worker            (graceful; audit on failure)
16. start_worker           (audit on failure)
17. health_check           (90 s poll; audit on failure)
18. emit DEPLOY_COMPLETED(phase=live); exit 0
```

### Rollback semantics

If any phase ∈ {migrate, start_worker, health_check} fails:

1. Emit `DEPLOY_FAILED(phase=<failing_phase>)`.
2. `git checkout <sha_before>` (the worker's previous sha).
3. `uv sync` (restore previous deps).
4. `Supervisor.start_worker()` (restart previous version).
5. Wait up to 90 s for `WORKER_STARTED` evidence.
6. On rollback success: emit `DEPLOY_ROLLED_BACK`; exit 1.
7. On rollback failure: emit `DEPLOY_FAILED(phase=rollback)`; exit 1.

Phases before `DEPLOY_STARTED` do not trigger rollback (nothing
side-effecting happened yet).

### Lock semantics

The PID lock file at `data/auto_invest.deploy.pid` carries the PID
of the running deploy. Acquisition (R-D3):

- If file absent: create + write PID.
- If file present + `/proc/<pid>` exists + cmdline contains `auto-invest`: refuse with exit 2 + `phase=precondition_lock`.
- If file present but stale (process gone or wrong cmdline): overwrite.

Release: `try/finally` removal on exit. SIGTERM/SIGINT handled to
ensure release.

### No-op contract

If `git rev-parse HEAD == git rev-parse origin/<branch>` after the
`git fetch`, the runner MUST:

- Print exactly: `no changes to deploy (HEAD == origin/<branch> @ <sha>)`.
- Exit 0.
- Write zero audit rows.
- Complete in < 2 s (SC-D04). The lock is acquired and released
  during this path; no other phase runs.

### Health-check contract

Within `--health-window-s` seconds after `start_worker`:

- Query `audit_log` every 1 s.
- Required: ≥ 1 row of `WORKER_STARTED` whose `ts_utc > DEPLOY_STARTED.ts_utc` (R-D9).
- Required: zero rows of `ERROR` whose `ts_utc > DEPLOY_STARTED.ts_utc`.
- Required: zero rows of `DATA_QUALITY_ISSUE` whose `ts_utc > DEPLOY_STARTED.ts_utc` AND whose payload references telemetry mismatch.
- On timeout without `WORKER_STARTED`: `DEPLOY_FAILED(phase=health_check, reason="worker did not signal WORKER_STARTED within Ns")`.
- On any `ERROR` row: `DEPLOY_FAILED(phase=health_check, reason="ERROR row during health window: <where>: <message>")`.

## Idempotency property

Running `auto-invest deploy` repeatedly with no changes upstream is
safe and cheap: each invocation acquires the lock, fetches, sees
HEAD matches origin, releases the lock, exits 0. No side effects.

## Acceptance: integration test

`tests/integration/test_deploy_end_to_end.py` exercises:

1. No-op idempotent exit (FR-D11 / SC-D04).
2. Market-hours block (FR-D02).
3. Dry-run success (FR-D09).
4. Live deploy success with `DryRunSupervisor`.
5. Migration failure → rollback success.
6. Health-check timeout → rollback success.
7. Kernel-touched diff → `DEPLOY_KERNEL_TOUCHED` emitted, deploy continues.
8. Auto-tuner canary gate: missing CANARY_PASSED → exit 2.
9. Auto-tuner canary gate: matching CANARY_PASSED → deploy continues.

All using a fake git worktree + the `DryRunSupervisor` so the test
never calls `systemctl`.
