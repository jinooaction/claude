"""Live rebalance must fail closed outside the XNYS regular session."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from auto_invest.cli import (
    _live_rebalance_session_refusal,
    _rebalance_exit_code,
    app,
)
from auto_invest.execution.rebalancer import RebalanceOrderResult, RebalanceOutcome


def test_live_order_is_allowed_during_regular_session() -> None:
    refusal = _live_rebalance_session_refusal(
        mode="live",
        dry_run=False,
        now=datetime(2026, 8, 31, 14, 17, tzinfo=UTC),
    )

    assert refusal is None


def test_live_order_is_refused_after_regular_session() -> None:
    refusal = _live_rebalance_session_refusal(
        mode="live",
        dry_run=False,
        now=datetime(2026, 8, 31, 22, 17, tzinfo=UTC),
    )

    assert refusal is not None
    assert "XNYS regular session is closed" in refusal
    assert "2026-09-01T13:30:00+00:00" in refusal


def test_live_order_is_refused_on_market_holiday() -> None:
    refusal = _live_rebalance_session_refusal(
        mode="live",
        dry_run=False,
        now=datetime(2026, 9, 7, 14, 17, tzinfo=UTC),
    )

    assert refusal is not None
    assert "2026-09-08T13:30:00+00:00" in refusal


def test_paper_and_dry_run_do_not_require_an_open_session() -> None:
    closed = datetime(2026, 8, 31, 22, 17, tzinfo=UTC)

    assert _live_rebalance_session_refusal(mode="paper", dry_run=False, now=closed) is None
    assert _live_rebalance_session_refusal(mode="live", dry_run=True, now=closed) is None


def test_rebalance_cli_checks_session_before_db_write_or_broker_access() -> None:
    source = (Path(__file__).resolve().parents[2] / "src/auto_invest/cli.py").read_text(
        encoding="utf-8"
    )
    command = source.split('@app.command("rebalance-once")', 1)[1].split(
        '\n@app.command(', 1
    )[0]

    guard = command.index("_live_rebalance_session_refusal(")
    assert guard < command.index("_require_clean_migrations(")
    assert guard < command.index("async def _go()")
    assert "--ignore-session-window" not in command


def test_live_rebalance_serializes_kis_rest_without_initial_burst() -> None:
    source = (Path(__file__).resolve().parents[2] / "src/auto_invest/cli.py").read_text(
        encoding="utf-8"
    )
    command = source.split('@app.command("rebalance-once")', 1)[1].split(
        '\n@app.command(', 1
    )[0]

    live = command.split("async def _go()", 1)[1]
    assert "AsyncTokenBucket(rate_per_sec=5.0, capacity=1.0)" in live
    assert "AsyncTokenBucket(rate_per_sec=15.0, capacity=15.0)" not in live


def test_kis_order_write_is_never_replayed_by_http_retry() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "src/auto_invest/broker/overseas.py"
    ).read_text(encoding="utf-8")
    order = source.split("async def place_order(", 1)[1].split("\n\nasync def ", 1)[0]

    assert "retry_transient=False" in order


def test_closed_session_cli_refusal_happens_before_db_or_broker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio = tmp_path / "portfolio.toml"
    portfolio.write_text(
        """
[caps]
per_trade_pct = 5
per_symbol_pct = 20
global_exposure_pct = 80
canary_capital_pct = 10
canary_min_duration_days = 5
canary_acceptance_drawdown_pct = 3

[whitelist]
symbols = ["AAPL", "MSFT"]
accounts = ["TEST"]
order_types = ["LIMIT"]
sessions = ["REGULAR"]

[portfolio]
id = "session-guard-test"
universe = ["AAPL", "MSFT"]
weights = { momentum = "1" }
top_n = 1
weight_scheme = "equal"
invested_fraction = "0.5"
lookback_bars = 30
momentum_period = 10
""".strip()
        + "\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "must-not-exist.db"
    monkeypatch.setattr(
        "auto_invest.cli._live_rebalance_session_refusal",
        lambda **_kwargs: "REFUSED: XNYS regular session is closed",
    )

    result = CliRunner().invoke(
        app,
        [
            "rebalance-once",
            "--portfolio",
            str(portfolio),
            "--mode",
            "live",
            "--confirm-live",
            "--capital",
            "100",
            "--db",
            str(db_path),
        ],
    )

    assert result.exit_code == 75, result.output
    assert "XNYS regular session is closed" in result.output
    assert not db_path.exists()


def test_mid_run_session_rejection_propagates_temporary_failure() -> None:
    outcome = RebalanceOutcome(
        portfolio_id="session-guard-test",
        target_weights={},
        planned=[],
        results=[
            RebalanceOrderResult(
                symbol="AAPL",
                side="BUY",
                requested_qty=1,
                routed_qty=1,
                limit_price_usd=1,
                state="REJECTED_BY_GATE",
                correlation_id="ord-closed",
                gate="market_hours_gate",
                reason="XNYS regular session is closed",
            )
        ],
    )

    assert _rebalance_exit_code(outcome) == 75
