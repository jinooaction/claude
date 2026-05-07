# Feature Specification: Deploy Automation

**Feature Branch**: `006-deploy-automation` (developed on `claude/optimize-token-efficiency-uYiKk`)
**Created**: 2026-05-06
**Last revised**: 2026-05-06 (constitution v2.0.0 alignment — kernel-touch guard added)
**Status**: Draft
**Constitution**: v2.0.0 (consumes principles VIII.A, VIII.B, and IX)
**Input**: Operator description: "배포도 자동화해줘. 필요하다면 헌법도 수정할거야 ... 나는 머지도 개입하고 싶지 않아." Operator wants a single command that pulls the latest branch, applies migrations, validates config, restarts the worker, and confirms health — refusing to run during US regular hours, recording every step in the audit log, AND auto-merging non-Kernel change sets that pass spec 007's hardened canary.

## User Scenarios & Testing

### User Story 1 — One command deploys safely off-hours (Priority: P1)

The operator types `auto-invest deploy` (or invokes the scheduled cron/systemd timer that calls the same script) and the system pulls the configured branch, applies pending migrations, dry-runs the config, restarts the worker, and waits 30 s for a healthy liveness signal before declaring success. The whole flow is recorded in `audit_log` as `DEPLOY_STARTED` → `DEPLOY_COMPLETED` (or `DEPLOY_FAILED`).

**Why this priority**: Manual deploys are the single most reliable way principle VIII.A gets violated by accident. Automation that enforces the rule is the right answer.

**Independent Test**: Stage a fake commit on the configured branch, run `auto-invest deploy --dry-run` outside market hours; verify it pulls, applies migrations against a temporary DB, dry-runs the config, and emits `DEPLOY_STARTED` + `DEPLOY_COMPLETED` with `phase="dry_run"`. No actual worker restart in dry-run.

**Acceptance Scenarios**:

1. **Given** the US market is currently open, **When** `auto-invest deploy` runs, **Then** the command refuses with exit code 2, prints the next allowed deploy window (UTC), and emits `DEPLOY_FAILED` with `phase="market_hours_guard"`.
2. **Given** the working tree has uncommitted changes, **When** the command runs, **Then** it refuses with exit code 2 and emits `DEPLOY_FAILED` with `phase="precondition_dirty_tree"`.
3. **Given** all preconditions pass, **When** the command runs, **Then** it executes phases `pull → sync → migrate → dry_run → stop_worker → start_worker → health_check` in order and emits `DEPLOY_STARTED` before phase 1 and `DEPLOY_COMPLETED` after phase 7.
4. **Given** the migration fails, **When** the command runs, **Then** it does NOT stop the existing worker, emits `DEPLOY_FAILED` with `phase="migrate"`, and exits non-zero.
5. **Given** the post-restart health check times out, **When** the command runs, **Then** it emits `DEPLOY_FAILED` with `phase="health_check"`, attempts to restart the previous version (if a previous PID/sha is recorded), and surfaces the failure on stderr.

---

### User Story 2 — Audit log carries deploy lineage (Priority: P1)

After a deploy, the operator can answer "what changed in production at 02:00 UTC?" by running a single SQL query against the audit log. Every deploy event carries: `git_sha_before`, `git_sha_after`, `phase`, `reason`, and `correlation_id` so all phases of one deploy are joinable.

**Acceptance Scenarios**:

1. **Given** a successful deploy, **When** the operator queries `SELECT * FROM audit_log WHERE event_type LIKE 'DEPLOY_%' AND correlation_id = ?`, **Then** they get exactly two rows (`DEPLOY_STARTED`, `DEPLOY_COMPLETED`) sharing the same `correlation_id`.
2. **Given** a failed deploy, **When** queried similarly, **Then** the rows are `DEPLOY_STARTED` + `DEPLOY_FAILED` (and optionally a `DEPLOY_ROLLED_BACK` row).

---

### User Story 3 — Scheduler-friendly exit codes (Priority: P2)

A cron line or systemd timer can call the deploy script every 30 minutes during off-hours; the script must be safe to retry: if there is nothing to deploy (HEAD already matches origin), it MUST exit 0 without any side effect or audit row.

**Acceptance Scenarios**:

1. **Given** local HEAD already matches `origin/<branch>`, **When** the script runs, **Then** it exits 0 with the message "no changes to deploy" and writes no audit rows.
2. **Given** local HEAD lags `origin/<branch>` and market hours are open, **When** the script runs, **Then** it exits 2 with the market-hours-guard message and writes a single `DEPLOY_FAILED` row (so a forensic trail exists for blocked attempts).

---

### Edge Cases

- The previous worker is already stopped at deploy time (operator stopped it manually): script proceeds without a `stop_worker` step, but still emits `DEPLOY_STARTED` and the post-deploy health check still applies.
- The Anthropic SDK or KIS endpoint is down at deploy time: the worker's normal resilience (constitution VII) handles it after restart; deploy success is judged by `WORKER_STARTED` landing, not by external API health.
- The deploy script itself is updated in the same pull: the OS shell still has the old script in memory; the script MUST `exec`-replace itself with the new version after `git pull` if and only if the script's own SHA changed (or the operator can re-run the script idempotently — current design favors idempotent re-run).
- Disk full mid-migration: SQLite raises; the migration is `IF NOT EXISTS`-guarded so a retry after freeing space succeeds. `DEPLOY_FAILED(phase="migrate")` records the cause.
- Two operators trigger the script concurrently on the same host: a PID file at `data/auto_invest.deploy.pid` (similar to the existing `auto_invest.pid`) prevents overlap; the second instance exits 2 with `phase="precondition_lock"`.

## Requirements

- **FR-D01**: System MUST ship a single command-line entry point `auto-invest deploy` (subcommand of the existing CLI) that performs the full deploy flow.
- **FR-D02**: The command MUST refuse to proceed during US regular trading hours (constitution VIII.A) using `exchange_calendars` to determine session state. The check uses the same logic the worker already uses for trigger evaluation.
- **FR-D03**: The command MUST emit `DEPLOY_STARTED` before any side-effecting phase, and exactly one of `DEPLOY_COMPLETED` / `DEPLOY_FAILED` per invocation.
- **FR-D04**: All deploy audit rows MUST share a `correlation_id` so a single query reconstructs the deploy. The id is the git sha-256 of `git_sha_before + ':' + start_ts_utc`.
- **FR-D05**: The command MUST refuse to proceed if the working tree is dirty, unless `--allow-dirty` is passed (logged in the audit row). Dirty-tree detection is `git status --porcelain` returning non-empty.
- **FR-D06**: The command MUST hold an exclusive deploy lock (PID file at `data/auto_invest.deploy.pid`) for its duration; a second concurrent invocation refuses with exit 2.
- **FR-D07**: The command MUST run a 30-second post-restart health check that requires: (a) a new `WORKER_STARTED` audit row dated after the deploy started, (b) zero `ERROR` rows in that window, (c) zero `DATA_QUALITY_ISSUE` rows about telemetry mismatch.
- **FR-D08**: On failure of the health check OR the migration phase, the command MUST attempt to restore the previous worker version (`git checkout <sha_before>` + restart) AND, on rollback success, emit `DEPLOY_ROLLED_BACK`. On rollback failure, emit `DEPLOY_FAILED` with `phase="rollback"` and exit non-zero. The command MUST NEVER leave the worker silently stopped.
- **FR-D09**: A `--dry-run` flag MUST run all phases that have no irreversible side effect (pull, sync, migrate against a temp DB, config dry-run) and emit `DEPLOY_COMPLETED` with `phase="dry_run"` without restarting the worker.
- **FR-D10**: System MUST refuse to deploy if any required secret is missing (FR-011 from spec 001), failing at the `precondition` phase.
- **FR-D11**: Idempotency: if `git rev-parse HEAD == git rev-parse origin/<branch>`, the command exits 0 with no side effects and no audit rows.
- **FR-D12**: System MUST ship a systemd unit + timer template at `deploy/auto-invest.service` and `deploy/auto-invest-deploy.timer` so operators on Linux hosts can wire it up in two `systemctl enable` invocations.
- **FR-D13** (constitution IX.B-1): System MUST consult `.specify/memory/kernel.toml` BEFORE the migrate phase and BEFORE the start-worker phase. If the change set's diff (`git diff --name-only <sha_before>..<sha_after>`) intersects ANY path in the manifest, the command MUST emit `DEPLOY_BLOCKED_KERNEL_TOUCH` carrying the touched paths and the matched manifest groups, abort, and exit 2. The previous worker version MUST remain running.
- **FR-D14** (constitution IX.B-2): When the deploy is initiated by the autonomous tuner (spec 005, identified by a request flag like `--triggered-by=auto-tuner`), the command MUST additionally verify the change set has passed the spec 007 hardened-canary acceptance criteria. Until 007 ships, autonomous-tuner deploys are refused at this phase regardless of kernel-touch result; the change set falls back to the human-merge path.

## Key Entities

- **DeployRun**: one invocation of `auto-invest deploy`. Identified by `correlation_id`. Phases: `precondition`, `market_hours_guard`, `pull`, `sync`, `migrate`, `dry_run`, `stop_worker`, `start_worker`, `health_check`, `rollback`.
- **DeployAuditEvent**: one of `DEPLOY_STARTED` / `DEPLOY_COMPLETED` / `DEPLOY_FAILED` / `DEPLOY_ROLLED_BACK`. Append-only via the existing `audit_log` table (no new table).

## Success Criteria

- **SC-D01**: Across any rolling 30-day window, zero deploys land during US regular hours (constitution VIII.A; verified by audit-log query).
- **SC-D02**: 100% of deploys are reconstructable from `audit_log` alone — operator can answer "what was the worker version at 14:00 UTC on date X?" without external state.
- **SC-D03**: A failed deploy never leaves the worker silently stopped; either the new version is running or the previous version is running.
- **SC-D04**: A no-op deploy (HEAD matches origin) completes in < 2 s and writes zero audit rows.

## Assumptions

- The operator is the sole user. Multi-tenant deploy authorization is out of scope.
- The host runs Linux with `systemd` OR the operator wires a different supervisor; the deploy script is supervisor-agnostic but ships systemd templates as the recommended path.
- The worker's audit log is reachable from the deploy script (same SQLite file). Cross-host deploys are out of scope for v1 of this feature.
- The deploy script lives in `src/auto_invest/deploy/` (importable so it can be unit-tested) and is exposed as `auto-invest deploy`. It does NOT live as a free-standing shell script under `scripts/` because it carries trading-system invariants and deserves the same test discipline as the rest of the codebase.

## Out of Scope (this feature)

- Multi-host deploys, blue/green, canary infrastructure, container orchestration.
- Rollback to arbitrary historical versions; rollback target is the immediately preceding sha.
- Push notifications on deploy events (future work; the audit log is sufficient for v1).
- Auto-merge to main: branches still merge by operator action.
