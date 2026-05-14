"""Spec 007 T027 — audit-integrity regression fails the canary.

Spec.md US2 independent test: "inject a synthetic test that drops
1/1000 fills; verify the canary's audit-integrity check rejects."

We simulate the regression at the metric-counting boundary rather than
inside spec 008's replay loop: the integrity count is what the candidate
code would have observed during replay, so monkey-patching the counter
exercises the same code path the canary uses to decide.

Assertions:
  - exit code 1 (CANARY_FAILED)
  - audit row CANARY_FAILED with failing_metrics: ["audit_integrity_failures"]
  - the other four metrics PASS (drawdown clean, gate-violations 0, etc.)
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.canary import replay_window as replay_module
from auto_invest.canary.cli import app as canary_app
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


def test_audit_integrity_regression_rejects_canary(
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
        ["ingest-history", "--from-dir", str(csv_root), "--out-dir", str(history_root)],
    )

    # Inject the regression: candidate code's replay produces N quality
    # issues. FR-C01 #3 pins the band at 0; any non-zero count fails.
    def buggy_count(run, run_dir):  # noqa: ARG001
        return 3  # 3 data-quality issues "observed" by candidate

    monkeypatch.setattr(replay_module, "_count_audit_integrity", buggy_count)

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
    assert result.exit_code == 1, result.output  # CANARY_FAILED
    assert "CANARY_FAILED" in result.output

    # Audit row carries the failing metric.
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        rows = audit.read_all(conn)
    finally:
        conn.close()
    failed_rows = [r for r in rows if r["event_type"] == "CANARY_FAILED"]
    assert len(failed_rows) == 1
    payload = json.loads(failed_rows[0]["payload_json"])
    assert payload["failing_metrics"] == ["audit_integrity_failures"]

    # canary-run.json reflects per-metric truth.
    runs = list(canary_out.iterdir())
    assert len(runs) == 1
    blob = json.loads((runs[0] / CANARY_RUN_JSON).read_text())
    assert blob["outcome"] == "failed"
    assert blob["failing_metrics"] == ["audit_integrity_failures"]

    # Other 4 metrics PASS — this is the load-bearing US2 assertion: PnL
    # alone would not have caught the regression, audit-integrity did.
    metrics = blob["metrics"]
    assert metrics["pnl_drawdown_pct"]["inside_band"] is True
    assert metrics["risk_gate_violations"]["inside_band"] is True
    assert metrics["audit_integrity_failures"]["inside_band"] is False
    assert metrics["audit_integrity_failures"]["observed_value"] == 3.0
    assert metrics["latency_p95_regression_pct"]["inside_band"] is True
    assert metrics["llm_cost_regression_pct"]["inside_band"] is True
