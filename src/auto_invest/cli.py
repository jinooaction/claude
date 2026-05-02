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
        Path("config/rules.toml"), "--config", "-c",
        help="Path to the rules TOML.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db",
        help="SQLite database path.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"), "--halt-path",
        help="Filesystem halt-flag path.",
    ),
    env_file: Path | None = typer.Option(
        None, "--env-file",
        help="Optional .env file (defaults to process environment only).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Validate config, run migrations, then exit 0 — never contacts the broker.",
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443", "--base-url",
        help="KIS REST base URL.",
    ),
    capital: float = typer.Option(
        0.0, "--capital",
        help="Operator-declared total capital in USD; required for live runs.",
    ),
    require_session_open: bool = typer.Option(
        True,
        "--require-session-open/--ignore-session-window",
        help="Skip ticks outside US regular hours (default) or run anyway.",
    ),
) -> None:
    configure_logging()

    # 1. Secrets + config (refuses on missing required values).
    try:
        secrets = load_secrets(env_file)
        cfg = load_config(config, env_path=env_file)
    except ConfigError as exc:
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
