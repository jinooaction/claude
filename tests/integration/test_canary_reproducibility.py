"""Spec 007 T030 — SC-C04 byte-identical reproducibility.

Run the canary twice against identical inputs (including
``--hypothesis-seed``). Verify ``canary-run.json`` is byte-identical
between the two runs after stripping the three volatile fields
(``canary_run_id``, ``started_at``, ``finished_at``).

Also asserts:
  - ``metrics.csv`` is byte-identical (no volatile fields in there).
  - ``property-fuzz/seeds.txt`` is byte-identical (the seed is the
    reproducibility key for the fuzz pass).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.canary.cli import app as canary_app
from auto_invest.canary.report import (
    CANARY_RUN_JSON,
    FUZZ_DIR,
    METRICS_CSV,
)
from auto_invest.cli import app as main_app

runner = CliRunner()


_AAPL_CSV = """\
session_date,open,high,low,close,volume,session_schedule_tag
2024-01-02,185.640000,188.440000,183.890000,185.640000,82488700,regular
2024-01-03,184.220000,185.880000,183.430000,184.250000,58414500,regular
2024-01-04,182.150000,183.090000,180.880000,181.910000,71983600,regular
2024-01-05,181.990000,182.760000,180.170000,181.180000,62303300,regular
2024-01-08,182.090000,185.600000,181.500000,185.560000,59144500,regular
2024-01-09,183.920000,185.150000,182.730000,185.140000,42841800,regular
2024-01-10,184.350000,186.400000,183.920000,186.190000,46792900,regular
"""

_RULES_TOML = """\
[caps]
per_trade_pct = 5
per_symbol_pct = 10
global_exposure_pct = 50
canary_capital_pct = 1
canary_min_duration_days = 5
canary_acceptance_drawdown_pct = 5

[whitelist]
symbols = ["AAPL"]
accounts = ["BACKTEST"]
order_types = ["LIMIT"]
sessions = ["REGULAR"]

[[rules]]
id = "buy_aapl_below_184"
symbol = "AAPL"
stage = "BACKTEST"
priority = 0
trigger = { kind = "price", direction = "<=", threshold = "184.50", cooldown_seconds = 0 }
action  = { side = "BUY", order_type = "LIMIT", qty = 20, limit_price = "183.00" }
"""


def _setup_fixture(tmp_path: Path, *, label: str) -> tuple[Path, Path, Path, Path]:
    csv_root = tmp_path / "history-csv"
    if not csv_root.exists():
        csv_root.mkdir()
        (csv_root / "AAPL.csv").write_text(_AAPL_CSV)
    rules_path = tmp_path / "rules.toml"
    if not rules_path.exists():
        rules_path.write_text(_RULES_TOML)
    canary_out = tmp_path / f"canary-{label}"
    db_path = tmp_path / f"audit-{label}.db"
    return csv_root, rules_path, canary_out, db_path


def _run_canary(
    *,
    rules_path: Path,
    history_root: Path,
    canary_out: Path,
    db_path: Path,
    halt_path: Path,
    seed: int,
    iterations: int,
) -> str:
    """Invoke the canary CLI and return the run_id from canary_out."""
    result = runner.invoke(
        canary_app,
        [
            "run",
            "--tier",
            "L2",
            "--rules",
            str(rules_path),
            "--from",
            "2024-01-02",
            "--to",
            "2024-01-10",
            "--candidate-rev",
            "HEAD",
            "--baseline-rev",
            "HEAD",
            "--out-dir",
            str(canary_out),
            "--db",
            str(db_path),
            "--history-root",
            str(history_root),
            "--halt-path",
            str(halt_path),
            "--hypothesis-seed",
            str(seed),
            "--hypothesis-iterations",
            str(iterations),
            "--skip-shock",  # shock data not in fixture; doesn't affect SC-C04
        ],
    )
    assert result.exit_code == 0, result.output
    runs = list(canary_out.iterdir())
    assert len(runs) == 1
    return runs[0].name


def test_canary_run_byte_identical_with_same_seed(tmp_path: Path) -> None:
    csv_root, rules_path, canary_out_a, db_a = _setup_fixture(tmp_path, label="a")
    canary_out_b = tmp_path / "canary-b"
    db_b = tmp_path / "audit-b.db"
    history_root = tmp_path / "history"

    # Ingest once; both runs share the same dataset_version.
    runner.invoke(
        main_app,
        ["ingest-history", "--from-dir", str(csv_root), "--out-dir", str(history_root)],
    )

    run_a_id = _run_canary(
        rules_path=rules_path,
        history_root=history_root,
        canary_out=canary_out_a,
        db_path=db_a,
        halt_path=tmp_path / "HALT-A",
        seed=42,
        iterations=200,
    )
    run_b_id = _run_canary(
        rules_path=rules_path,
        history_root=history_root,
        canary_out=canary_out_b,
        db_path=db_b,
        halt_path=tmp_path / "HALT-B",
        seed=42,
        iterations=200,
    )

    # Different canary_run_ids (UUIDs).
    assert run_a_id != run_b_id

    # canary-run.json byte-identical modulo volatile fields.
    blob_a = json.loads(
        (canary_out_a / run_a_id / CANARY_RUN_JSON).read_text()
    )
    blob_b = json.loads(
        (canary_out_b / run_b_id / CANARY_RUN_JSON).read_text()
    )
    for volatile in ("canary_run_id", "started_at", "finished_at"):
        blob_a.pop(volatile, None)
        blob_b.pop(volatile, None)
    assert blob_a == blob_b

    # metrics.csv has NO volatile fields → byte-identical.
    metrics_a = (canary_out_a / run_a_id / METRICS_CSV).read_bytes()
    metrics_b = (canary_out_b / run_b_id / METRICS_CSV).read_bytes()
    assert metrics_a == metrics_b

    # Fuzz seeds.txt — seed is the operator-provided reproducibility key.
    seeds_a = (canary_out_a / run_a_id / FUZZ_DIR / "seeds.txt").read_bytes()
    seeds_b = (canary_out_b / run_b_id / FUZZ_DIR / "seeds.txt").read_bytes()
    assert seeds_a == seeds_b
    assert seeds_a.strip() == b"42"

    # Fuzz counterexamples — both clean K1 → both empty.
    ces_a = json.loads(
        (canary_out_a / run_a_id / FUZZ_DIR / "counterexamples.json").read_text()
    )
    ces_b = json.loads(
        (canary_out_b / run_b_id / FUZZ_DIR / "counterexamples.json").read_text()
    )
    assert ces_a == ces_b == []


def test_different_seeds_produce_different_seed_files(tmp_path: Path) -> None:
    """Sanity: changing --hypothesis-seed changes seeds.txt content."""
    csv_root, rules_path, canary_out_a, db_a = _setup_fixture(tmp_path, label="a")
    canary_out_b = tmp_path / "canary-b"
    db_b = tmp_path / "audit-b.db"
    history_root = tmp_path / "history"
    runner.invoke(
        main_app,
        ["ingest-history", "--from-dir", str(csv_root), "--out-dir", str(history_root)],
    )

    run_a_id = _run_canary(
        rules_path=rules_path,
        history_root=history_root,
        canary_out=canary_out_a,
        db_path=db_a,
        halt_path=tmp_path / "HALT-A",
        seed=42,
        iterations=100,
    )
    run_b_id = _run_canary(
        rules_path=rules_path,
        history_root=history_root,
        canary_out=canary_out_b,
        db_path=db_b,
        halt_path=tmp_path / "HALT-B",
        seed=43,
        iterations=100,
    )

    seeds_a = (canary_out_a / run_a_id / FUZZ_DIR / "seeds.txt").read_text().strip()
    seeds_b = (canary_out_b / run_b_id / FUZZ_DIR / "seeds.txt").read_text().strip()
    assert seeds_a == "42"
    assert seeds_b == "43"
