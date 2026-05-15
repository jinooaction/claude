# Data Model — Spec 006 Deploy Automation

This feature does NOT introduce a new SQLite table. It extends the
existing `audit_log` table (defined in
`migrations/0001_initial.sql`) with five new `event_type` literals,
each carrying a frozen pydantic payload. The deprecated
`DEPLOY_BLOCKED_KERNEL_TOUCH` literal is preserved in the union for
backward compatibility but the runner no longer emits it.

## EventType union additions (K4 touch — additive)

```python
EventType = Literal[
    # ... existing literals ...
    "DEPLOY_BLOCKED_KERNEL_TOUCH",  # deprecated v3.0.0; preserved for old rows
    # NEW under spec 006 v3.0.0:
    "DEPLOY_STARTED",
    "DEPLOY_COMPLETED",
    "DEPLOY_FAILED",
    "DEPLOY_ROLLED_BACK",
    "DEPLOY_KERNEL_TOUCHED",
]
```

Adding to the `EventType` union is a K4 touch (forensic-attention per
constitution v3.0.0 IX.A). The change is purely additive — every
existing row's `event_type` value remains valid. K4 touch is logged
via the PR description per CLAUDE.md.

## Payloads

All payloads inherit from `AuditPayload` (frozen, `extra="forbid"`)
and pin their `event_type` literal as the discriminator.

### DeployStartedPayload

```python
class DeployStartedPayload(AuditPayload):
    event_type: Literal["DEPLOY_STARTED"] = "DEPLOY_STARTED"
    correlation_id: str            # 32-char hex (R-D5)
    sha_before: str                # 40-char git sha
    sha_after: str                 # 40-char git sha (target, == origin/<branch>)
    branch: str
    triggered_by: Literal["manual", "auto-tuner"]
    dry_run: bool
    allow_dirty: bool
    health_window_s: int           # 90 default; configurable upward
```

Emitted exactly once per non-noop invocation, before any side-effecting
phase (after preconditions pass).

### DeployCompletedPayload

```python
class DeployCompletedPayload(AuditPayload):
    event_type: Literal["DEPLOY_COMPLETED"] = "DEPLOY_COMPLETED"
    correlation_id: str
    sha_before: str
    sha_after: str
    phase: Literal["live", "dry_run"]
    duration_s: float
```

Emitted exactly once on success. `phase="dry_run"` for `--dry-run`
invocations; `phase="live"` for real deploys.

### DeployFailedPayload

```python
class DeployFailedPayload(AuditPayload):
    event_type: Literal["DEPLOY_FAILED"] = "DEPLOY_FAILED"
    correlation_id: str
    sha_before: str
    sha_after: str | None          # None if pull failed before resolving HEAD
    phase: Literal[
        "precondition_lock",
        "precondition_dirty_tree",
        "precondition_secrets",
        "market_hours_guard",
        "pull",
        "kernel_check",            # only if kernel guard itself errored (manifest load); not emitted for routine touches
        "sync",
        "migrate",
        "dry_run",
        "stop_worker",
        "start_worker",
        "health_check",
        "canary_gate",             # spec 007 verification failure
        "rollback",
    ]
    reason: str                    # human-readable cause
    exit_code: int                 # 2 for precondition; 1 for runtime
```

Emitted exactly once on any failed deploy. Subsequent rollback success
emits a separate `DEPLOY_ROLLED_BACK` row sharing `correlation_id`.

### DeployRolledBackPayload

```python
class DeployRolledBackPayload(AuditPayload):
    event_type: Literal["DEPLOY_ROLLED_BACK"] = "DEPLOY_ROLLED_BACK"
    correlation_id: str
    sha_before: str                # the sha we rolled BACK TO
    sha_after_failed: str          # the sha that failed to deploy
    rolled_back_phase: str         # which DEPLOY_FAILED.phase triggered the rollback
```

Emitted at most once per invocation. Pre-condition: a prior
`DEPLOY_FAILED` row with the same `correlation_id` exists. The
runner emits `DEPLOY_FAILED` first, attempts rollback, then emits
this row on rollback success. On rollback failure, no second row is
emitted; the operator must intervene.

### DeployKernelTouchedPayload

```python
class DeployKernelTouchedPayload(AuditPayload):
    event_type: Literal["DEPLOY_KERNEL_TOUCHED"] = "DEPLOY_KERNEL_TOUCHED"
    correlation_id: str
    sha_before: str
    sha_after: str
    touched_paths: list[str]       # POSIX paths from git diff --name-only
    touched_groups: list[str]      # e.g. ["K4_append_only_audit"]
    triggered_by: Literal["manual", "auto-tuner"]
```

Emitted at most once per invocation, between `DEPLOY_STARTED` and
the side-effecting phases, when `kernel_diff_check` reports
`touches`. Per constitution v3.0.0 IX.B-1 (repealed) this is
**informational**, not blocking — the deploy continues after the row
lands.

## Correlation graph

A single `correlation_id` (32-char hex per R-D5) joins all rows from
one deploy invocation:

```
DEPLOY_STARTED                      (always)
  └─ DEPLOY_KERNEL_TOUCHED          (only if kernel diff non-empty)
  └─ DEPLOY_FAILED                  (only on failure; mutually exclusive with COMPLETED)
       └─ DEPLOY_ROLLED_BACK        (only if rollback succeeded)
  └─ DEPLOY_COMPLETED               (only on success; mutually exclusive with FAILED)
```

Operator forensic query (SC-D02):

```sql
SELECT ts_utc, event_type, payload
FROM audit_log
WHERE json_extract(payload, '$.correlation_id') = ?
ORDER BY ts_utc ASC;
```

The `correlation_id` is also surfaced on stdout by the CLI as the
first line: `deploy correlation_id: <hex>` so the operator can copy
it directly into the query.

## On-disk artefacts (none)

The deploy automation writes ONLY to the audit log. There is no
`deploy-run.json`, no `metrics.csv`, no per-deploy artefact tree.
This is deliberate — the audit log is the single source of truth for
"what happened" and adding parallel artefacts would split that.

The PID lock file at `data/auto_invest.deploy.pid` is operational
state, not a deploy artefact; it is removed on normal exit.

## DB schema (unchanged)

```sql
-- existing migrations/0001_initial.sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,        -- JSON
    rule_id TEXT,
    order_id TEXT,
    symbol TEXT,
    correlation_id TEXT           -- existed from spec 001
);
```

No migration is required. The new event_type literals fit the
existing TEXT column; the new payloads fit the existing TEXT payload
JSON column.

## Invariants

- **I-1**: Exactly one of `DEPLOY_COMPLETED` / `DEPLOY_FAILED` per
  `correlation_id`. Enforced by the runner's try/finally branch
  structure.
- **I-2**: `DEPLOY_STARTED.ts_utc < DEPLOY_*.ts_utc` for every row
  sharing the same `correlation_id`. Enforced by the runner emitting
  STARTED before any other deploy event.
- **I-3**: `DEPLOY_ROLLED_BACK` rows exist only when a
  `DEPLOY_FAILED` row with the same `correlation_id` precedes them.
  Enforced by the runner's rollback path being unreachable from the
  success path.
- **I-4**: `DEPLOY_KERNEL_TOUCHED.touched_paths` is non-empty if the
  row exists. Enforced by the runner emitting the row only when
  `kernel_diff_check(...)` returns `touches` with at least one entry.
- **I-5**: No audit rows are written for a no-op deploy (HEAD already
  matches origin/<branch>). Enforced by the idempotency check
  running before `DEPLOY_STARTED` is emitted.
