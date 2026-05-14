"""Spec 007 T026 — kernel-touch detected during a canary run (R-C8).

The candidate-vs-baseline diff is computed by ``canary.diff.diff_paths``;
we monkey-patch it for this test so the orchestrator sees a synthetic
diff that touches K1 (``src/auto_invest/risk/gates.py``).

Assertions:

1. ``CANARY_KERNEL_TOUCH_DETECTED`` is emitted with the touched K1 group.
2. The metric battery STILL ran (CANARY_PASSED or CANARY_FAILED present).
3. Under v3.0.0 IX.A the kernel touch is forensic, not blocking; the
   final outcome reflects the metric results, not the touch.
4. ``canary-run.json.kernel_touches`` carries the K1 entry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from auto_invest.canary import diff as diff_module
from auto_invest.canary.cli import app as canary_app
from auto_invest.canary.data_model import KernelTouch
from auto_invest.canary.report import CANARY_RUN_JSON
from auto_invest.cli import app as main_app
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


def test_kernel_touching_candidate_emits_forensic_row_and_still_evaluates_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    csv_root = tmp_path / "history-csv"
    csv_root.mkdir()
    (csv_root / "AAPL.csv").write_text(_AAPL_CSV)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_RULES_TOML)
    history_root = tmp_path / "history"
    canary_out = tmp_path / "canary"
    db_path = tmp_path / "audit.db"

    runner.invoke(
        main_app,
        [
            "ingest-history",
            "--from-dir",
            str(csv_root),
            "--out-dir",
            str(history_root),
        ],
    )

    # Synthesise a diff that touches a K1 path. We patch BOTH the module
    # symbol (used internally) AND the symbol re-imported by run.py so
    # the orchestrator's call resolves to our mock.
    def fake_diff_paths(*, baseline_sha, candidate_sha, cwd=None):
        return ["src/auto_invest/risk/gates.py", "README.md"]

    monkeypatch.setattr(diff_module, "diff_paths", fake_diff_paths)
    from auto_invest.canary import run as run_module

    monkeypatch.setattr(run_module, "diff_paths", fake_diff_paths)

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
            str(tmp_path / "HALT"),
            "--skip-fuzz",
            "--skip-shock",
        ],
    )
    # v3.0.0 IX.A: kernel touch is forensic, not a halt. Outcome must reflect
    # metric battery (passes here because window replay is clean).
    assert result.exit_code == 0, result.output

    # Audit chain — touch row precedes terminal row, same correlation_id.
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        rows = audit.read_all(conn)
    finally:
        conn.close()
    event_types = [r["event_type"] for r in rows]
    assert "CANARY_ENTERED" in event_types
    assert "CANARY_KERNEL_TOUCH_DETECTED" in event_types
    assert "CANARY_PASSED" in event_types

    # Ordering: KERNEL_TOUCH between ENTERED and PASSED.
    entered_idx = event_types.index("CANARY_ENTERED")
    touch_idx = event_types.index("CANARY_KERNEL_TOUCH_DETECTED")
    passed_idx = event_types.index("CANARY_PASSED")
    assert entered_idx < touch_idx < passed_idx

    # Payload — touched_groups includes K1.
    touch_row = next(
        r for r in rows if r["event_type"] == "CANARY_KERNEL_TOUCH_DETECTED"
    )
    payload = json.loads(touch_row["payload_json"])
    assert "K1" in payload["touched_groups"]
    assert "src/auto_invest/risk/gates.py" in payload["touched_files"]

    # canary-run.json reflects the kernel-touch entry too.
    runs = list(canary_out.iterdir())
    assert len(runs) == 1
    blob = json.loads((runs[0] / CANARY_RUN_JSON).read_text())
    groups_in_run = [kt["group"] for kt in blob["kernel_touches"]]
    assert "K1" in groups_in_run


def test_non_kernel_diff_does_not_emit_kernel_touch_row(
    tmp_path: Path, monkeypatch
) -> None:
    """Sanity: a diff that touches only non-Kernel paths produces no row."""
    csv_root = tmp_path / "history-csv"
    csv_root.mkdir()
    (csv_root / "AAPL.csv").write_text(_AAPL_CSV)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_RULES_TOML)
    history_root = tmp_path / "history"
    canary_out = tmp_path / "canary"
    db_path = tmp_path / "audit.db"

    runner.invoke(
        main_app,
        [
            "ingest-history",
            "--from-dir",
            str(csv_root),
            "--out-dir",
            str(history_root),
        ],
    )

    def fake_diff_paths(*, baseline_sha, candidate_sha, cwd=None):
        return ["README.md", "docs/whatever.md"]

    from auto_invest.canary import run as run_module

    monkeypatch.setattr(run_module, "diff_paths", fake_diff_paths)

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
            str(tmp_path / "HALT"),
            "--skip-fuzz",
            "--skip-shock",
        ],
    )
    assert result.exit_code == 0, result.output

    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        events = [r["event_type"] for r in audit.read_all(conn)]
    finally:
        conn.close()
    assert "CANARY_KERNEL_TOUCH_DETECTED" not in events
