"""Spec 007 T016 — canary-run.json + metrics.csv writer contract."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from auto_invest.canary.bands import load_bands
from auto_invest.canary.data_model import (
    CanaryMetrics,
    CanaryRun,
    KernelTouch,
    MetricResult,
    SeedBundle,
)
from auto_invest.canary.metrics import evaluate_metrics
from auto_invest.canary.report import (
    CANARY_RUN_JSON,
    FUZZ_DIR,
    METRICS_CSV,
    SHOCK_DIR,
    WINDOW_DIR,
    write_fuzz_artefacts,
    write_report,
)


def _passing_metrics() -> CanaryMetrics:
    bands = load_bands()["L2"]
    return evaluate_metrics(
        candidate_drawdown_pct=1.83,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=bands,
    )


def _run(
    *,
    canary_run_id: UUID = UUID("12345678-1234-1234-1234-1234567890ab"),
    outcome: str = "passed",
    metrics: CanaryMetrics | None = None,
    kernel_touches: list[KernelTouch] | None = None,
    failing_metrics: list[str] | None = None,
) -> CanaryRun:
    return CanaryRun(
        canary_run_id=canary_run_id,
        candidate_rev="a" * 40,
        baseline_rev="b" * 40,
        tier="L2",
        window_trading_days=30,
        window_start_date=date(2026, 3, 31),
        window_end_date=date(2026, 5, 13),
        started_at=datetime(2026, 5, 14, 8, 30, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 14, 8, 42, 17, tzinfo=timezone.utc),
        outcome=outcome,  # type: ignore[arg-type]
        failing_metrics=failing_metrics or [],
        kernel_touches=kernel_touches or [],
        metrics=metrics or _passing_metrics(),
        seed_bundle=SeedBundle(
            hypothesis_database_seed=42,
            hypothesis_iterations=10000,
            synthetic_shock_dates=[
                date(2020, 3, 12),
                date(2020, 4, 20),
                date(2024, 8, 5),
                date(2026, 3, 20),
            ],
            quarterly_opex_resolved_for=date(2026, 5, 14),
        ),
    )


# ---------------------------------------------------------- layout


def test_write_report_creates_required_directories(tmp_path: Path) -> None:
    run = _run()
    out_root = tmp_path / "canary"
    run_dir = write_report(run, out_root)
    assert run_dir == out_root / str(run.canary_run_id)
    assert (run_dir / CANARY_RUN_JSON).is_file()
    assert (run_dir / METRICS_CSV).is_file()
    assert (run_dir / SHOCK_DIR).is_dir()
    assert (run_dir / WINDOW_DIR / "candidate").is_dir()
    assert (run_dir / WINDOW_DIR / "baseline").is_dir()
    assert (run_dir / FUZZ_DIR).is_dir()


def test_metrics_csv_has_one_row_per_metric_plus_header(tmp_path: Path) -> None:
    run = _run()
    run_dir = write_report(run, tmp_path)
    content = (run_dir / METRICS_CSV).read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    assert lines[0] == "id,observed_value,band_upper,band_must_equal,inside_band,source"
    assert len(lines) == 6  # header + 5 metrics
    ids = [line.split(",")[0] for line in lines[1:]]
    assert ids == [
        "pnl_drawdown_pct",
        "risk_gate_violations",
        "audit_integrity_failures",
        "latency_p95_regression_pct",
        "llm_cost_regression_pct",
    ]


# ---------------------------------------------------------- schema


def test_canary_run_json_has_contract_top_level_keys(tmp_path: Path) -> None:
    run = _run()
    run_dir = write_report(run, tmp_path)
    blob = json.loads((run_dir / CANARY_RUN_JSON).read_text(encoding="utf-8"))
    expected_keys = {
        "canary_run_id",
        "candidate_rev",
        "baseline_rev",
        "tier",
        "window_trading_days",
        "window_start_date",
        "window_end_date",
        "started_at",
        "finished_at",
        "outcome",
        "failing_metrics",
        "kernel_touches",
        "metrics",
        "seed_bundle",
    }
    assert set(blob.keys()) == expected_keys
    assert blob["candidate_rev"] == "a" * 40


def test_canary_run_json_metrics_block_has_5_entries(tmp_path: Path) -> None:
    run = _run()
    run_dir = write_report(run, tmp_path)
    blob = json.loads((run_dir / CANARY_RUN_JSON).read_text(encoding="utf-8"))
    assert set(blob["metrics"].keys()) == {
        "pnl_drawdown_pct",
        "risk_gate_violations",
        "audit_integrity_failures",
        "latency_p95_regression_pct",
        "llm_cost_regression_pct",
    }


# ---------------------------------------------------------- determinism


def test_canary_run_json_byte_identical_modulo_volatile_fields(tmp_path: Path) -> None:
    """SC-C04 byte-identical re-write on identical input.

    The volatile fields are canary_run_id, started_at, finished_at. The rest
    of the JSON must round-trip identically.
    """
    run_a = _run(canary_run_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    run_b = _run(canary_run_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))

    dir_a = write_report(run_a, tmp_path / "a")
    dir_b = write_report(run_b, tmp_path / "b")

    a = json.loads((dir_a / CANARY_RUN_JSON).read_text())
    b = json.loads((dir_b / CANARY_RUN_JSON).read_text())
    for vol in ("canary_run_id", "started_at", "finished_at"):
        a.pop(vol, None)
        b.pop(vol, None)
    assert a == b


def test_failing_metrics_sorted_lexicographically(tmp_path: Path) -> None:
    run = _run(failing_metrics=["llm_cost_regression_pct", "pnl_drawdown_pct"])
    run_dir = write_report(run, tmp_path)
    blob = json.loads((run_dir / CANARY_RUN_JSON).read_text())
    assert blob["failing_metrics"] == sorted(
        ["llm_cost_regression_pct", "pnl_drawdown_pct"]
    )


def test_kernel_touches_sorted_by_kernel_rank(tmp_path: Path) -> None:
    """Kernel touches MUST be ordered K1..K6, K_meta in the on-disk JSON."""
    run = _run(
        kernel_touches=[
            KernelTouch(group="K_meta", files=[".specify/memory/kernel.toml"]),
            KernelTouch(group="K4", files=["src/auto_invest/persistence/audit.py"]),
            KernelTouch(group="K1", files=["src/auto_invest/risk/gates.py"]),
        ]
    )
    run_dir = write_report(run, tmp_path)
    blob = json.loads((run_dir / CANARY_RUN_JSON).read_text())
    groups = [kt["group"] for kt in blob["kernel_touches"]]
    assert groups == ["K1", "K4", "K_meta"]


def test_kernel_touch_files_sorted_lexicographically(tmp_path: Path) -> None:
    run = _run(
        kernel_touches=[
            KernelTouch(
                group="K_meta",
                files=[".specify/memory/kernel.toml", ".specify/memory/constitution.md"],
            )
        ]
    )
    run_dir = write_report(run, tmp_path)
    blob = json.loads((run_dir / CANARY_RUN_JSON).read_text())
    assert blob["kernel_touches"][0]["files"] == [
        ".specify/memory/constitution.md",
        ".specify/memory/kernel.toml",
    ]


def test_write_report_requires_metrics(tmp_path: Path) -> None:
    """metrics=None at write time is a programmer error."""
    run = CanaryRun(
        canary_run_id=UUID("12345678-1234-1234-1234-1234567890ab"),
        candidate_rev="a" * 40,
        baseline_rev="b" * 40,
        tier="L2",
        window_trading_days=30,
        window_start_date=date(2026, 3, 31),
        window_end_date=date(2026, 5, 13),
        started_at=datetime(2026, 5, 14, 8, 30, 0, tzinfo=timezone.utc),
    )
    with pytest.raises(ValueError, match="metrics"):
        write_report(run, tmp_path)


# ---------------------------------------------------------- fuzz artefacts


def test_write_fuzz_artefacts_empty(tmp_path: Path) -> None:
    write_fuzz_artefacts(canary_run_dir=tmp_path, counterexamples=[], seeds=[42])
    seeds_text = (tmp_path / FUZZ_DIR / "seeds.txt").read_text()
    assert seeds_text == "42\n"
    ce_text = (tmp_path / FUZZ_DIR / "counterexamples.json").read_text()
    assert json.loads(ce_text) == []
