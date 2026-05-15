# Research — Spec 006 Deploy Automation (Phase 0)

Each entry documents a design decision the `/speckit-plan` flow needs
recorded so the resulting code matches operator intent.

## R-D1 — Supervisor abstraction (systemd-first, but pluggable)

**Decision**: ship a `Supervisor` protocol with two concrete
implementations: `SystemdSupervisor` (production) and
`DryRunSupervisor` (tests + `--dry-run`). The runner depends on the
protocol; the CLI flag `--supervisor` selects the implementation.

**Why**: the operator runs on a single Linux box with systemd today.
A protocol with one production implementation costs ~20 LOC more than
inlining `subprocess.run("systemctl", ...)` directly, BUT keeps the
integration test free of `systemctl` calls (the dry-run supervisor
captures intents in-memory). A second backend (e.g. raw `nohup`/PID
file) can be added without touching the runner.

**Rejected alternative**: invoke `systemctl` directly inside the
runner. Saves LOC but makes integration testing on non-systemd CI
boxes painful and forces test mocks at the `subprocess` layer.

## R-D2 — Health-check window (90 s default, configurable upward)

**Decision**: `--health-window-s` flag, default **90**, minimum 90 per
constitution VIII.B-3. The runner polls the audit log every 1 s for
the required signals.

**Why**: constitution VIII.B-3 says ≥ 90 s. The 30 s figure in the
original spec.md predates v1.1.0; corrected in this revision.
Polling cadence of 1 s is cheap (one indexed SQL query per tick) and
gives ≤ 1 s detection latency for `ERROR` and `DATA_QUALITY_ISSUE`
rows.

**Rejected alternative**: wait the full window then check once.
Cheaper but doubles worst-case detection latency for an early failure.

## R-D3 — Deploy lock file (PID file with stale detection)

**Decision**: `data/auto_invest.deploy.pid` contains the PID of the
running deploy. On startup the runner: (a) reads the file, (b) checks
`/proc/<pid>` (POSIX), (c) if the process is alive AND the cmdline
contains `auto-invest`, refuse with exit 2 + `phase=precondition_lock`,
(d) otherwise, treat as stale and overwrite. The file is removed on
normal exit AND on uncaught exception (`try/finally`).

**Why**: a crashed-deploy must not block the next attempt forever.
The cmdline check prevents PID-reuse false positives. POSIX-only
`/proc` check is acceptable per FR-D12 assumption (Linux + systemd).

## R-D4 — Idempotency check (origin-HEAD comparison, no audit row)

**Decision**: very first runner action after CLI parsing is
`git fetch --quiet origin <branch>` followed by `git rev-parse HEAD`
vs `git rev-parse origin/<branch>`. If equal: emit nothing to the
audit log, print "no changes to deploy", exit 0. SC-D04 budget < 2 s.

**Why**: the cron line will fire every 30 minutes. A no-op MUST be
silent in the audit log — otherwise the audit log fills with thousands
of "nothing to do" rows that obscure real deploys. Constitution
principle IV is preserved (still append-only for real events).

**Rejected alternative**: always emit a `DEPLOY_STARTED` even on
no-ops. Easier flow but violates SC-D04 (no audit rows for no-op).

## R-D5 — Correlation id derivation

**Decision**: `correlation_id = sha256(sha_before + ":" + start_ts_utc_iso8601).hexdigest()[:32]`.
First 32 hex chars (128 bits) are unique enough; full 64 chars are
overkill for the lifetime audit log.

**Why**: collision-free per-deploy id; reproducible from the audit
row data alone (no separate id generator state); 32-char truncation
keeps audit rows readable.

## R-D6 — Rollback strategy (one commit back, no arbitrary checkout)

**Decision**: rollback target is exactly `sha_before` (the SHA the
worker was running before this deploy). The runner records
`sha_before` in `DEPLOY_STARTED.payload` and re-uses it for the
`git checkout sha_before` step on failure. No arbitrary-version
rollback.

**Why**: arbitrary rollback raises the surface area significantly
(version skew with the DB schema, with the audit-event union, with
the config schema). Single-commit rollback is the minimum that gives
"never silently halted" (SC-D03) without DB-migration surprises —
because no schema change happened during this deploy if rollback is
to the immediately preceding sha.

**Rejected alternative**: rollback to last known-good sha tracked in
audit log. More resilient but introduces "last known good" state that
itself can become inconsistent. Deferred to a future spec.

## R-D7 — Kernel-touch check is post-pull, pre-migrate (still emitted, no longer blocking)

**Decision**: after `git pull` but before `migrate`, the runner runs
`git diff --name-only <sha_before>..<sha_after>` and feeds the list
into `auto_invest.deploy.kernel_guard.kernel_diff_check`. If `touches`
is non-empty, the runner emits a `DEPLOY_KERNEL_TOUCHED` audit row
carrying the touched paths and matched groups, **then continues**.

**Why**: per constitution v3.0.0 IX.A/IX.B-1, kernel touches are a
forensic-attention signal, not a merge or deploy gate. The real
production-deploy gate is the spec 007 canary (consumed via FR-D14).
The kernel_guard module's `KernelTouchReport` return type already
supports this — the consumer's interpretation just shifts from
"abort" to "log loud".

## R-D8 — Worker-start sequencing

**Decision**: the runner calls `Supervisor.stop_worker()`, waits up
to 10 s for the worker process to exit (poll `WORKER_STOPPED` audit
row), THEN calls `Supervisor.start_worker()`. A timeout on stop
fails the deploy at `phase=stop_worker`. There is no SIGKILL escape
hatch in v1; the operator can pre-stop the worker manually if it's
hung.

**Why**: a graceful stop is more important than fast deploy; a
SIGKILL during an open broker session could leak open orders.
Constitution principle II (deny-by-default) implies "fail closed" —
refuse to deploy on a hung worker rather than force-kill it.

## R-D9 — Health-check requires fresh WORKER_STARTED (not first-row poll)

**Decision**: the health check polls for a `WORKER_STARTED` row
whose `ts_utc > DEPLOY_STARTED.ts_utc`. The previous worker's
`WORKER_STARTED` (older) does NOT satisfy the check.

**Why**: if the new worker fails to come up but the old worker is
still running and emitted its own `WORKER_STARTED` row at boot, that
old row must not be mistaken for evidence that the new version is
healthy. Time-ordering is unambiguous because the audit log is
clock-monotonic per principle IV.

## R-D10 — Spec 007 canary verification (FR-D14, when triggered by auto-tuner)

**Decision**: when `--triggered-by=auto-tuner`, after the kernel
check, the runner queries the audit log for the most recent
`CANARY_PASSED` row and:

1. The row MUST exist and be ≤ 24 h old.
2. The row's `ruleset_sha256` MUST equal the operator-supplied
   `--ruleset-sha256` flag (the ruleset the canary validated).
3. The row's `code_sha256` MUST equal `git rev-parse <sha_after>`.

Failure on any clause emits `DEPLOY_FAILED(phase="canary_gate")` and
exits 2. Operator-initiated deploys (`--triggered-by=manual`, the
default) bypass this entire check per constitution IX.D.

**Why**: this is the production-deploy gate from constitution v3.0.0
IX.B-2. The spec 007 canary writes `CANARY_PASSED` with both hashes;
we just verify alignment. The 24 h staleness window prevents an old
canary pass from authorising a far-future deploy.

**Spec 005 dependency**: spec 005's tuner doesn't exist yet, so the
`auto-tuner` channel has no real caller today. The CLI flag is
present and the check is wired; spec 005 will fill in the caller.

## R-D11 — Migration runs against the live DB, not a temp DB

**Decision**: `migrate` phase calls `auto_invest.persistence.db.migrate(conn)`
against the *live* SQLite DB. The original spec text said "temp DB"
for dry-run only — clarified: live deploy migrates the live DB; the
existing `IF NOT EXISTS`-guarded migrations make this idempotent.

**Why**: the temp-DB pattern is for `--dry-run` (which still validates
that migrations would *apply*). For a real deploy, the migrations
must hit the actual `data/auto_invest.db` — otherwise the new worker
starts against an old schema. Per FR-D08, a migration failure
triggers rollback BEFORE the worker is stopped (the previous worker
keeps running its old schema, which is the current schema).

## R-D12 — No new runtime dependencies

**Decision**: implementation uses only `subprocess` (git, systemctl),
`tomllib` (manifest already loaded by kernel_guard), `pydantic` (audit
payloads), `typer` (CLI), `exchange_calendars` (market hours check —
already a dep). No new packages enter `pyproject.toml`.

**Why**: deploy automation must work on a minimally-provisioned host;
every new dep is a new pre-deploy `uv sync` surface to debug. The
existing deps cover everything.
