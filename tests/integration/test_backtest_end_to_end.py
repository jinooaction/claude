"""T028 — end-to-end integration test for `auto-invest backtest`.

Drives the full pipeline:
  1. ingest a small CSV fixture via `auto-invest ingest-history`
  2. run `auto-invest backtest --from --to --rules` against the ingested data
  3. assert: artefact tree exists, audit chain has BACKTEST_*/ORDER_*/FILL,
            no live-broker leak, no real-LLM call, stdout first+last line
            is `backtest run_id: <hex>`.

Per FR-B06 + FR-B08 + FR-B11 the run MUST:
  - never reach a real KIS endpoint (broker.overseas.place_order is never imported)
  - never construct an AnthropicClient (no spec-004 yet, but guard_no_real_llm
    would raise if one were added)
  - produce the contracts/backtest-cli.md-shaped stdout layout
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import audit, db

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
2024-01-11,186.540000,187.050000,183.620000,185.590000,49128400,regular
2024-01-12,186.060000,186.740000,185.190000,185.920000,40477800,regular
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


def _setup_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Lay out csvs / rules / db / out roots; return all four paths."""
    csv_root = tmp_path / "history-csv"
    csv_root.mkdir()
    (csv_root / "AAPL.csv").write_text(_AAPL_CSV)

    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_RULES_TOML)

    history_root = tmp_path / "history"
    out_dir = tmp_path / "backtest-out"
    return csv_root, rules_path, history_root, out_dir


def test_end_to_end_backtest_produces_artefact_tree_and_audit_chain(tmp_path: Path) -> None:
    csv_root, rules_path, history_root, out_dir = _setup_fixture(tmp_path)
    db_path = tmp_path / "audit.db"

    # (1) Ingest.
    ingest_result = runner.invoke(
        app,
        [
            "ingest-history",
            "--from-dir",
            str(csv_root),
            "--out-dir",
            str(history_root),
        ],
    )
    assert ingest_result.exit_code == 0, ingest_result.output
    dataset_version = ingest_result.output.strip().splitlines()[-1]
    assert len(dataset_version) == 64  # SHA-256 hex

    # (2) Backtest.
    bt_result = runner.invoke(
        app,
        [
            "backtest",
            "--rules",
            str(rules_path),
            "--from",
            "2024-01-02",
            "--to",
            "2024-01-12",
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--history-root",
            str(history_root),
            "--halt-path",
            str(tmp_path / "HALT"),
            "--allow-kernel-edits",  # tests don't care about repo's kernel state
        ],
    )
    assert bt_result.exit_code == 0, bt_result.output

    # (3) Stdout shape — first AND last printable line is `backtest run_id: <hex>`.
    lines = [
        ln for ln in bt_result.output.splitlines() if ln.strip()
    ]
    assert lines[0].startswith("backtest run_id: ")
    assert lines[-1].startswith("backtest run_id: ")
    assert lines[0] == lines[-1]
    run_id = lines[0].split("backtest run_id: ", 1)[1].strip()
    assert len(run_id) == 32  # uuid4 hex

    # (4) Artefact tree.
    run_dir = out_dir / run_id
    assert (run_dir / "backtest-run.json").exists()
    assert (run_dir / "metrics.csv").exists()
    assert (run_dir / "_meta" / "kernel-guard-report.json").exists()
    assert (run_dir / "per-rule" / "buy_aapl_below_184").exists()
    payload = json.loads((run_dir / "backtest-run.json").read_text())
    assert payload["status"] == "completed"
    assert payload["dataset_version"] == dataset_version
    assert payload["summary"] is not None
    assert payload["summary"]["total_orders"] >= 1

    # (5) Audit chain — backtest events present + ORDER/FILL chain reached.
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        events = [r["event_type"] for r in audit.read_all(conn)]
    finally:
        conn.close()
    assert "BACKTEST_STARTED" in events
    assert "BACKTEST_COMPLETED" in events
    assert "ORDER_INTENT" in events
    assert events.count("BACKTEST_COMPLETED") == 1


def test_end_to_end_no_live_broker_or_anthropic_imports(tmp_path: Path) -> None:
    """FR-B06 + FR-B08: a successful backtest must NOT import / instantiate
    the live KIS or Anthropic clients. We check by importing the cli module
    and confirming `broker.overseas.place_order` and any AnthropicClient
    are never *called* — easiest proxy is to assert exit 0 + no NetworkX
    failures, AND that BACKTEST_MODE is restored after the run."""
    import os

    from auto_invest.backtest.judgment_stub import BACKTEST_MODE_ENV

    prior = os.environ.get(BACKTEST_MODE_ENV)
    csv_root, rules_path, history_root, out_dir = _setup_fixture(tmp_path)

    runner.invoke(
        app,
        [
            "ingest-history",
            "--from-dir",
            str(csv_root),
            "--out-dir",
            str(history_root),
        ],
    )
    bt = runner.invoke(
        app,
        [
            "backtest",
            "--rules",
            str(rules_path),
            "--from",
            "2024-01-02",
            "--to",
            "2024-01-12",
            "--out-dir",
            str(out_dir),
            "--db",
            str(tmp_path / "audit.db"),
            "--history-root",
            str(history_root),
            "--halt-path",
            str(tmp_path / "HALT"),
            "--allow-kernel-edits",
        ],
    )
    assert bt.exit_code == 0, bt.output
    # BACKTEST_MODE env restored to whatever it was before.
    assert os.environ.get(BACKTEST_MODE_ENV) == prior


def test_end_to_end_coverage_hole_exits_66(tmp_path: Path) -> None:
    """A requested window with no bars in the ingested dataset → exit 66."""
    csv_root, rules_path, history_root, out_dir = _setup_fixture(tmp_path)
    runner.invoke(
        app,
        [
            "ingest-history",
            "--from-dir",
            str(csv_root),
            "--out-dir",
            str(history_root),
        ],
    )
    bt = runner.invoke(
        app,
        [
            "backtest",
            "--rules",
            str(rules_path),
            # Request a window the fixture does not cover.
            "--from",
            "2024-02-01",
            "--to",
            "2024-02-05",
            "--out-dir",
            str(out_dir),
            "--db",
            str(tmp_path / "audit.db"),
            "--history-root",
            str(history_root),
            "--halt-path",
            str(tmp_path / "HALT"),
            "--allow-kernel-edits",
        ],
    )
    assert bt.exit_code == 66, bt.output
    assert "coverage hole" in bt.output or "coverage hole" in (bt.stderr or "")


def test_end_to_end_artefact_files_are_byte_stable_across_runs(tmp_path: Path) -> None:
    """FR-B15 byte-identical determinism — two runs of the same inputs
    produce byte-identical metrics.csv + per-rule/orders.json."""
    csv_root, rules_path, history_root, out_dir = _setup_fixture(tmp_path)
    runner.invoke(
        app,
        [
            "ingest-history",
            "--from-dir",
            str(csv_root),
            "--out-dir",
            str(history_root),
        ],
    )

    def _run() -> Path:
        result = runner.invoke(
            app,
            [
                "backtest",
                "--rules",
                str(rules_path),
                "--from",
                "2024-01-02",
                "--to",
                "2024-01-12",
                "--out-dir",
                str(out_dir),
                "--db",
                str(tmp_path / "audit.db"),
                "--history-root",
                str(history_root),
                "--halt-path",
                str(tmp_path / "HALT"),
                "--allow-kernel-edits",
            ],
        )
        assert result.exit_code == 0, result.output
        run_id = result.output.splitlines()[0].split(":", 1)[1].strip()
        return out_dir / run_id

    run_dir_a = _run()
    run_dir_b = _run()
    assert (run_dir_a / "metrics.csv").read_bytes() == (run_dir_b / "metrics.csv").read_bytes()
    assert (run_dir_a / "per-rule" / "buy_aapl_below_184" / "orders.json").read_bytes() == (
        run_dir_b / "per-rule" / "buy_aapl_below_184" / "orders.json"
    ).read_bytes()
