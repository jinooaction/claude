"""Integration tests for the CLI dry-run path (T046, T047)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from auto_invest.cli import app

runner = CliRunner()


VALID_RULES_TOML = """
[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL"]
accounts = ["${KIS_ACCOUNT_NO}"]

[[rules]]
id = "aapl-dip"
symbol = "AAPL"
stage = "CANARY"
priority = 10
enabled = true

  [rules.trigger]
  kind = "price"
  direction = "<="
  threshold = 100.0
  cooldown_seconds = 600

  [rules.action]
  side = "BUY"
  order_type = "LIMIT"
  qty = 1
  limit_price = "100.00"
"""


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_APP_KEY", "test-app-key-12345")
    monkeypatch.setenv("KIS_APP_SECRET", "test-app-secret-12345")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "1234567801")


def _write_rules(tmp_path: Path, body: str = VALID_RULES_TOML) -> Path:
    p = tmp_path / "rules.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_dry_run_succeeds_with_valid_config(env, tmp_path: Path):
    rules = _write_rules(tmp_path)
    db_path = tmp_path / "data" / "auto_invest.db"
    halt_path = tmp_path / "data" / "halt.flag"

    result = runner.invoke(
        app,
        [
            "run",
            "--dry-run",
            "--config",
            str(rules),
            "--db",
            str(db_path),
            "--halt-path",
            str(halt_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Dry run successful" in result.output
    assert "AAPL" in result.output
    # The CLI applies pending migrations during a dry run so a follow-up
    # live run does not need a separate migrate step.
    assert db_path.exists()


def test_dry_run_exit_2_on_missing_secret(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    monkeypatch.delenv("KIS_ACCOUNT_NO", raising=False)
    rules = _write_rules(tmp_path)

    result = runner.invoke(
        app,
        ["run", "--dry-run", "--config", str(rules)],
    )
    assert result.exit_code == 2
    assert "Configuration error" in result.output or "required secret" in result.output


def test_dry_run_exit_2_on_invalid_caps(env, tmp_path: Path):
    bad_rules = VALID_RULES_TOML.replace(
        "per_trade_pct = 5.0",
        "per_trade_pct = 30.0",  # 30 > per_symbol 20
    )
    rules = _write_rules(tmp_path, bad_rules)

    result = runner.invoke(
        app,
        ["run", "--dry-run", "--config", str(rules)],
    )
    assert result.exit_code == 2


def test_dry_run_exit_2_on_unknown_symbol(env, tmp_path: Path):
    bad_rules = VALID_RULES_TOML.replace('symbols = ["AAPL"]', 'symbols = ["MSFT"]')
    rules = _write_rules(tmp_path, bad_rules)

    result = runner.invoke(
        app,
        ["run", "--dry-run", "--config", str(rules)],
    )
    assert result.exit_code == 2


def test_dry_run_exit_2_on_stage_uniqueness_conflict(env, tmp_path: Path):
    bad_rules = (
        VALID_RULES_TOML
        + """
[[rules]]
id = "aapl-live"
symbol = "AAPL"
stage = "FULL_LIVE"
priority = 20
enabled = true

  [rules.trigger]
  kind = "price"
  direction = ">="
  threshold = 200.0
  cooldown_seconds = 600

  [rules.action]
  side = "SELL"
  order_type = "LIMIT"
  qty = 1
  limit_price = "200.00"
"""
    )
    rules = _write_rules(tmp_path, bad_rules)

    result = runner.invoke(
        app,
        ["run", "--dry-run", "--config", str(rules)],
    )
    assert result.exit_code == 2
    assert "Stage-uniqueness denied" in result.output


def test_live_run_refuses_zero_capital(env, tmp_path: Path):
    """Live run with no --capital must fail at the capital validation
    step (after migrations are applied via a one-time dry-run)."""
    rules = _write_rules(tmp_path)
    db_path = tmp_path / "t.db"

    # Apply migrations once via dry-run so we hit the capital gate cleanly.
    runner.invoke(
        app,
        [
            "run",
            "--dry-run",
            "--config",
            str(rules),
            "--db",
            str(db_path),
            "--halt-path",
            str(tmp_path / "halt.flag"),
        ],
    )

    result = runner.invoke(
        app,
        [
            "run",
            "--config",
            str(rules),
            "--db",
            str(db_path),
            "--halt-path",
            str(tmp_path / "halt.flag"),
        ],
    )
    assert result.exit_code == 2
    assert "--capital" in result.output


def test_python_module_form_invokes_cli():
    """`python -m auto_invest --help` should exit 0 and show the usage banner."""
    import subprocess

    result = subprocess.run(
        ["python", "-m", "auto_invest", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    combined = (result.stdout + result.stderr).lower()
    assert "auto_invest" in combined or "usage:" in combined
