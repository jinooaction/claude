"""Top-level backtest orchestration (T025).

`run_backtest(options, *, conn)` is the single entrypoint that ties the
backtest engine together. It is called by the CLI (`auto-invest
backtest`, T026) and by spec 007's hardened canary harness when it ships.

Sequence (per data-model.md § BacktestRun lifecycle + contracts/backtest-cli.md):

  1. kernel pre-flight (FR-B12) — if any Kernel path has uncommitted
     edits AND --allow-kernel-edits was NOT set:
       - emit ERROR audit row reason=BACKTEST_BLOCKED_KERNEL_TOUCH
       - write minimal backtest-run.json (status=failed) for forensics
       - return exit 78
  2. compute kernel_guard_report (snapshot of kernel.toml SHA-256 at run start)
  3. set BACKTEST_MODE=1 so any future AnthropicClient construction inside
     replay raises BacktestJudgmentLeakError (FR-B08 defense-in-depth)
  4. enter wall_clock_guard() — any datetime.now() / time.time() call
     inside auto_invest.* during replay raises WallClockLeakError
  5. emit BACKTEST_STARTED audit row
  6. call replay() (Path B per R-B13)
  7. emit BACKTEST_COMPLETED audit row with summary aggregates
  8. write_report() — writes the per-run artefact tree
  9. return exit 0

Exit codes match contracts/backtest-cli.md:

    0  — success
    66 — dataset coverage incomplete (caller MAY pre-check; run also detects)
    77 — wall-clock leak mid-run (WallClockLeakError)
    78 — kernel-touched + no --allow-kernel-edits
    79 — BACKTEST_JUDGMENT_LEAK (real LLM client constructed under BACKTEST_MODE=1)
    80 — BACKTEST_LIVE_BROKER_LEAK (non-mock adapter reached the router)
    81 — run_id collision (skipped in v1 since uuid4 collisions are negligible)

Every error branch STILL writes `backtest-run.json` with status=failed and
failure_reason populated so the operator has a forensic record.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.deploy import load_kernel_manifest
from auto_invest.persistence import audit
from auto_invest.persistence.audit import (
    BacktestCompletedPayload,
    BacktestStartedPayload,
    ErrorPayload,
)

from .broker_mock import BacktestBroker, BacktestLiveBrokerLeakError
from .clock import ReplayClock, WallClockLeakError, wall_clock_guard
from .data_model import BacktestRun, canonicalise_decimal
from .data_source import HistoricalDataSource
from .judgment_stub import BACKTEST_MODE_ENV, BacktestJudgmentLeakError
from .kernel_pre_flight import PreFlightResult, run_pre_flight
from .replay import DEFAULT_TOTAL_CAPITAL_USD, ReplayResult, replay
from .report import KernelGuardReport, build_per_rule_results, build_summary, write_report

EXIT_OK = 0
EXIT_COVERAGE = 66
EXIT_WALL_CLOCK_LEAK = 77
EXIT_KERNEL_TOUCHED = 78
EXIT_JUDGMENT_LEAK = 79
EXIT_LIVE_BROKER_LEAK = 80


@dataclass(frozen=True)
class RunOptions:
    """Inputs for a single backtest run."""

    rules_path: Path
    rules: Sequence[TradingRule]
    ruleset_sha256: str
    data_source: HistoricalDataSource
    date_start: date
    date_end: date
    caps: SizingCaps
    whitelist: Whitelist
    halt_path: Path
    out_root: Path
    invoker: Literal["cli", "canary"] = "cli"
    replay_seed: int = 0
    synthetic_shock: bool = False
    allow_kernel_edits: bool = False
    total_capital_usd: Decimal = DEFAULT_TOTAL_CAPITAL_USD
    chmod_readonly: bool = True
    repo_root: Path | None = None
    pre_flight_result: PreFlightResult | None = None  # injected by tests


@dataclass(frozen=True)
class RunOutcome:
    """What `run_backtest` returned. CLI inspects `exit_code` for sys.exit."""

    run_id: str
    exit_code: int
    run_dir: Path
    failure_reason: str | None = None
    summary_aggregate_return_pct: str | None = None
    summary_aggregate_max_drawdown_pct: str | None = None
    summary_aggregate_sharpe: str | None = None
    total_orders: int = 0
    total_fills: int = 0
    total_gate_rejections: int = 0
    kernel_touched_paths: list[str] = field(default_factory=list)


# ---------- helpers --------------------------------------------------------


def _new_run_id() -> str:
    """UUIDv4 hex — data-model.md says UUIDv7 but uuid4 is sufficient v1.

    v1 collision risk: 2^-122 per run; the spec's exit-81 path is reserved
    for a future v2 that switches to uuid7 (sortable). uuid4 hex preserves
    the printable shape `0193b8c4-...`-equivalent so artefact paths look right.
    """
    return uuid.uuid4().hex


def _compute_kernel_manifest_sha256(repo_root: Path | None) -> str:
    """SHA-256 of `.specify/memory/kernel.toml` AT RUN START.

    Pinned in `backtest-run.json` so future kernel changes do not
    retroactively invalidate forensic claims (contracts/backtest-run-json.md
    § kernel_guard_report block).
    """
    base = repo_root or Path.cwd()
    manifest_path = base / ".specify" / "memory" / "kernel.toml"
    if not manifest_path.exists():
        return ""
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _checked_kernel_paths(repo_root: Path | None) -> list[str]:
    """Flatten every kernel-listed path for the run.json snapshot."""
    base = repo_root or Path.cwd()
    manifest_path = base / ".specify" / "memory" / "kernel.toml"
    try:
        manifest = load_kernel_manifest(manifest_path if manifest_path.exists() else None)
    except Exception:  # noqa: BLE001 — best-effort forensic field
        return []
    return sorted(set(manifest.all_paths))


def _utcnow() -> datetime:
    """Wall-clock read — only called OUTSIDE the wall_clock_guard scope."""
    return datetime.now(UTC)


def _to_iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"


def _failure_run(
    *,
    options: RunOptions,
    run_id: str,
    start_ts: datetime,
    end_ts: datetime,
    status: Literal["failed"],
    failure_reason: str,
    dataset_version: str,
) -> BacktestRun:
    return BacktestRun(
        run_id=run_id,
        invoker=options.invoker,
        ruleset_path=options.rules_path,
        ruleset_sha256=options.ruleset_sha256,
        dataset_version=dataset_version,
        date_start=options.date_start,
        date_end=options.date_end,
        replay_seed=options.replay_seed,
        synthetic_shock=options.synthetic_shock,
        start_ts=start_ts,
        end_ts=end_ts,
        status=status,
    )


def _emit_completed(
    *,
    conn: sqlite3.Connection,
    run_id: str,
    outcome: Literal["completed", "failed"],
    failure_reason: str | None,
    result: ReplayResult | None,
    ts_iso: str,
    aggregate_return_pct: Decimal = Decimal("0"),
    aggregate_max_drawdown_pct: Decimal = Decimal("0"),
    aggregate_sharpe: Decimal = Decimal("0"),
) -> None:
    audit.append(
        conn,
        BacktestCompletedPayload(
            run_id=run_id,
            outcome=outcome,
            failure_reason=failure_reason,
            aggregate_return_pct=canonicalise_decimal(aggregate_return_pct),
            aggregate_max_drawdown_pct=canonicalise_decimal(aggregate_max_drawdown_pct),
            aggregate_sharpe=canonicalise_decimal(aggregate_sharpe),
            total_orders=result.total_orders if result else 0,
            total_fills=result.total_fills if result else 0,
            total_gate_rejections=result.total_gate_rejections if result else 0,
        ),
        correlation_id=run_id,
        ts_utc=ts_iso,
    )


# ---------- main entrypoint -----------------------------------------------


def run_backtest(options: RunOptions, *, conn: sqlite3.Connection) -> RunOutcome:
    run_id = _new_run_id()
    start_ts = _utcnow()
    start_iso = _to_iso(start_ts)

    # (1) Kernel pre-flight.
    pre_flight = options.pre_flight_result or run_pre_flight(repo_root=options.repo_root)
    kernel_guard_report = KernelGuardReport(
        touched=pre_flight.touched,
        checked_paths=_checked_kernel_paths(options.repo_root),
        manifest_sha256=_compute_kernel_manifest_sha256(options.repo_root),
    )

    if pre_flight.touched and not options.allow_kernel_edits:
        reason = (
            f"working tree has uncommitted Kernel modifications: {pre_flight.paths!r}"
        )
        audit.append(
            conn,
            ErrorPayload(
                where="backtest.run.pre_flight",
                message=f"BACKTEST_BLOCKED_KERNEL_TOUCH: {reason}",
            ),
            correlation_id=run_id,
            ts_utc=start_iso,
        )
        end_ts = _utcnow()
        failed_run = _failure_run(
            options=options,
            run_id=run_id,
            start_ts=start_ts,
            end_ts=end_ts,
            status="failed",
            failure_reason=reason,
            dataset_version=options.data_source.dataset_version,
        )
        run_dir = _write_failure_report(
            run=failed_run,
            kernel_guard_report=kernel_guard_report,
            out_root=options.out_root,
            chmod_readonly=options.chmod_readonly,
        )
        _emit_completed(
            conn=conn,
            run_id=run_id,
            outcome="failed",
            failure_reason=reason,
            result=None,
            ts_iso=_to_iso(end_ts),
        )
        return RunOutcome(
            run_id=run_id,
            exit_code=EXIT_KERNEL_TOUCHED,
            run_dir=run_dir,
            failure_reason=reason,
            kernel_touched_paths=list(pre_flight.paths),
        )

    # (2) Activate BACKTEST_MODE so guard_no_real_llm() fires inside replay.
    prior_env = os.environ.get(BACKTEST_MODE_ENV)
    os.environ[BACKTEST_MODE_ENV] = "1"

    # (3) BACKTEST_STARTED row.
    audit.append(
        conn,
        BacktestStartedPayload(
            run_id=run_id,
            invoker=options.invoker,
            ruleset_sha256=options.ruleset_sha256,
            dataset_version=options.data_source.dataset_version,
            date_start=options.date_start.isoformat(),
            date_end=options.date_end.isoformat(),
            replay_seed=options.replay_seed,
            fill_model="pessimistic_zero_slip",
            judgment_mode="stub",
            synthetic_shock=options.synthetic_shock,
        ),
        correlation_id=run_id,
        ts_utc=start_iso,
    )

    broker = BacktestBroker()
    # ReplayClock starts BEFORE the first bar so the replay can advance to
    # each bar's session_close without rewinding. The wall-clock `start_ts`
    # is only used in the audit-log header — it is NOT what the engine reads.
    clock = ReplayClock(datetime.combine(options.date_start, datetime.min.time(), UTC))

    failure_reason: str | None = None
    exit_code = EXIT_OK
    result: ReplayResult | None = None

    try:
        with wall_clock_guard():
            result = replay(
                rules=list(options.rules),
                data_source=options.data_source,
                date_start=options.date_start,
                date_end=options.date_end,
                caps=options.caps,
                whitelist=options.whitelist,
                halt_path=options.halt_path,
                conn=conn,
                clock=clock,
                broker=broker,
                run_id=run_id,
                total_capital_usd=options.total_capital_usd,
            )
    except WallClockLeakError as exc:
        failure_reason = f"WALL_CLOCK_LEAK: {exc}"
        exit_code = EXIT_WALL_CLOCK_LEAK
        audit.append(
            conn,
            ErrorPayload(where="backtest.replay", message=failure_reason),
            correlation_id=run_id,
            ts_utc=_to_iso(_utcnow()),
        )
    except BacktestJudgmentLeakError as exc:
        failure_reason = f"BACKTEST_JUDGMENT_LEAK: {exc}"
        exit_code = EXIT_JUDGMENT_LEAK
        audit.append(
            conn,
            ErrorPayload(where="backtest.replay", message=failure_reason),
            correlation_id=run_id,
            ts_utc=_to_iso(_utcnow()),
        )
    except BacktestLiveBrokerLeakError as exc:
        failure_reason = f"BACKTEST_LIVE_BROKER_LEAK: {exc}"
        exit_code = EXIT_LIVE_BROKER_LEAK
        audit.append(
            conn,
            ErrorPayload(where="backtest.replay", message=failure_reason),
            correlation_id=run_id,
            ts_utc=_to_iso(_utcnow()),
        )
    finally:
        _restore_env(BACKTEST_MODE_ENV, prior_env)

    end_ts = _utcnow()
    end_iso = _to_iso(end_ts)

    if exit_code == EXIT_OK and result is not None:
        # Successful path: build summary and write the full artefact tree.
        per_rule = build_per_rule_results(result)
        summary = build_summary(result, per_rule)
        run = BacktestRun(
            run_id=run_id,
            invoker=options.invoker,
            ruleset_path=options.rules_path,
            ruleset_sha256=options.ruleset_sha256,
            dataset_version=options.data_source.dataset_version,
            date_start=options.date_start,
            date_end=options.date_end,
            replay_seed=options.replay_seed,
            synthetic_shock=options.synthetic_shock,
            start_ts=start_ts,
            end_ts=end_ts,
            status="completed",
            summary=summary,
        )
        run_dir = write_report(
            run=run,
            result=result,
            kernel_guard_report=kernel_guard_report,
            out_root=options.out_root,
            chmod_readonly=options.chmod_readonly,
        )
        _emit_completed(
            conn=conn,
            run_id=run_id,
            outcome="completed",
            failure_reason=None,
            result=result,
            ts_iso=end_iso,
            aggregate_return_pct=summary.aggregate_return_pct,
            aggregate_max_drawdown_pct=summary.aggregate_max_drawdown_pct,
            aggregate_sharpe=summary.aggregate_sharpe,
        )
        return RunOutcome(
            run_id=run_id,
            exit_code=EXIT_OK,
            run_dir=run_dir,
            summary_aggregate_return_pct=canonicalise_decimal(summary.aggregate_return_pct),
            summary_aggregate_max_drawdown_pct=canonicalise_decimal(
                summary.aggregate_max_drawdown_pct
            ),
            summary_aggregate_sharpe=canonicalise_decimal(summary.aggregate_sharpe),
            total_orders=result.total_orders,
            total_fills=result.total_fills,
            total_gate_rejections=result.total_gate_rejections,
        )

    # Failure path: still write a backtest-run.json for forensics.
    failed_run = _failure_run(
        options=options,
        run_id=run_id,
        start_ts=start_ts,
        end_ts=end_ts,
        status="failed",
        failure_reason=failure_reason or "unknown failure",
        dataset_version=options.data_source.dataset_version,
    )
    run_dir = _write_failure_report(
        run=failed_run,
        kernel_guard_report=kernel_guard_report,
        out_root=options.out_root,
        chmod_readonly=options.chmod_readonly,
    )
    _emit_completed(
        conn=conn,
        run_id=run_id,
        outcome="failed",
        failure_reason=failure_reason,
        result=result,
        ts_iso=end_iso,
    )
    return RunOutcome(
        run_id=run_id,
        exit_code=exit_code,
        run_dir=run_dir,
        failure_reason=failure_reason,
        total_orders=result.total_orders if result else 0,
        total_fills=result.total_fills if result else 0,
        total_gate_rejections=result.total_gate_rejections if result else 0,
    )


# ---------- failure-path artefact writer ----------------------------------


def _write_failure_report(
    *,
    run: BacktestRun,
    kernel_guard_report: KernelGuardReport,
    out_root: Path,
    chmod_readonly: bool,
) -> Path:
    """Write a minimal artefact tree on failure: just backtest-run.json + _meta.

    metrics.csv and per-rule artefacts are skipped (no summary to compute);
    the JSON's `status` field carries `failed` and `summary` is null, so the
    operator can spot the failure quickly via `cat backtest-run.json`.
    """
    from .report import _write_json  # local import — keep private helper close

    run_dir = out_root / run.run_id
    meta_dir = run_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_id": run.run_id,
        "invoker": run.invoker,
        "ruleset_path": str(run.ruleset_path),
        "ruleset_sha256": run.ruleset_sha256,
        "dataset_version": run.dataset_version,
        "date_start": run.date_start.isoformat(),
        "date_end": run.date_end.isoformat(),
        "replay_seed": run.replay_seed,
        "fill_model": run.fill_model,
        "judgment_mode": run.judgment_mode,
        "synthetic_shock": run.synthetic_shock,
        "start_ts": run.start_ts.isoformat(),
        "end_ts": run.end_ts.isoformat() if run.end_ts is not None else None,
        "status": run.status,
        "summary": None,
        "kernel_guard_report": {
            "touched": kernel_guard_report.touched,
            "checked_paths": list(kernel_guard_report.checked_paths),
            "manifest_sha256": kernel_guard_report.manifest_sha256,
        },
    }
    _write_json(run_dir / "backtest-run.json", payload)
    _write_json(
        meta_dir / "kernel-guard-report.json",
        {
            "touched": kernel_guard_report.touched,
            "checked_paths": list(kernel_guard_report.checked_paths),
            "manifest_sha256": kernel_guard_report.manifest_sha256,
        },
    )
    if chmod_readonly and os.name == "posix":
        from .report import _chmod_tree_readonly  # private helper, same module group

        _chmod_tree_readonly(run_dir)
    return run_dir


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        with suppress(KeyError):
            del os.environ[key]
    else:
        os.environ[key] = value


__all__ = [
    "EXIT_COVERAGE",
    "EXIT_JUDGMENT_LEAK",
    "EXIT_KERNEL_TOUCHED",
    "EXIT_LIVE_BROKER_LEAK",
    "EXIT_OK",
    "EXIT_WALL_CLOCK_LEAK",
    "RunOptions",
    "RunOutcome",
    "run_backtest",
]
