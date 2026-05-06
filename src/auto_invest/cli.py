"""Operator CLI (T046).

Implements the `auto-invest run` subcommand from
`contracts/cli.md`. Delegates parsing/validation to
`config.loader.load_config`, the gate chain to `risk/gates`, and the
runtime to `worker.loop.Worker`. Dry-run never reaches the broker.

Exit codes:
    0  normal shutdown
    1  runtime error after startup (logged + audited)
    2  startup validation failure (config invalid, secrets missing,
       schema migration required, stage-uniqueness conflict)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from decimal import Decimal
from pathlib import Path

import httpx
import typer

from auto_invest.broker.auth import get_valid_token
from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.loader import ConfigError, load_config, load_secrets
from auto_invest.execution.order_router import verify_stage_uniqueness
from auto_invest.logging_config import configure_logging
from auto_invest.persistence import db
from auto_invest.worker.loop import Worker, WorkerSettings

app = typer.Typer(no_args_is_help=True, add_completion=False)
db_app = typer.Typer(help="Database management subcommands.", no_args_is_help=True)
app.add_typer(db_app, name="db")
logger = logging.getLogger(__name__)


def _exit(code: int) -> None:
    raise typer.Exit(code)


def _require_clean_migrations(db_path: Path, *, allow_apply: bool) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    try:
        pending = db.pending_migrations(conn)
        if not pending:
            return
        if not allow_apply:
            typer.echo(
                f"Pending migrations: {pending}. Run `auto-invest db migrate`.",
                err=True,
            )
            _exit(2)
        db.migrate(conn)
    finally:
        conn.close()


@app.command()
def run(
    config: Path = typer.Option(
        Path("config/rules.toml"),
        "--config",
        "-c",
        help="Path to the rules TOML.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Optional .env file (defaults to process environment only).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate config, run migrations, then exit 0 — never contacts the broker.",
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443",
        "--base-url",
        help="KIS REST base URL.",
    ),
    capital: float = typer.Option(
        0.0,
        "--capital",
        help="Operator-declared total capital in USD; required for live runs.",
    ),
    require_session_open: bool = typer.Option(
        True,
        "--require-session-open/--ignore-session-window",
        help="Skip ticks outside US regular hours (default) or run anyway.",
    ),
    prices_path: Path = typer.Option(
        Path("config/llm_prices.toml"),
        "--prices",
        help="Anthropic price table (TOML); validated at startup per spec 002.",
    ),
) -> None:
    configure_logging()

    # 1. Secrets + config (refuses on missing required values).
    from auto_invest.telemetry.prices import PriceTableError, load_prices

    try:
        secrets = load_secrets(env_file)
        cfg = load_config(config, env_path=env_file)
        prices = load_prices(prices_path)
    except (ConfigError, PriceTableError) as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        _exit(2)

    # 2. Stage-uniqueness preflight.
    decisions = verify_stage_uniqueness(list(cfg.rules))
    blocked = [d for d in decisions if not d.allow]
    if blocked:
        for decision in blocked:
            typer.echo(
                f"Stage-uniqueness denied: {decision.reason}",
                err=True,
            )
        _exit(2)

    # 3. Migrations gate. Dry-run is allowed to apply pending migrations
    # so the operator can run the full chain (validate -> migrate -> exit)
    # in one safe step.
    _require_clean_migrations(db_path, allow_apply=dry_run)

    # 4. Telemetry integrity check (FR-T12). Mismatches produce a
    # DATA_QUALITY_ISSUE audit row but do not block startup. Also pin
    # the price-table version that priced this process (T503 / spec 002 R-T3).
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _integrity_conn = db.get_connection(db_path)
    try:
        from auto_invest.persistence import audit as _audit_mod
        from auto_invest.persistence.audit import DataQualityIssuePayload as _DQIP
        from auto_invest.persistence.audit import (
            PriceTableLoadedPayload as _PTLP,
        )
        from auto_invest.telemetry.store import integrity_check as _integrity

        _audit_mod.append(
            _integrity_conn,
            _PTLP(path=prices.source_path, sha256=prices.sha256),
        )
        mismatches = _integrity(_integrity_conn)
        for m in mismatches:
            _audit_mod.append(
                _integrity_conn,
                _DQIP(
                    issue="token_usage_audit_mismatch",
                    detail={"correlation_id": m.correlation_id, "kind": m.kind},
                ),
                correlation_id=m.correlation_id,
            )
    finally:
        _integrity_conn.close()

    if dry_run:
        typer.echo("Dry run successful.")
        typer.echo(f"  rules:    {len(cfg.rules)}")
        typer.echo(f"  symbols:  {sorted(cfg.whitelist.symbols)}")
        typer.echo(
            "  caps:     "
            f"per-trade {cfg.caps.per_trade_pct}%, "
            f"per-symbol {cfg.caps.per_symbol_pct}%, "
            f"global {cfg.caps.global_exposure_pct}%"
        )
        typer.echo(f"  database: {db_path}")
        typer.echo(f"  halt:     {halt_path}")
        _exit(0)

    if capital <= 0:
        typer.echo("--capital must be > 0 for a live run.", err=True)
        _exit(2)

    asyncio.run(
        _run_live(
            cfg=cfg,
            secrets=secrets,
            db_path=db_path,
            halt_path=halt_path,
            config_path=config,
            base_url=base_url,
            total_capital_usd=Decimal(str(capital)),
            require_session_open=require_session_open,
        )
    )


@app.command()
def version() -> None:
    """Print the auto-invest package version."""
    typer.echo("auto-invest 0.1.0")


@app.command()
def efficiency(
    window: str = typer.Option(
        "7d",
        "--window",
        help="Window size: Nd (days) or Nh (hours). Default 7d.",
    ),
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Window end (exclusive). YYYY-MM-DD; default: now (UTC).",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    prices_path: Path = typer.Option(
        Path("config/llm_prices.toml"),
        "--prices",
        help="Anthropic price table (TOML).",
    ),
    thresholds_path: Path = typer.Option(
        Path("config/llm_kpi_thresholds.toml"),
        "--thresholds",
        help="KPI threshold table (TOML).",
    ),
) -> None:
    """Emit a JSON snapshot of LLM token-efficiency KPIs over a window."""
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime
    from datetime import timedelta

    from auto_invest.persistence import audit as _audit
    from auto_invest.persistence.audit import PriceTableLoadedPayload
    from auto_invest.telemetry.kpi import compute_snapshot
    from auto_invest.telemetry.prices import PriceTableError, load_prices
    from auto_invest.telemetry.thresholds import TierTableError, load_thresholds

    if window.endswith("d"):
        delta = timedelta(days=int(window[:-1]))
    elif window.endswith("h"):
        delta = timedelta(hours=int(window[:-1]))
    else:
        typer.echo("--window must be Nd or Nh", err=True)
        _exit(2)

    end = (
        _datetime.fromisoformat(as_of).replace(tzinfo=_UTC)
        if as_of is not None
        else _datetime.now(_UTC)
    )
    start = end - delta

    def _iso_ms(d: _datetime) -> str:
        return d.strftime("%Y-%m-%dT%H:%M:%S.") + f"{d.microsecond // 1000:03d}Z"

    try:
        prices = load_prices(prices_path)
        tiers = load_thresholds(thresholds_path)
    except (PriceTableError, TierTableError) as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        _exit(2)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        _audit.append(
            conn,
            PriceTableLoadedPayload(path=prices.source_path, sha256=prices.sha256),
        )
        snapshot = compute_snapshot(
            conn,
            window_start_utc=_iso_ms(start),
            window_end_utc=_iso_ms(end),
            tiers=tiers,
        )
    finally:
        conn.close()

    payload = {
        "window_start_utc": snapshot.window_start_utc,
        "window_end_utc": snapshot.window_end_utc,
        "call_count": snapshot.call_count,
        "kpis": [
            {
                "name": k.name,
                "value": str(k.value),
                "tier": k.tier,
                "direction": k.direction,
                "threshold_used": k.threshold_used,
            }
            for k in snapshot.kpis
        ],
        "per_decision_class": snapshot.per_decision_class,
        "top_n_calls": snapshot.top_n_calls,
    }
    typer.echo(_json.dumps(payload, sort_keys=True, indent=2))


@db_app.command("migrate")
def db_migrate(
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
) -> None:
    """Apply any pending schema migrations.

    Refuses to run when the worker's PID file exists and the recorded
    process is still alive — running migrations against an open DB
    risks corrupting the audit log.
    """
    pid_file = db_path.parent / "auto_invest.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
        except (ValueError, OSError):
            # Stale PID file: process is gone, safe to remove.
            pid_file.unlink(missing_ok=True)
        else:
            typer.echo(
                f"Worker process {pid} appears to be running; stop it first.",
                err=True,
            )
            _exit(2)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    try:
        applied = db.migrate(conn)
    finally:
        conn.close()

    if applied:
        typer.echo("Applied migrations: " + ", ".join(applied))
    else:
        typer.echo("No pending migrations.")


@app.command()
def report(
    date: str = typer.Option(
        None,
        "--date",
        "-d",
        help="Session date in YYYY-MM-DD (default: yesterday UTC).",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    output_root: Path = typer.Option(
        Path("data/reports"),
        "--output-root",
        help="Reports directory; one folder per session date.",
    ),
    thresholds_path: Path = typer.Option(
        Path("config/llm_kpi_thresholds.toml"),
        "--thresholds",
        help="KPI threshold table for the Token Efficiency section (spec 002).",
    ),
) -> None:
    """Generate the daily report for the given session date."""
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime
    from datetime import timedelta

    from auto_invest.reports.daily import build_report, write_report
    from auto_invest.telemetry.thresholds import TierTableError, load_thresholds

    session_date = date or ((_datetime.now(_UTC) - timedelta(days=1)).strftime("%Y-%m-%d"))

    tiers = None
    if thresholds_path.exists():
        try:
            tiers = load_thresholds(thresholds_path)
        except TierTableError as exc:
            typer.echo(f"Threshold table error: {exc}", err=True)
            _exit(2)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        rep = build_report(conn, session_date=session_date, tiers=tiers)
        md_path, json_path = write_report(rep, output_root=output_root)
    finally:
        conn.close()

    typer.echo(f"Daily report written: {md_path}")
    typer.echo(f"  JSON sibling:        {json_path}")
    typer.echo(f"  orders attempted:    {rep.counters.get('orders_attempted', 0)}")
    typer.echo(f"  orders submitted:    {rep.counters.get('orders_submitted', 0)}")
    typer.echo(f"  orders rejected:     {rep.counters.get('orders_rejected_by_gate', 0)}")
    typer.echo(f"  reconciliation:      {rep.reconciliation}")
    if rep.efficiency is not None:
        typer.echo(f"  llm_calls:           {rep.efficiency.call_count}")


@app.command()
def status(
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
) -> None:
    """Print a one-screen JSON summary of the current state."""
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from auto_invest.persistence import positions as _positions
    from auto_invest.worker.halt import read_halt as _read_halt

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        halt_state = _read_halt(halt_path)
        last_recon = conn.execute(
            "SELECT result, started_at_utc FROM reconciliation_runs ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        today = _datetime.now(_UTC).strftime("%Y-%m-%d")
        order_counts = dict(
            conn.execute(
                """
                SELECT event_type, COUNT(*) FROM audit_log
                WHERE substr(ts_utc, 1, 10) = ?
                  AND event_type IN ('ORDER_INTENT','ORDER_SUBMITTED',
                                     'ORDER_REJECTED_BY_GATE','FILL')
                GROUP BY event_type
                """,
                (today,),
            ).fetchall()
        )
        positions = [
            {"symbol": p.symbol, "qty": p.qty, "avg_cost_usd": str(p.avg_cost_usd)}
            for p in _positions.get_all_positions(conn)
        ]
    finally:
        conn.close()

    summary = {
        "halt": (
            {"reason": halt_state.reason, "ts_utc": halt_state.ts_utc} if halt_state else None
        ),
        "last_reconciliation": (
            {"result": last_recon["result"], "started_at_utc": last_recon["started_at_utc"]}
            if last_recon
            else None
        ),
        "today_order_counts": order_counts,
        "positions": positions,
    }
    typer.echo(_json.dumps(summary, sort_keys=True, indent=2))


@app.command()
def halt(
    reason: str = typer.Option(..., "--reason", help="Operator-supplied reason for halting."),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path (audit log destination).",
    ),
) -> None:
    """Set the halt flag so no new orders are submitted."""
    from auto_invest.persistence.audit import HaltSetPayload
    from auto_invest.worker.halt import set_halt as _set_halt

    db_path.parent.mkdir(parents=True, exist_ok=True)
    state = _set_halt(halt_path, reason)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        from auto_invest.persistence import audit as _audit

        _audit.append(conn, HaltSetPayload(reason=state.reason))
    finally:
        conn.close()
    typer.echo(f"Halt set: {state.reason!r} at {state.ts_utc}")


@app.command()
def resume(
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="Required to actually clear the halt; prevents accidental resume.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path (audit log destination).",
    ),
) -> None:
    """Clear the halt flag (requires --confirm)."""
    from auto_invest.persistence.audit import HaltClearedPayload
    from auto_invest.worker.halt import clear_halt as _clear_halt

    if not confirm:
        typer.echo(
            "Pass --confirm to actually clear the halt flag.",
            err=True,
        )
        _exit(2)

    cleared = _clear_halt(halt_path)
    if not cleared:
        typer.echo("No halt flag was set.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        from auto_invest.persistence import audit as _audit

        _audit.append(conn, HaltClearedPayload(cleared_by="cli"))
    finally:
        conn.close()
    typer.echo("Halt cleared.")


async def _run_live(
    *,
    cfg,
    secrets: dict,
    db_path: Path,
    halt_path: Path,
    config_path: Path,
    base_url: str,
    total_capital_usd: Decimal,
    require_session_open: bool,
) -> None:
    settings = WorkerSettings(
        config=cfg,
        db_path=db_path,
        halt_path=halt_path,
        config_path=config_path,
        total_capital_usd=total_capital_usd,
        require_session_open=require_session_open,
    )

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as inner:
        token = await get_valid_token(
            inner,
            base_url=base_url,
            app_key=secrets["KIS_APP_KEY"],
            app_secret=secrets["KIS_APP_SECRET"],
            cache_path=db_path.parent / "kis_token.json",
        )
        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=15.0, capacity=15.0),
            breaker=CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0),
            max_retries=4,
        )
        worker = Worker(
            settings,
            broker=broker,
            access_token=token.access_token,
            app_key=secrets["KIS_APP_KEY"],
            app_secret=secrets["KIS_APP_SECRET"],
            account_no=secrets["KIS_ACCOUNT_NO"],
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):  # pragma: no cover (Windows)
                loop.add_signal_handler(sig, worker.request_stop)

        worker.record_start(secret_keys=list(secrets.keys()))
        try:
            await worker.run_forever()
        finally:
            worker.record_stop("normal_shutdown")
            worker.close()
