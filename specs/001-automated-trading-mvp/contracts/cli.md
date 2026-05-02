# Contract: Operator CLI

The worker is operated through `auto-invest`, a Typer-based CLI exposed
by `src/auto_invest/cli.py` and reachable via `python -m auto_invest`
or the `auto-invest` console script declared in `pyproject.toml`.

## Subcommands (v1 surface)

### `auto-invest run`

Starts the worker. Loads `.env`, validates `config/rules.toml`,
opens the SQLite database, schedules tasks, and enters the asyncio
loop. Exits with non-zero status if any startup gate fails.

| Flag | Meaning |
|------|---------|
| `--config PATH` | Override path to rules TOML (default `config/rules.toml`). |
| `--db PATH` | Override SQLite path (default `data/auto_invest.db`). |
| `--dry-run` | Validate config, open DB read-only, print resolved settings, then exit 0 — never contacts the broker. |

Exit codes:
- `0` — normal shutdown.
- `1` — runtime error after startup (logged + audited).
- `2` — startup validation failure (config invalid, secrets missing, schema migration required).

### `auto-invest halt --reason "<text>"`

Writes `data/halt.flag` with `{ "ts_utc": ..., "reason": ... }` payload.
Subsequent attempts to submit orders are denied at the gate. The flag
persists across worker restarts (FR-013).

### `auto-invest resume --confirm`

Removes `data/halt.flag` after writing a `HALT_CLEARED` audit row. The
explicit `--confirm` flag prevents an accidental enter-key resume.

### `auto-invest status`

Prints a one-screen JSON summary: worker pid (if running), halt state,
last reconciliation result, today's order counts by state, current
positions. Read-only; never mutates state.

### `auto-invest report [--date YYYY-MM-DD]`

Generates the daily report (see `daily-report.md`) for the given
session date, defaulting to the most recently completed US session.
Prints the report path and a short summary to stdout. Idempotent;
re-running on the same date reproduces the same artifact bytes.

### `auto-invest db migrate`

Applies any pending SQLite schema migrations. Idempotent. Safe to run
on a worker that is currently stopped; refuses to run if a worker
process is detected via PID file.

## Startup sequence (used by `run`)

1. Load `.env` → register every value through `register_secret()`.
2. Open DB; if migrations are pending, abort with exit code 2.
3. Parse and validate `config/rules.toml`.
4. Verify each whitelisted account exists in KIS (single bootstrap call).
5. Reconcile `current_positions` against KIS once before accepting any rule.
6. Start the asyncio loop with one task per active rule plus the
   APScheduler instance for end-of-session jobs.
7. Write `WORKER_STARTED` audit row.

## Shutdown sequence

`SIGINT` and `SIGTERM` request graceful shutdown:

1. Stop accepting new triggers.
2. Wait up to 5 s for in-flight broker calls to settle.
3. Write `WORKER_STOPPED` audit row with reason.
4. Close DB connections.
5. Exit `0`.

A second signal escalates to immediate exit `130` without writing the
stop row (the audit log will show only the start, which is enough to
flag the unclean shutdown).
