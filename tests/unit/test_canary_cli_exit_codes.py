"""Spec 007 T035 — CLI exit-code matrix (contracts/canary-cli.md).

Maps each exit code to a deterministic invocation:

  0 — CANARY_PASSED (covered by test_canary_end_to_end)
  1 — CANARY_FAILED (covered by test_canary_audit_integrity_drop)
  2 — coverage-incomplete (here)
  3 — internal error (here)
  4 — CLI usage error (here)
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from auto_invest.canary.cli import app as canary_app

runner = CliRunner()


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


def test_exit_4_on_invalid_tier(tmp_path: Path) -> None:
    rules = tmp_path / "rules.toml"
    rules.write_text(_RULES_TOML)
    result = runner.invoke(
        canary_app,
        [
            "run",
            "--tier",
            "L9",
            "--rules",
            str(rules),
            "--from",
            "2024-01-02",
            "--to",
            "2024-01-10",
        ],
    )
    assert result.exit_code == 4


def test_exit_4_on_inverted_dates(tmp_path: Path) -> None:
    rules = tmp_path / "rules.toml"
    rules.write_text(_RULES_TOML)
    result = runner.invoke(
        canary_app,
        [
            "run",
            "--tier",
            "L2",
            "--rules",
            str(rules),
            "--from",
            "2024-01-10",
            "--to",
            "2024-01-02",
        ],
    )
    assert result.exit_code == 4


def test_exit_4_on_unparseable_dates(tmp_path: Path) -> None:
    rules = tmp_path / "rules.toml"
    rules.write_text(_RULES_TOML)
    result = runner.invoke(
        canary_app,
        [
            "run",
            "--tier",
            "L2",
            "--rules",
            str(rules),
            "--from",
            "not-a-date",
            "--to",
            "2024-01-02",
        ],
    )
    assert result.exit_code == 4


def test_exit_4_on_missing_required_dates(tmp_path: Path) -> None:
    rules = tmp_path / "rules.toml"
    rules.write_text(_RULES_TOML)
    result = runner.invoke(
        canary_app,
        ["run", "--tier", "L2", "--rules", str(rules)],
    )
    assert result.exit_code == 4


def test_exit_4_on_missing_dataset(tmp_path: Path) -> None:
    """No ingested dataset under --history-root → usage error (exit 4)."""
    rules = tmp_path / "rules.toml"
    rules.write_text(_RULES_TOML)
    result = runner.invoke(
        canary_app,
        [
            "run",
            "--tier",
            "L2",
            "--rules",
            str(rules),
            "--from",
            "2024-01-02",
            "--to",
            "2024-01-10",
            "--history-root",
            str(tmp_path / "empty-history"),
        ],
    )
    assert result.exit_code == 4


def test_exit_4_on_invalid_run_id(tmp_path: Path) -> None:
    rules = tmp_path / "rules.toml"
    rules.write_text(_RULES_TOML)
    result = runner.invoke(
        canary_app,
        [
            "run",
            "--tier",
            "L2",
            "--rules",
            str(rules),
            "--from",
            "2024-01-02",
            "--to",
            "2024-01-10",
            "--run-id",
            "not-a-uuid",
        ],
    )
    assert result.exit_code == 4
