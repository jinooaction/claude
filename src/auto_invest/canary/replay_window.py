"""Window replay — drives a single backtest pass for the canary (T012).

v1 simplification (per research.md "Out of scope" — replay-only):

The canary's metric battery needs at minimum ONE backtest run of the
candidate code over the ≥30/≥45-trading-day window. The Δ-style
metrics (latency_p95_regression, llm_cost_regression) compare the
candidate against a "previous version"; in v1 there is no separate
process running the baseline rev's code, so Δ metrics resolve to 0
(trivially inside band). A future v2 will use git worktrees +
subprocess to honestly run two revs and compute non-zero deltas.

The LOAD-BEARING canary signals in v1 are:

  - ``pnl_drawdown_pct``    — from BacktestRun.summary.aggregate_max_drawdown_pct
  - ``audit_integrity_failures`` — count of DATA_QUALITY_ISSUE rows during replay
  - ``risk_gate_violations`` — from synthetic-shock pass (US2, FR-C03)
  - property fuzz on K1     — from fuzz pass (US2, FR-C04)

The latency / cost regression metrics are kept in the API for v2 but
are computed as 0.0 in v1 with ``source="telemetry_unused"`` so the
artefact tree carries the contract shape.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from auto_invest.backtest.data_model import BacktestRun
from auto_invest.backtest.data_source import HistoricalDataSource
from auto_invest.backtest.run import RunOptions, RunOutcome, run_backtest
from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist


@dataclass(frozen=True)
class WindowReplayResult:
    """What the window-replay step returns to the orchestrator.

    Carries both the candidate and baseline ``BacktestRun`` summaries
    (in v1, the same object) plus the data-quality-warning count used
    by the audit-integrity metric and the on-disk paths to the
    underlying spec-008 artefacts so the canary report writer can
    copy/symlink them into ``data/canary/<run_id>/replay-window/{candidate,baseline}/``.
    """

    candidate: BacktestRun
    baseline: BacktestRun
    candidate_run_outcome: RunOutcome
    baseline_run_outcome: RunOutcome
    audit_integrity_count: int


@dataclass(frozen=True)
class ReplayWindowInputs:
    """Inputs the orchestrator needs to call ``run_backtest`` for the canary."""

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


def _build_options(inputs: ReplayWindowInputs) -> RunOptions:
    return RunOptions(
        rules_path=inputs.rules_path,
        rules=inputs.rules,
        ruleset_sha256=inputs.ruleset_sha256,
        data_source=inputs.data_source,
        date_start=inputs.date_start,
        date_end=inputs.date_end,
        caps=inputs.caps,
        whitelist=inputs.whitelist,
        halt_path=inputs.halt_path,
        out_root=inputs.out_root,
        invoker="canary",
        replay_seed=0,
        synthetic_shock=False,
        # The canary does its OWN kernel-touch detection against the
        # candidate-vs-baseline diff (R-C7), then emits
        # CANARY_KERNEL_TOUCH_DETECTED. Spec 008's working-tree
        # pre-flight is redundant here AND would halt every canary run
        # because the operator's working tree is rarely empty when
        # invoking the canary. Under v3.0.0 IX.A the Kernel is a
        # forensic-attention list, not a halt; bypassing 008's working-
        # tree check honours the v3.0.0 semantics at the canary boundary.
        allow_kernel_edits=True,
    )


def _load_backtest_run_json(run_dir: Path) -> dict[str, Any]:
    import json

    path = run_dir / "backtest-run.json"
    if not path.exists():
        raise FileNotFoundError(f"backtest-run.json missing under {run_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def _backtest_run_from_dir(run_dir: Path) -> BacktestRun:
    """Parse spec 008's `backtest-run.json` back into the in-memory model.

    The on-disk JSON carries extra fields like ``kernel_guard_report``
    that the report writer adds but ``BacktestRun`` itself does not
    declare. Strip unknown keys before validation; the canary only
    needs the BacktestRun core fields.
    """
    data = _load_backtest_run_json(run_dir)
    allowed = set(BacktestRun.model_fields.keys())
    pruned = {k: v for k, v in data.items() if k in allowed}
    return BacktestRun.model_validate(pruned)


def _count_audit_integrity(run: BacktestRun, run_dir: Path) -> int:
    """Per FR-C01 #3 — count data-quality issues observed during replay.

    Spec 008 surfaces data-quality warnings either in
    ``BacktestRun.summary.data_quality_warnings`` (when the model is fully
    populated) or as a top-level ``summary.data_quality_warnings`` array
    in ``backtest-run.json``. The on-disk JSON is canonical for v1
    because the in-memory ``BacktestRun.summary`` is None after the
    pruned validate above.
    """
    data = _load_backtest_run_json(run_dir)
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return 0
    warnings = summary.get("data_quality_warnings", [])
    if not isinstance(warnings, list):
        return 0
    return len(warnings)


def replay_window(
    inputs: ReplayWindowInputs,
    *,
    audit_conn: sqlite3.Connection,
) -> WindowReplayResult:
    """Run a single backtest over the canary window and return its summary twice.

    In v1, the candidate and baseline backtest summaries are the SAME
    `BacktestRun` (same on-disk artefact, same numbers). The metric
    evaluator's Δ-style metrics therefore resolve to 0.0. A future v2
    will run two backtests under git-worktrees to compute honest deltas;
    the WindowReplayResult shape already supports that, so v2 is a
    drop-in replacement for this function.
    """

    options = _build_options(inputs)
    outcome = run_backtest(options, conn=audit_conn)
    run = _backtest_run_from_dir(outcome.run_dir)
    integrity_count = _count_audit_integrity(run, outcome.run_dir)
    return WindowReplayResult(
        candidate=run,
        baseline=run,
        candidate_run_outcome=outcome,
        baseline_run_outcome=outcome,
        audit_integrity_count=integrity_count,
    )
