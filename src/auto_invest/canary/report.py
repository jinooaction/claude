"""Canary report writer — produces ``data/canary/<run_id>/`` tree (T015).

Layout per contracts/canary-run-json.md + data-model.md § "On-disk layout".

Deterministic write order (R-C9):

  1. ``replay-window/{candidate,baseline}/``
  2. ``shock-replay/<YYYY-MM-DD>/``
  3. ``property-fuzz/``
  4. ``metrics.csv``
  5. ``canary-run.json``  (LAST — its presence guarantees all sub-artefacts are
     also complete)

Byte-identical reproducibility (SC-C04) requires:

  - Pydantic ``model_dump_json`` (not raw ``json.dumps`` on ``model_dump()``).
  - Map key order forced via ``sort_keys=True`` in custom encoder.
  - Lexicographic sort of ``kernel_touches[].files`` and ``failing_metrics``.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections.abc import Iterable
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from uuid import UUID

from auto_invest.canary.data_model import (
    CanaryMetrics,
    CanaryRun,
    FuzzCounterexample,
    KernelTouch,
    MetricResult,
)


CANARY_RUN_JSON = "canary-run.json"
METRICS_CSV = "metrics.csv"
SHOCK_DIR = "shock-replay"
WINDOW_DIR = "replay-window"
FUZZ_DIR = "property-fuzz"


def _sort_kernel_touches(touches: Iterable[KernelTouch]) -> list[KernelTouch]:
    rank: dict[str, int] = {
        "K1": 1,
        "K2": 2,
        "K3": 3,
        "K4": 4,
        "K5": 5,
        "K6": 6,
        "K_meta": 7,
    }
    return [
        KernelTouch(group=t.group, files=sorted(t.files))
        for t in sorted(touches, key=lambda t: rank.get(t.group, 99))
    ]


def _canonical_run(run: CanaryRun) -> CanaryRun:
    return run.model_copy(
        update={
            "kernel_touches": _sort_kernel_touches(run.kernel_touches),
            "failing_metrics": sorted(run.failing_metrics),
        }
    )


def _serialise_run_json(run: CanaryRun) -> str:
    """Stable, sort-keyed JSON of CanaryRun for byte-identical reproducibility.

    Round-trips via ``model_dump(mode="json")`` to get pydantic's canonical
    encoders for UUID / datetime / date, then ``json.dumps`` with
    ``sort_keys=True`` to enforce map ordering across Python versions.
    """
    data = run.model_dump(mode="json")
    return json.dumps(data, indent=2, sort_keys=True)


def _write_canary_run_json(run: CanaryRun, run_dir: Path) -> Path:
    path = run_dir / CANARY_RUN_JSON
    payload = _serialise_run_json(run)
    path.write_text(payload + "\n", encoding="utf-8")
    return path


def _metric_row(metric_id: str, m: MetricResult) -> list[str]:
    return [
        metric_id,
        f"{m.observed_value}",
        "" if m.band_upper is None else f"{m.band_upper}",
        "" if m.band_must_equal is None else f"{m.band_must_equal}",
        "true" if m.inside_band else "false",
        m.source,
    ]


def _write_metrics_csv(metrics: CanaryMetrics, run_dir: Path) -> Path:
    path = run_dir / METRICS_CSV
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        ["id", "observed_value", "band_upper", "band_must_equal", "inside_band", "source"]
    )
    for metric_id, m in (
        ("pnl_drawdown_pct", metrics.pnl_drawdown_pct),
        ("risk_gate_violations", metrics.risk_gate_violations),
        ("audit_integrity_failures", metrics.audit_integrity_failures),
        ("latency_p95_regression_pct", metrics.latency_p95_regression_pct),
        ("llm_cost_regression_pct", metrics.llm_cost_regression_pct),
    ):
        writer.writerow(_metric_row(metric_id, m))
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


def _ensure_dirs(run_dir: Path) -> None:
    (run_dir / SHOCK_DIR).mkdir(parents=True, exist_ok=True)
    (run_dir / WINDOW_DIR / "candidate").mkdir(parents=True, exist_ok=True)
    (run_dir / WINDOW_DIR / "baseline").mkdir(parents=True, exist_ok=True)
    (run_dir / FUZZ_DIR).mkdir(parents=True, exist_ok=True)


def copy_window_artefact(
    *,
    source_run_dir: Path,
    canary_run_dir: Path,
    side: str,
) -> None:
    """Copy spec 008's per-backtest artefacts into the canary tree.

    R-C9: copy (not symlink) so the canary run dir is self-contained.
    """
    if side not in ("candidate", "baseline"):
        raise ValueError(f"side must be candidate|baseline, got {side!r}")
    dst = canary_run_dir / WINDOW_DIR / side
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("backtest-run.json", "metrics.csv", "summary.md"):
        src = source_run_dir / name
        if src.exists():
            shutil.copy2(src, dst / name)


def write_fuzz_artefacts(
    *,
    canary_run_dir: Path,
    counterexamples: list[FuzzCounterexample],
    seeds: list[int],
) -> None:
    fuzz_dir = canary_run_dir / FUZZ_DIR
    fuzz_dir.mkdir(parents=True, exist_ok=True)
    (fuzz_dir / "seeds.txt").write_text(
        "\n".join(str(s) for s in seeds) + ("\n" if seeds else ""),
        encoding="utf-8",
    )
    blob = [c.model_dump(mode="json") for c in counterexamples]
    (fuzz_dir / "counterexamples.json").write_text(
        json.dumps(blob, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_report(run: CanaryRun, out_root: Path) -> Path:
    """Write the canary run tree under ``<out_root>/<canary_run_id>/``.

    Returns the run directory. Caller is expected to have written any
    sub-artefacts (window replay artefacts, shock-replay artefacts,
    fuzz outputs) BEFORE calling this — this function finalises by
    writing ``metrics.csv`` and ``canary-run.json`` last.
    """

    canonical = _canonical_run(run)
    if canonical.metrics is None:
        raise ValueError(
            "write_report called with CanaryRun.metrics=None — populate metrics first"
        )

    run_dir = out_root / str(canonical.canary_run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    _ensure_dirs(run_dir)

    _write_metrics_csv(canonical.metrics, run_dir)
    _write_canary_run_json(canonical, run_dir)
    return run_dir


__all__ = [
    "CANARY_RUN_JSON",
    "FUZZ_DIR",
    "METRICS_CSV",
    "SHOCK_DIR",
    "WINDOW_DIR",
    "copy_window_artefact",
    "write_fuzz_artefacts",
    "write_report",
]
