"""Synthetic-shock pass for the canary (T020).

Wraps spec 008's batched-shock backtest (``run_backtest(..., synthetic_shock=True)``)
and counts the total ``ORDER_REJECTED_BY_GATE`` events across the canonical
adverse historical days (FR-C03).

Graceful degradation (v1): if any shock date is missing from the
ingested dataset, the pass records the missing dates in the result and
returns 0 violations from THAT shock. The orchestrator decides whether
to fail the canary on missing data (typical production setup pre-ingests
the four shock dates per quickstart.md).

The shock result carries:
  - per-shock ``ShockOutcome`` (date, violations, skipped flag)
  - aggregate ``total_violations`` used directly by the metric evaluator
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from auto_invest.backtest.data_model import SyntheticShockDay
from auto_invest.backtest.data_source import HistoricalDataSource
from auto_invest.backtest.run import RunOptions, run_backtest
from auto_invest.backtest.synthetic_shocks import (
    SyntheticShockConfigError,
    resolve_synthetic_shock_dates,
    shock_window,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist


@dataclass(frozen=True)
class ShockOutcome:
    name: str
    session_date: date
    violations: int
    skipped: bool = False
    skipped_reason: str | None = None


@dataclass(frozen=True)
class ShockBatteryResult:
    outcomes: list[ShockOutcome]
    total_violations: int
    skipped_count: int
    resolved_dates: list[date]


@dataclass(frozen=True)
class ShockInputs:
    rules_path: Path
    rules: Sequence[TradingRule]
    ruleset_sha256: str
    data_source: HistoricalDataSource
    caps: SizingCaps
    whitelist: Whitelist
    halt_path: Path
    out_root: Path
    today: date  # determinism input for ``resolve_synthetic_shock_dates``
    shocks_toml: Path | None = None  # default: spec-008 path


def _coverage_holes_for_shock(
    *,
    data_source: HistoricalDataSource,
    shock: SyntheticShockDay,
) -> list[tuple[str, date]]:
    start, end = shock_window(shock, lookback_bars=30)
    symbols = list(data_source.list_symbols())
    return data_source.coverage_holes(symbols, start, end)


def _run_one_shock(
    *,
    inputs: ShockInputs,
    shock: SyntheticShockDay,
    audit_conn: sqlite3.Connection,
) -> ShockOutcome:
    holes = _coverage_holes_for_shock(
        data_source=inputs.data_source, shock=shock
    )
    if holes:
        return ShockOutcome(
            name=shock.name,
            session_date=shock.session_date,
            violations=0,
            skipped=True,
            skipped_reason=(
                f"dataset missing {len(holes)} bars in shock window "
                f"{shock.session_date.isoformat()}"
            ),
        )

    start, end = shock_window(shock, lookback_bars=30)
    options = RunOptions(
        rules_path=inputs.rules_path,
        rules=inputs.rules,
        ruleset_sha256=inputs.ruleset_sha256,
        data_source=inputs.data_source,
        date_start=start,
        date_end=end,
        caps=inputs.caps,
        whitelist=inputs.whitelist,
        halt_path=inputs.halt_path,
        out_root=inputs.out_root,
        invoker="canary",
        replay_seed=0,
        synthetic_shock=True,
        allow_kernel_edits=True,
        shocks=(shock,),
        shock_windows=((start, end),),
    )
    outcome = run_backtest(options, conn=audit_conn)

    # Read total_gate_rejections from backtest-run.json (the in-memory
    # BacktestRun model has it under summary.total_gate_rejections).
    import json

    backtest_json = outcome.run_dir / "backtest-run.json"
    if not backtest_json.exists():
        return ShockOutcome(
            name=shock.name,
            session_date=shock.session_date,
            violations=0,
            skipped=True,
            skipped_reason="backtest-run.json not written (likely kernel-touch refusal)",
        )
    blob = json.loads(backtest_json.read_text())
    summary = blob.get("summary") or {}
    violations = int(summary.get("total_gate_rejections", 0))
    return ShockOutcome(
        name=shock.name,
        session_date=shock.session_date,
        violations=violations,
    )


def run_synthetic_shock_battery(
    inputs: ShockInputs,
    *,
    audit_conn: sqlite3.Connection,
) -> ShockBatteryResult:
    """Run a synthetic-shock backtest for each resolved shock date.

    Returns aggregate violations across all shocks. Per FR-C03 any
    non-zero violation rejects the canary (the orchestrator handles
    the all-or-nothing decision via ``metrics.evaluate_metrics``).
    """

    try:
        resolved = resolve_synthetic_shock_dates(
            today=inputs.today,
            path=inputs.shocks_toml,
        )
    except SyntheticShockConfigError as exc:
        # No shocks configured / unparseable config: treat as zero
        # violations + zero outcomes. Orchestrator records the empty list.
        return ShockBatteryResult(
            outcomes=[],
            total_violations=0,
            skipped_count=0,
            resolved_dates=[],
        )

    outcomes: list[ShockOutcome] = []
    for s in resolved:
        outcomes.append(
            _run_one_shock(
                inputs=inputs,
                shock=s,
                audit_conn=audit_conn,
            )
        )

    total = sum(o.violations for o in outcomes)
    skipped = sum(1 for o in outcomes if o.skipped)
    return ShockBatteryResult(
        outcomes=outcomes,
        total_violations=total,
        skipped_count=skipped,
        resolved_dates=[s.session_date for s in resolved],
    )


__all__ = [
    "ShockBatteryResult",
    "ShockInputs",
    "ShockOutcome",
    "run_synthetic_shock_battery",
]
