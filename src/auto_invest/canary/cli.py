"""Canary CLI — ``python -m auto_invest.canary`` entrypoint (T018).

Implements ``contracts/canary-cli.md`` exit codes:

  0 — CANARY_PASSED
  1 — CANARY_FAILED
  2 — historical dataset incomplete
  3 — internal error
  4 — CLI usage error

Phase 3 US1 wires the ``run`` subcommand fully. ``shock`` and ``fuzz``
are stubbed to ``EXIT_INTERNAL`` until Phase 4 US2 fills them.
"""

from __future__ import annotations

import sys
import sqlite3
import traceback
import uuid
from datetime import date as _date
from pathlib import Path

import typer

from auto_invest.canary import run as run_module
from auto_invest.canary.bands import DEFAULT_PATH as DEFAULT_BANDS_PATH
from auto_invest.canary.bands import CanaryBandsConfigError
from auto_invest.canary.replay_window import ReplayWindowInputs
from auto_invest.canary.run import (
    EXIT_FAILED,
    EXIT_INTERNAL,
    EXIT_OK,
    EXIT_USAGE,
    CanaryOptions,
    run_canary,
)
from auto_invest.persistence import db

app = typer.Typer(
    add_completion=False,
    rich_markup_mode=None,
    help="Hardened canary harness — spec 007 / constitution v3.0.0 IX.B-2.",
)


@app.command("run")
def run_cmd(
    tier: str = typer.Option(..., "--tier", help="L2 or L3. L1 rejected (no canary needed)."),
    rules: Path = typer.Option(
        ..., "--rules", help="Rules TOML path (same format as live worker)."
    ),
    date_from: str = typer.Option(
        None, "--from", help="Window start (YYYY-MM-DD)."
    ),
    date_to: str = typer.Option(
        None, "--to", help="Window end (YYYY-MM-DD)."
    ),
    candidate_rev: str = typer.Option(
        "HEAD", "--candidate-rev", help="Git ref or SHA; default HEAD."
    ),
    baseline_rev: str = typer.Option(
        None,
        "--baseline-rev",
        help="Git ref or SHA. Default: most recent CANARY_PASSED.candidate_rev,"
        " fallback origin/main (per R-C1).",
    ),
    bands_toml: Path = typer.Option(
        DEFAULT_BANDS_PATH, "--bands-toml", help="Path to canary_bands.toml."
    ),
    out_root: Path = typer.Option(
        Path("data/canary"), "--out-dir", help="Where per-run artefacts go."
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite audit-log path."
    ),
    history_root: Path = typer.Option(
        Path("data/history"),
        "--history-root",
        help="Where spec-008 ingested datasets live.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Halt-flag path (reused unmodified from live worker).",
    ),
    canary_run_id: str = typer.Option(
        None, "--run-id", help="Override the generated UUID4 (forensic reruns)."
    ),
    hypothesis_seed: int = typer.Option(
        None, "--hypothesis-seed", help="Seed for the fuzz pass; default derives from run_id."
    ),
    hypothesis_iterations: int = typer.Option(
        10_000, "--hypothesis-iterations", help="Per FR-C04, minimum 10000."
    ),
    skip_fuzz: bool = typer.Option(
        False,
        "--skip-fuzz",
        help="Skip the property-fuzz pass (test-only; production canaries MUST fuzz).",
    ),
    shocks_toml: Path = typer.Option(
        None,
        "--shocks-toml",
        help="Path to synthetic_shocks.toml; default uses spec 008's config.",
    ),
    skip_shock: bool = typer.Option(
        False,
        "--skip-shock",
        help="Skip the synthetic-shock pass (test-only; production canaries MUST shock).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve revs + plan only; do NOT emit CANARY_ENTERED or write artefacts.",
    ),
) -> None:
    """Run the full canary battery (Phase 3 US1: window replay + 5-metric eval)."""

    if tier not in ("L2", "L3"):
        typer.echo(
            f"--tier must be L2 or L3 (got {tier!r}); L1 changes do not need a canary",
            err=True,
        )
        _exit(EXIT_USAGE)

    if date_from is None or date_to is None:
        typer.echo("--from and --to are required (YYYY-MM-DD)", err=True)
        _exit(EXIT_USAGE)

    try:
        ds_start = _date.fromisoformat(date_from)
        ds_end = _date.fromisoformat(date_to)
    except ValueError as exc:
        typer.echo(f"date parsing failed: {exc}", err=True)
        _exit(EXIT_USAGE)
        return  # pragma: no cover

    if ds_end < ds_start:
        typer.echo(f"--to ({ds_end}) is before --from ({ds_start})", err=True)
        _exit(EXIT_USAGE)

    # Build ReplayWindowInputs — same shape as spec-008's backtest CLI uses.
    try:
        replay_inputs = _build_replay_inputs(
            rules_path=rules,
            history_root=history_root,
            date_start=ds_start,
            date_end=ds_end,
            halt_path=halt_path,
            out_root=Path("data/backtest"),
        )
    except _CoverageHole as exc:
        typer.echo(f"historical dataset incomplete: {exc}", err=True)
        _exit(run_module.EXIT_COVERAGE)
        return
    except _CanaryUsageError as exc:
        typer.echo(str(exc), err=True)
        _exit(EXIT_USAGE)
        return

    # Build ShockInputs (US2) unless skipped.
    shock_inputs = None
    if not skip_shock:
        from auto_invest.canary.shock import ShockInputs

        shock_inputs = ShockInputs(
            rules_path=replay_inputs.rules_path,
            rules=replay_inputs.rules,
            ruleset_sha256=replay_inputs.ruleset_sha256,
            data_source=replay_inputs.data_source,
            caps=replay_inputs.caps,
            whitelist=replay_inputs.whitelist,
            halt_path=replay_inputs.halt_path,
            out_root=Path("data/backtest/shock"),
            today=ds_end,
            shocks_toml=shocks_toml,
        )

    run_id_uuid: uuid.UUID | None = None
    if canary_run_id is not None:
        try:
            run_id_uuid = uuid.UUID(canary_run_id)
        except ValueError as exc:
            typer.echo(f"--run-id must be a UUID: {exc}", err=True)
            _exit(EXIT_USAGE)

    options = CanaryOptions(
        tier=tier,  # type: ignore[arg-type]
        candidate_rev=candidate_rev,
        baseline_rev=baseline_rev,
        bands_path=bands_toml,
        out_root=out_root,
        audit_db_path=db_path,
        replay_inputs=replay_inputs,
        shock_inputs=shock_inputs,
        canary_run_id=run_id_uuid,
        hypothesis_seed=hypothesis_seed,
        hypothesis_iterations=hypothesis_iterations,
        skip_fuzz=skip_fuzz,
        dry_run=dry_run,
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        try:
            outcome = run_canary(options, audit_conn=conn)
        except CanaryBandsConfigError as exc:
            typer.echo(f"canary bands config error: {exc}", err=True)
            _exit(EXIT_INTERNAL)
            return
        except Exception as exc:  # noqa: BLE001 — last-resort forensic exit
            typer.echo(f"internal error: {exc!r}", err=True)
            traceback.print_exc(file=sys.stderr)
            _exit(EXIT_INTERNAL)
            return
    finally:
        conn.close()

    if dry_run:
        typer.echo(
            f"dry-run: canary_run_id={outcome.canary_run_id} would write under {out_root}"
        )
        _exit(EXIT_OK)
        return

    if outcome.outcome == "passed":
        typer.echo(f"CANARY_PASSED canary_run_id={outcome.canary_run_id}")
        if outcome.run_dir is not None:
            typer.echo(f"artefacts: {outcome.run_dir}")
        _exit(EXIT_OK)
    else:
        typer.echo(
            f"CANARY_FAILED canary_run_id={outcome.canary_run_id} "
            f"failing_metrics={outcome.failing_metrics}"
        )
        if outcome.run_dir is not None:
            typer.echo(f"artefacts: {outcome.run_dir}")
        _exit(EXIT_FAILED)


@app.command("shock")
def shock_cmd(
    rules: Path = typer.Option(..., "--rules"),
    history_root: Path = typer.Option(Path("data/history"), "--history-root"),
    halt_path: Path = typer.Option(Path("data/halt.flag"), "--halt-path"),
    db_path: Path = typer.Option(Path("data/auto_invest.db"), "--db"),
    out_root: Path = typer.Option(Path("data/backtest/shock"), "--out-dir"),
    shocks_toml: Path = typer.Option(None, "--shocks-toml"),
) -> None:
    """Synthetic-shock pass only — forensic debug aid.

    Useful when investigating a single adverse day; emits the same
    BACKTEST_* rows the full canary would, but does NOT emit
    CANARY_ENTERED / CANARY_PASSED. Returns 0 iff all shocks clean.
    """
    from datetime import date as _dt

    from auto_invest.canary.shock import (
        ShockInputs,
        run_synthetic_shock_battery,
    )

    try:
        replay_inputs = _build_replay_inputs(
            rules_path=rules,
            history_root=history_root,
            date_start=_dt.today(),
            date_end=_dt.today(),
            halt_path=halt_path,
            out_root=out_root,
        )
    except _CanaryUsageError as exc:
        typer.echo(str(exc), err=True)
        _exit(EXIT_USAGE)
        return

    inputs = ShockInputs(
        rules_path=replay_inputs.rules_path,
        rules=replay_inputs.rules,
        ruleset_sha256=replay_inputs.ruleset_sha256,
        data_source=replay_inputs.data_source,
        caps=replay_inputs.caps,
        whitelist=replay_inputs.whitelist,
        halt_path=replay_inputs.halt_path,
        out_root=out_root,
        today=_dt.today(),
        shocks_toml=shocks_toml,
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        result = run_synthetic_shock_battery(inputs, audit_conn=conn)
    finally:
        conn.close()
    typer.echo(
        f"shock_battery: resolved={len(result.resolved_dates)} "
        f"total_violations={result.total_violations} "
        f"skipped={result.skipped_count}"
    )
    _exit(EXIT_FAILED if result.total_violations > 0 else EXIT_OK)


@app.command("fuzz")
def fuzz_cmd(
    iterations: int = typer.Option(10_000, "--iterations"),
    seed: int = typer.Option(0, "--seed"),
    out_dir: Path = typer.Option(None, "--out-dir"),
) -> None:
    """Property-fuzz pass only — forensic debug aid for risk/gates.py."""
    from auto_invest.canary.fuzz import run_fuzz_pass
    from auto_invest.canary.report import write_fuzz_artefacts

    result = run_fuzz_pass(iterations=iterations, database_seed=seed)
    typer.echo(
        f"fuzz: iterations={result.iterations} "
        f"counterexamples={len(result.counterexamples)}"
    )
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        write_fuzz_artefacts(
            canary_run_dir=out_dir,
            counterexamples=result.counterexamples,
            seeds=[seed],
        )
    _exit(EXIT_FAILED if result.counterexamples else EXIT_OK)


# ---------------------------------------------------------- helpers


class _CoverageHole(RuntimeError):
    pass


class _CanaryUsageError(RuntimeError):
    pass


def _build_replay_inputs(
    *,
    rules_path: Path,
    history_root: Path,
    date_start: _date,
    date_end: _date,
    halt_path: Path,
    out_root: Path,
) -> ReplayWindowInputs:
    """Resolve dataset + load rules + build ReplayWindowInputs.

    Mirrors spec-008's CLI dataset-resolution pattern so the canary
    inherits identical coverage-hole semantics.
    """
    from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
    from auto_invest.cli import (
        _load_rules_for_backtest,
        _require_clean_migrations,
    )

    latest = latest_dataset_dir(history_root)
    if latest is None:
        raise _CanaryUsageError(
            f"no ingested datasets under {history_root}; "
            "run `auto-invest ingest-history` first"
        )

    data_source = CSVDataSource(latest)
    symbols = list(data_source.list_symbols())
    holes = data_source.coverage_holes(symbols, date_start, date_end)
    if holes:
        sample = ", ".join(f"{s} {d.isoformat()}" for s, d in holes[:5])
        more = f" (+{len(holes) - 5} more)" if len(holes) > 5 else ""
        raise _CoverageHole(f"missing bars: {sample}{more}")

    try:
        caps, whitelist, parsed_rules, ruleset_sha256 = _load_rules_for_backtest(
            rules_path
        )
    except Exception as exc:  # noqa: BLE001 — surface as usage error
        raise _CanaryUsageError(f"rules load failed: {exc}") from exc

    return ReplayWindowInputs(
        rules_path=rules_path,
        rules=parsed_rules,
        ruleset_sha256=ruleset_sha256,
        data_source=data_source,
        date_start=date_start,
        date_end=date_end,
        caps=caps,
        whitelist=whitelist,
        halt_path=halt_path,
        out_root=out_root,
    )


def _exit(code: int) -> None:
    """Indirection so tests can monkeypatch sys.exit if needed."""
    sys.exit(code)


def main() -> None:
    """Module entrypoint for ``python -m auto_invest.canary``."""
    app()


if __name__ == "__main__":
    main()
