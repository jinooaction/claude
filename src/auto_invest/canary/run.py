"""Top-level canary orchestration (T017).

``run_canary(options)`` is the single entrypoint that ties the canary
harness together. It is called by the CLI (``python -m auto_invest.canary
run``) and by future consumers (spec 005 tuner, spec 006 deploy runner
reading audit-log outcomes).

Sequence (per spec.md US1 + data-model.md state machine):

  1. Resolve candidate-rev + baseline-rev via ``diff.resolve_rev`` /
     ``diff.resolve_baseline``.
  2. Compute kernel-touch diff via ``diff.diff_paths`` +
     ``diff.intersect_kernel``.
  3. Emit ``CANARY_ENTERED`` (bands snapshot captured).
  4. If kernel-touch list non-empty: emit ``CANARY_KERNEL_TOUCH_DETECTED``
     (R-C8 — forensic callout, NOT a halt under v3.0.0 IX.A).
  5. Call ``replay_window.replay_window`` to drive spec 008's backtest
     engine for the window.
  6. (US2 wires:) call ``shock.run_synthetic_shock_battery`` and
     ``fuzz.run_fuzz_pass``. Phase 3 US1 stubs both to zero contributions.
  7. Evaluate the 5-metric battery via ``metrics.evaluate_metrics``.
  8. Decide outcome (all-or-nothing per FR-C06).
  9. Write the canary artefact tree via ``report.write_report``.
  10. Emit ``CANARY_PASSED`` or ``CANARY_FAILED`` (artefact_path included).
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from auto_invest.canary.bands import DEFAULT_PATH as DEFAULT_BANDS_PATH
from auto_invest.canary.bands import load_bands
from auto_invest.canary.data_model import (
    CanaryMetrics,
    CanaryRun,
    KernelTouch,
    SeedBundle,
    Tier,
)
from auto_invest.canary.diff import (
    diff_paths,
    intersect_kernel,
    resolve_baseline,
    resolve_rev,
)
from auto_invest.canary.metrics import evaluate_metrics
from auto_invest.canary.replay_window import (
    ReplayWindowInputs,
    WindowReplayResult,
    replay_window,
)
from auto_invest.canary.report import copy_window_artefact, write_report
from auto_invest.deploy import load_kernel_manifest
from auto_invest.persistence import audit
from auto_invest.persistence.audit import (
    CanaryEnteredPayload,
    CanaryFailedPayload,
    CanaryKernelTouchDetectedPayload,
    CanaryPassedPayload,
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_COVERAGE = 2
EXIT_INTERNAL = 3
EXIT_USAGE = 4


@dataclass(frozen=True)
class CanaryOptions:
    """Inputs for a canary run (Phase 3 US1 surface)."""

    tier: Tier
    candidate_rev: str | None = None  # default: HEAD
    baseline_rev: str | None = None  # default: most-recent CANARY_PASSED, fallback origin/main
    window_trading_days: int | None = None  # default: bands[tier].trading_days
    bands_path: Path = DEFAULT_BANDS_PATH
    out_root: Path = Path("data/canary")
    audit_db_path: Path = Path("data/auto_invest.db")
    replay_inputs: ReplayWindowInputs | None = None  # injected by CLI
    repo_root: Path | None = None  # default: cwd
    canary_run_id: uuid.UUID | None = None  # default: uuid4
    hypothesis_seed: int | None = None
    hypothesis_iterations: int = 10_000
    dry_run: bool = False


@dataclass(frozen=True)
class CanaryRunOutcome:
    """What ``run_canary`` returns. CLI maps to sys.exit."""

    canary_run_id: uuid.UUID
    exit_code: int
    outcome: Literal["passed", "failed", "in_progress"]
    run_dir: Path | None
    failing_metrics: list[str] = field(default_factory=list)
    kernel_touches: list[KernelTouch] = field(default_factory=list)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"


def _bands_snapshot(bands_value) -> dict[str, object]:
    return {
        "trading_days": bands_value.trading_days,
        "pnl_drawdown_pct": bands_value.pnl_drawdown_pct,
        "risk_gate_violations": bands_value.risk_gate_violations,
        "audit_integrity_failures": bands_value.audit_integrity_failures,
        "latency_p95_regression_pct": bands_value.latency_p95_regression_pct,
        "llm_cost_regression_pct": bands_value.llm_cost_regression_pct,
    }


def _derive_seed(canary_run_id: uuid.UUID, override: int | None) -> int:
    if override is not None:
        return override
    return int.from_bytes(canary_run_id.bytes[:8], "big", signed=False)


def _resolve_revs(
    *,
    candidate_rev_in: str | None,
    baseline_rev_in: str | None,
    audit_conn: sqlite3.Connection,
    cwd: Path,
) -> tuple[str, str]:
    candidate = resolve_rev(candidate_rev_in or "HEAD", cwd=cwd)
    if baseline_rev_in is not None:
        baseline = resolve_rev(baseline_rev_in, cwd=cwd)
    else:
        baseline = resolve_baseline(
            audit_conn=audit_conn,
            candidate_rev=candidate,
            cwd=cwd,
        )
    return candidate, baseline


def _decide_outcome(
    metrics: CanaryMetrics,
) -> tuple[Literal["passed", "failed"], list[str]]:
    failing = metrics.failing_metric_ids()
    if not failing:
        return "passed", []
    return "failed", failing


def run_canary(
    options: CanaryOptions,
    *,
    audit_conn: sqlite3.Connection,
) -> CanaryRunOutcome:
    """Orchestrate one canary run."""

    started_at = _utcnow()
    cwd = options.repo_root or Path.cwd()

    # ---------------- bands -----------------
    bands_map = load_bands(options.bands_path)
    if options.tier not in bands_map:
        raise ValueError(
            f"tier {options.tier!r} not present in {options.bands_path}; "
            f"available: {sorted(bands_map.keys())}"
        )
    tier_bands = bands_map[options.tier]
    window_days = options.window_trading_days or tier_bands.trading_days

    # ---------------- revs ------------------
    candidate_rev, baseline_rev = _resolve_revs(
        candidate_rev_in=options.candidate_rev,
        baseline_rev_in=options.baseline_rev,
        audit_conn=audit_conn,
        cwd=cwd,
    )

    canary_run_id = options.canary_run_id or uuid.uuid4()

    if options.dry_run:
        return CanaryRunOutcome(
            canary_run_id=canary_run_id,
            exit_code=EXIT_OK,
            outcome="in_progress",
            run_dir=None,
        )

    # ---------------- kernel touch ----------
    touched = diff_paths(
        baseline_sha=baseline_rev,
        candidate_sha=candidate_rev,
        cwd=cwd,
    )
    kernel_touches = intersect_kernel(touched, manifest=load_kernel_manifest())

    # ---------------- window dates ----------
    # The canary's "window" is the most recent N trading days the
    # operator has historical data for. The spec-008 RunOptions take
    # date_start / date_end; the orchestrator delegates that resolution
    # to the caller (CLI) — replay_inputs MUST be provided OR the run
    # is aborted with EXIT_USAGE.
    if options.replay_inputs is None:
        raise ValueError(
            "CanaryOptions.replay_inputs is required for Phase 3 US1 — the CLI"
            " supplies it; library callers must construct ReplayWindowInputs"
            " directly."
        )

    window_start = options.replay_inputs.date_start
    window_end = options.replay_inputs.date_end

    # ---------------- audit ENTERED ----------
    audit.append(
        audit_conn,
        CanaryEnteredPayload(
            canary_run_id=str(canary_run_id),
            candidate_rev=candidate_rev,
            baseline_rev=baseline_rev,
            tier=options.tier,
            window_trading_days=window_days,
            window_start_date=window_start.isoformat(),
            window_end_date=window_end.isoformat(),
            bands_snapshot=_bands_snapshot(tier_bands),
        ),
        correlation_id=str(canary_run_id),
        ts_utc=_to_iso(started_at),
    )

    # ---------------- kernel-touch row (R-C8) ----------
    if kernel_touches:
        audit.append(
            audit_conn,
            CanaryKernelTouchDetectedPayload(
                canary_run_id=str(canary_run_id),
                candidate_rev=candidate_rev,
                touched_groups=[t.group for t in kernel_touches],
                touched_files=sorted(
                    {f for t in kernel_touches for f in t.files}
                ),
            ),
            correlation_id=str(canary_run_id),
            ts_utc=_to_iso(_utcnow()),
        )

    # ---------------- window replay ----------
    window: WindowReplayResult = replay_window(
        options.replay_inputs,
        audit_conn=audit_conn,
    )
    audit_conn.commit()

    candidate_drawdown_pct = 0.0
    if window.candidate.summary is not None:
        candidate_drawdown_pct = float(window.candidate.summary.aggregate_max_drawdown_pct)

    # ---------------- shock + fuzz (US2 plugs in here) ----------
    shock_violations = 0
    fuzz_counterexamples = 0
    # In Phase 3 US1 these stay 0; Phase 4 US2 will wire shock.py + fuzz.py.

    # ---------------- metrics ----------
    metrics = evaluate_metrics(
        candidate_drawdown_pct=candidate_drawdown_pct,
        audit_integrity_count=window.audit_integrity_count,
        shock_risk_gate_violations=shock_violations,
        fuzz_counterexample_count=fuzz_counterexamples,
        bands=tier_bands,
    )

    outcome, failing = _decide_outcome(metrics)

    # ---------------- build CanaryRun ----------
    seed_bundle = SeedBundle(
        hypothesis_database_seed=_derive_seed(canary_run_id, options.hypothesis_seed),
        hypothesis_iterations=options.hypothesis_iterations,
        synthetic_shock_dates=[],  # US2 populates from spec 008 resolver
        quarterly_opex_resolved_for=date.today(),  # placeholder, US2 replaces
    )

    finished_at = _utcnow()
    run = CanaryRun(
        canary_run_id=canary_run_id,
        candidate_rev=candidate_rev,
        baseline_rev=baseline_rev,
        tier=options.tier,
        window_trading_days=window_days,
        window_start_date=window_start,
        window_end_date=window_end,
        started_at=started_at,
        finished_at=finished_at,
        outcome=outcome,
        failing_metrics=failing,
        kernel_touches=kernel_touches,
        metrics=metrics,
        seed_bundle=seed_bundle,
    )

    # ---------------- write artefact tree ----------
    canary_run_dir = write_report(run, options.out_root)

    # Copy spec-008 window backtest artefacts under replay-window/{candidate,baseline}/.
    if window.candidate_run_outcome.run_dir.exists():
        copy_window_artefact(
            source_run_dir=window.candidate_run_outcome.run_dir,
            canary_run_dir=canary_run_dir,
            side="candidate",
        )
    if window.baseline_run_outcome.run_dir.exists():
        copy_window_artefact(
            source_run_dir=window.baseline_run_outcome.run_dir,
            canary_run_dir=canary_run_dir,
            side="baseline",
        )

    artefact_path = str(canary_run_dir / "canary-run.json")

    # ---------------- terminal audit row ----------
    finished_iso = _to_iso(finished_at)
    if outcome == "passed":
        audit.append(
            audit_conn,
            CanaryPassedPayload(
                canary_run_id=str(canary_run_id),
                candidate_rev=candidate_rev,
                baseline_rev=baseline_rev,
                tier=options.tier,
                finished_at=finished_iso,
                artefact_path=artefact_path,
            ),
            correlation_id=str(canary_run_id),
            ts_utc=finished_iso,
        )
        exit_code = EXIT_OK
    else:
        audit.append(
            audit_conn,
            CanaryFailedPayload(
                canary_run_id=str(canary_run_id),
                candidate_rev=candidate_rev,
                baseline_rev=baseline_rev,
                tier=options.tier,
                finished_at=finished_iso,
                failing_metrics=sorted(failing),
                artefact_path=artefact_path,
            ),
            correlation_id=str(canary_run_id),
            ts_utc=finished_iso,
        )
        exit_code = EXIT_FAILED
    audit_conn.commit()

    return CanaryRunOutcome(
        canary_run_id=canary_run_id,
        exit_code=exit_code,
        outcome=outcome,
        run_dir=canary_run_dir,
        failing_metrics=failing,
        kernel_touches=kernel_touches,
    )


__all__ = [
    "EXIT_FAILED",
    "EXIT_INTERNAL",
    "EXIT_OK",
    "EXIT_USAGE",
    "CanaryOptions",
    "CanaryRunOutcome",
    "run_canary",
]
