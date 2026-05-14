"""T034 — FR-B15 byte-identical determinism contract / SC-B02.

Running the same backtest fixture twice MUST produce byte-identical:
  - metrics.csv
  - per-rule/<rid>/orders.json
  - per-rule/<rid>/fills.json
  - per-rule/<rid>/gate-rejections.json

And `backtest-run.json` MUST differ ONLY in the three volatile fields:
  run_id, start_ts, end_ts.

This is the contract spec 007's hardened canary verifier relies on.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app

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
id = "buy_aapl"
symbol = "AAPL"
stage = "BACKTEST"
priority = 0
trigger = { kind = "price", direction = "<=", threshold = "184.50", cooldown_seconds = 0 }
action  = { side = "BUY", order_type = "LIMIT", qty = 20, limit_price = "183.00" }
"""


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    csv_root = tmp_path / "csvs"
    csv_root.mkdir()
    (csv_root / "AAPL.csv").write_text(_AAPL_CSV)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_RULES_TOML)
    history_root = tmp_path / "history"
    return csv_root, rules_path, history_root


def _run_backtest(out_root: Path, *, csv_root: Path, rules_path: Path, history_root: Path) -> Path:
    if not (history_root.exists() and any(history_root.iterdir())):
        r = runner.invoke(
            app,
            [
                "ingest-history",
                "--from-dir",
                str(csv_root),
                "--out-dir",
                str(history_root),
            ],
        )
        assert r.exit_code == 0, r.output
    bt = runner.invoke(
        app,
        [
            "backtest",
            "--rules",
            str(rules_path),
            "--from",
            "2024-01-02",
            "--to",
            "2024-01-10",
            "--out-dir",
            str(out_root),
            "--db",
            str(out_root.parent / "audit.db"),
            "--history-root",
            str(history_root),
            "--halt-path",
            str(out_root.parent / "HALT"),
            "--allow-kernel-edits",
        ],
    )
    assert bt.exit_code == 0, bt.output
    run_id_line = [
        ln for ln in bt.output.splitlines() if ln.startswith("backtest run_id: ")
    ][0]
    return out_root / run_id_line.split("backtest run_id: ", 1)[1].strip()


def test_byte_identical_metrics_csv(tmp_path: Path) -> None:
    csv_root, rules_path, history_root = _setup(tmp_path)
    a = _run_backtest(
        tmp_path / "out-a", csv_root=csv_root, rules_path=rules_path, history_root=history_root
    )
    b = _run_backtest(
        tmp_path / "out-b", csv_root=csv_root, rules_path=rules_path, history_root=history_root
    )
    assert (a / "metrics.csv").read_bytes() == (b / "metrics.csv").read_bytes()


def test_byte_identical_per_rule_orders_fills_rejections(tmp_path: Path) -> None:
    csv_root, rules_path, history_root = _setup(tmp_path)
    a = _run_backtest(
        tmp_path / "out-a", csv_root=csv_root, rules_path=rules_path, history_root=history_root
    )
    b = _run_backtest(
        tmp_path / "out-b", csv_root=csv_root, rules_path=rules_path, history_root=history_root
    )
    rule_dir_a = a / "per-rule" / "buy_aapl"
    rule_dir_b = b / "per-rule" / "buy_aapl"
    for name in ("orders.json", "fills.json", "gate-rejections.json"):
        assert (rule_dir_a / name).read_bytes() == (rule_dir_b / name).read_bytes(), name


def test_backtest_run_json_differs_only_in_volatile_fields(tmp_path: Path) -> None:
    """run_id, start_ts, end_ts differ — everything else is byte-stable."""
    csv_root, rules_path, history_root = _setup(tmp_path)
    a = _run_backtest(
        tmp_path / "out-a", csv_root=csv_root, rules_path=rules_path, history_root=history_root
    )
    b = _run_backtest(
        tmp_path / "out-b", csv_root=csv_root, rules_path=rules_path, history_root=history_root
    )
    pa = json.loads((a / "backtest-run.json").read_text())
    pb = json.loads((b / "backtest-run.json").read_text())

    # Volatile fields ARE allowed to differ.
    for k in ("run_id", "start_ts", "end_ts"):
        pa.pop(k, None)
        pb.pop(k, None)
    assert pa == pb
