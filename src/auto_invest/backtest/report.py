"""Backtest report writer (T024).

Marshals a `ReplayResult` (from `backtest/replay.py`) into the on-disk
artefact tree under `data/backtest/<run_id>/` per
`specs/008-backtest-engine/data-model.md § On-disk per-run layout`:

    <run_dir>/
    ├── backtest-run.json
    ├── metrics.csv
    ├── per-rule/<rule_id>/{orders,fills,gate-rejections}.json
    └── _meta/kernel-guard-report.json

`summary.md` is extended by T035 (US3) and is intentionally not written
here. Determinism contract (FR-B15) is upheld through:

  - Decimal canonicalisation to 6 dp via canonicalise_decimal().
  - Stable sort: orders/fills/rejections sorted by ts_utc ASC, then by
    insertion order for ties.
  - `json.dump(..., sort_keys=True, separators=(",",":"))` so dict-key
    ordering is byte-identical across Python builds.
  - chmod -w on the run directory at completion (POSIX best-effort).

The byte-identical contract (R-B5) covers metrics.csv + per-rule/*.json.
`backtest-run.json` may differ in its three volatile fields (`run_id`,
`start_ts`, `end_ts`); the spec-007 verifier excludes those.
"""

from __future__ import annotations

import contextlib
import csv
import json
import os
import stat
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .data_model import (
    BacktestRun,
    BacktestSummary,
    DataQualityWarning,
    RuleBacktestResult,
    SyntheticShockDay,
    canonicalise_decimal,
)
from .metrics import (
    aggregate_metrics,
    daily_returns_from_equity,
    max_drawdown_pct,
    sharpe_ratio,
    total_return_pct,
)
from .replay import (
    FillRecord,
    GateRejectionRecord,
    OrderRecord,
    ReplayResult,
)


@dataclass(frozen=True)
class KernelGuardReport:
    """Snapshot of kernel_pre_flight at run start (data-model.md § _meta)."""

    touched: bool
    checked_paths: list[str] = field(default_factory=list)
    manifest_sha256: str = ""


# ---------- per-rule metric folds -----------------------------------------


def build_per_rule_results(result: ReplayResult) -> list[RuleBacktestResult]:
    """Compute `RuleBacktestResult` for every rule in `result.per_rule_symbol`.

    Order is by ascending rule_id so metrics.csv + summary.per_rule are
    byte-stable across runs.
    """
    per_rule: list[RuleBacktestResult] = []
    for rule_id in sorted(result.per_rule_symbol):
        symbol = result.per_rule_symbol[rule_id]
        equity = [eq for _, eq in result.per_rule_equity_curve.get(rule_id, [])]
        daily_rets = daily_returns_from_equity(equity)

        # Group gate rejections by gate name for the per-rule headline.
        rejections_for_rule = result.per_rule_gate_rejections.get(rule_id, [])
        by_gate: dict[str, int] = dict(Counter(r.gate for r in rejections_for_rule))

        per_rule.append(
            RuleBacktestResult(
                rule_id=rule_id,
                symbol=symbol,
                total_return_pct=total_return_pct(equity),
                max_drawdown_pct=max_drawdown_pct(equity),
                sharpe_ratio=sharpe_ratio(daily_rets),
                order_count=len(result.per_rule_orders.get(rule_id, [])),
                fill_count=len(result.per_rule_fills.get(rule_id, [])),
                gate_rejection_count_by_gate=by_gate,
                notional_traded_usd=Decimal(
                    canonicalise_decimal(
                        result.per_rule_notional_traded_usd.get(rule_id, Decimal("0"))
                    )
                ),
            )
        )
    return per_rule


def build_summary(
    result: ReplayResult,
    per_rule: list[RuleBacktestResult],
) -> BacktestSummary:
    agg_return, agg_dd, agg_sharpe = aggregate_metrics(per_rule)
    return BacktestSummary(
        aggregate_return_pct=agg_return,
        aggregate_max_drawdown_pct=agg_dd,
        aggregate_sharpe=agg_sharpe,
        per_rule=per_rule,
        total_orders=result.total_orders,
        total_fills=result.total_fills,
        total_gate_rejections=result.total_gate_rejections,
        data_quality_warnings=list(result.data_quality_warnings),
    )


# ---------- JSON serialisation helpers -----------------------------------


def _to_jsonable(value: Any) -> Any:
    """Convert Decimals → canonical 6dp str; dates → ISO; paths → str."""
    if isinstance(value, Decimal):
        return canonicalise_decimal(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(v) for v in value]
    return value


def _record_dict(rec: OrderRecord | FillRecord | GateRejectionRecord) -> dict[str, Any]:
    """Dataclass → JSON-safe dict (drops Nones to keep artefacts tight)."""
    d = asdict(rec)
    return _to_jsonable({k: v for k, v in d.items() if v is not None})


def _sort_by_ts_then_insertion(
    items: list[OrderRecord | FillRecord | GateRejectionRecord],
) -> list[Any]:
    """Stable sort by ts_utc (executed_at_utc for fills); ties preserve original order."""
    keyed: list[tuple[str, int, Any]] = []
    for idx, item in enumerate(items):
        ts = getattr(item, "ts_utc", None) or getattr(item, "executed_at_utc", "")
        keyed.append((ts, idx, item))
    keyed.sort(key=lambda t: (t[0], t[1]))
    return [item for _, _, item in keyed]


def _write_json(path: Path, payload: Any) -> None:
    """Write JSON with byte-stable formatting (sorted keys, compact separators)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        _to_jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    path.write_text(text + "\n", encoding="utf-8")


# ---------- top-level writer -----------------------------------------------


def write_report(
    *,
    run: BacktestRun,
    result: ReplayResult,
    kernel_guard_report: KernelGuardReport,
    out_root: Path,
    chmod_readonly: bool = True,
) -> Path:
    """Write the full per-run artefact tree under `out_root/<run.run_id>/`.

    Returns the run directory. The caller (run.py) updates `run.end_ts`
    and `run.status` before calling so the JSON header reflects terminal
    state.
    """
    run_dir = out_root / run.run_id
    per_rule_dir = run_dir / "per-rule"
    meta_dir = run_dir / "_meta"
    per_rule_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    per_rule_results = build_per_rule_results(result)
    summary = build_summary(result, per_rule_results)

    _write_backtest_run_json(
        path=run_dir / "backtest-run.json",
        run=run,
        summary=summary,
        kernel_guard_report=kernel_guard_report,
    )
    _write_metrics_csv(run_dir / "metrics.csv", summary)
    for rule_id in sorted(result.per_rule_symbol):
        _write_per_rule_artefacts(per_rule_dir / rule_id, result, rule_id)
    _write_json(
        meta_dir / "kernel-guard-report.json",
        {
            "touched": kernel_guard_report.touched,
            "checked_paths": list(kernel_guard_report.checked_paths),
            "manifest_sha256": kernel_guard_report.manifest_sha256,
        },
    )

    if chmod_readonly and os.name == "posix":
        _chmod_tree_readonly(run_dir)

    return run_dir


def _write_backtest_run_json(
    *,
    path: Path,
    run: BacktestRun,
    summary: BacktestSummary,
    kernel_guard_report: KernelGuardReport,
) -> None:
    payload: dict[str, Any] = {
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
        "summary": _summary_to_json(summary),
        "kernel_guard_report": {
            "touched": kernel_guard_report.touched,
            "checked_paths": list(kernel_guard_report.checked_paths),
            "manifest_sha256": kernel_guard_report.manifest_sha256,
        },
    }
    _write_json(path, payload)


def _summary_to_json(summary: BacktestSummary) -> dict[str, Any]:
    return {
        "aggregate_return_pct": canonicalise_decimal(summary.aggregate_return_pct),
        "aggregate_max_drawdown_pct": canonicalise_decimal(
            summary.aggregate_max_drawdown_pct
        ),
        "aggregate_sharpe": canonicalise_decimal(summary.aggregate_sharpe),
        "total_orders": summary.total_orders,
        "total_fills": summary.total_fills,
        "total_gate_rejections": summary.total_gate_rejections,
        "data_quality_warnings": [
            _data_quality_warning_to_json(w) for w in summary.data_quality_warnings
        ],
        "per_rule": [_rule_result_to_json(r) for r in summary.per_rule],
    }


def _rule_result_to_json(r: RuleBacktestResult) -> dict[str, Any]:
    return {
        "rule_id": r.rule_id,
        "symbol": r.symbol,
        "total_return_pct": canonicalise_decimal(r.total_return_pct),
        "max_drawdown_pct": canonicalise_decimal(r.max_drawdown_pct),
        "sharpe_ratio": canonicalise_decimal(r.sharpe_ratio),
        "order_count": r.order_count,
        "fill_count": r.fill_count,
        "gate_rejection_count_by_gate": dict(r.gate_rejection_count_by_gate),
        "notional_traded_usd": canonicalise_decimal(r.notional_traded_usd),
        "slippage_assumption": r.slippage_assumption,
    }


def _data_quality_warning_to_json(w: DataQualityWarning) -> dict[str, Any]:
    return {
        "symbol": w.symbol,
        "session_date": w.session_date.isoformat() if w.session_date else None,
        "kind": w.kind,
        "note": w.note,
    }


_METRICS_CSV_COLUMNS = (
    "rule_id",
    "symbol",
    "total_return_pct",
    "max_drawdown_pct",
    "sharpe",
    "order_count",
    "fill_count",
    "total_gate_rejections",
    "notional_usd",
)


def _write_metrics_csv(path: Path, summary: BacktestSummary) -> None:
    """One row per rule + one `_aggregate` row. Byte-stable across machines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(_METRICS_CSV_COLUMNS)
        for r in summary.per_rule:
            writer.writerow(
                [
                    r.rule_id,
                    r.symbol,
                    canonicalise_decimal(r.total_return_pct),
                    canonicalise_decimal(r.max_drawdown_pct),
                    canonicalise_decimal(r.sharpe_ratio),
                    r.order_count,
                    r.fill_count,
                    sum(r.gate_rejection_count_by_gate.values()),
                    canonicalise_decimal(r.notional_traded_usd),
                ]
            )
        writer.writerow(
            [
                "_aggregate",
                "",
                canonicalise_decimal(summary.aggregate_return_pct),
                canonicalise_decimal(summary.aggregate_max_drawdown_pct),
                canonicalise_decimal(summary.aggregate_sharpe),
                summary.total_orders,
                summary.total_fills,
                summary.total_gate_rejections,
                canonicalise_decimal(
                    sum(
                        (r.notional_traded_usd for r in summary.per_rule),
                        start=Decimal("0"),
                    )
                ),
            ]
        )


def _write_per_rule_artefacts(
    rule_dir: Path,
    result: ReplayResult,
    rule_id: str,
) -> None:
    rule_dir.mkdir(parents=True, exist_ok=True)
    orders = _sort_by_ts_then_insertion(list(result.per_rule_orders.get(rule_id, [])))
    fills = _sort_by_ts_then_insertion(list(result.per_rule_fills.get(rule_id, [])))
    rejections = _sort_by_ts_then_insertion(
        list(result.per_rule_gate_rejections.get(rule_id, []))
    )
    _write_json(rule_dir / "orders.json", [_record_dict(o) for o in orders])
    _write_json(rule_dir / "fills.json", [_record_dict(f) for f in fills])
    _write_json(
        rule_dir / "gate-rejections.json",
        [_record_dict(r) for r in rejections],
    )


def _chmod_tree_readonly(root: Path) -> None:
    """Strip write bits from every file and directory under `root` (POSIX best-effort).

    Directories keep the execute bit so listing still works; files keep
    only read bits. v1 enforces this so a later forensic review sees the
    same artefact bytes the run produced.
    """
    file_mode = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    dir_mode = (
        stat.S_IRUSR
        | stat.S_IXUSR
        | stat.S_IRGRP
        | stat.S_IXGRP
        | stat.S_IROTH
        | stat.S_IXOTH
    )
    for child in root.rglob("*"):
        try:
            if child.is_dir():
                os.chmod(child, dir_mode)
            else:
                os.chmod(child, file_mode)
        except OSError:
            # Best-effort: on filesystems that ignore chmod (e.g. tmpfs
            # under some test runners), keep going. The byte content is
            # still the authoritative artefact.
            continue
    with contextlib.suppress(OSError):
        os.chmod(root, dir_mode)


def write_synthetic_shock_report(
    *,
    run: BacktestRun,
    merged_result: ReplayResult,
    per_shock: list[tuple[SyntheticShockDay, ReplayResult]],
    kernel_guard_report: KernelGuardReport,
    out_root: Path,
    chmod_readonly: bool = True,
) -> Path:
    """Synthetic-shock variant of `write_report` (T032).

    Lays artefacts out as:

        <run_dir>/
        ├── backtest-run.json   (combined summary across all shocks)
        ├── metrics.csv          (one row per rule across ALL shocks + _aggregate)
        ├── per-rule/<rule_id>/by-date/<YYYY-MM-DD>/
        │   ├── orders.json
        │   ├── fills.json
        │   └── gate-rejections.json
        └── _meta/kernel-guard-report.json

    The merged_result is used for the combined summary (metrics.csv +
    backtest-run.json summary block). Each per_shock entry's ReplayResult
    is laid out under by-date/<session_date>/ so the operator can drill
    into one shock day at a time.
    """
    run_dir = out_root / run.run_id
    per_rule_dir = run_dir / "per-rule"
    meta_dir = run_dir / "_meta"
    per_rule_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    per_rule_results = build_per_rule_results(merged_result)
    summary = build_summary(merged_result, per_rule_results)

    _write_backtest_run_json(
        path=run_dir / "backtest-run.json",
        run=run,
        summary=summary,
        kernel_guard_report=kernel_guard_report,
    )
    _write_metrics_csv(run_dir / "metrics.csv", summary)
    _write_json(
        meta_dir / "kernel-guard-report.json",
        {
            "touched": kernel_guard_report.touched,
            "checked_paths": list(kernel_guard_report.checked_paths),
            "manifest_sha256": kernel_guard_report.manifest_sha256,
        },
    )

    # Per-shock per-rule artefacts under per-rule/<rid>/by-date/<date>/.
    for shock, sub in per_shock:
        date_str = shock.session_date.isoformat()
        for rule_id in sorted(sub.per_rule_symbol):
            by_date_dir = per_rule_dir / rule_id / "by-date" / date_str
            by_date_dir.mkdir(parents=True, exist_ok=True)
            orders = _sort_by_ts_then_insertion(
                list(sub.per_rule_orders.get(rule_id, []))
            )
            fills = _sort_by_ts_then_insertion(
                list(sub.per_rule_fills.get(rule_id, []))
            )
            rejections = _sort_by_ts_then_insertion(
                list(sub.per_rule_gate_rejections.get(rule_id, []))
            )
            _write_json(by_date_dir / "orders.json", [_record_dict(o) for o in orders])
            _write_json(by_date_dir / "fills.json", [_record_dict(f) for f in fills])
            _write_json(
                by_date_dir / "gate-rejections.json",
                [_record_dict(r) for r in rejections],
            )

    if chmod_readonly and os.name == "posix":
        _chmod_tree_readonly(run_dir)

    return run_dir


__all__ = [
    "KernelGuardReport",
    "build_per_rule_results",
    "build_summary",
    "write_report",
    "write_synthetic_shock_report",
]
