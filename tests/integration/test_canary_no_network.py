"""Spec 007 T031 — zero outbound network during a canary run.

Per ``contracts/canary-cli.md`` § "Side-effect contract": a successful
canary invocation MUST NOT touch the network. We enforce by monkey-
patching ``socket.socket.connect`` to raise on any attempt; any code path
that opens a TCP connection (live KIS, real Anthropic, etc.) would trip.

This is the canary's defence against a future change that accidentally
imports a real-broker adapter at module load time, or a judgment-stub
regression that calls the real Anthropic client.
"""

from __future__ import annotations

import socket
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.canary.cli import app as canary_app
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


class _NetworkProhibited(RuntimeError):
    pass


def test_canary_run_makes_zero_outbound_connections(
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

    # Ingest BEFORE installing the guard — ingest itself is local and
    # never makes network calls in spec 008 v1, but we play it safe by
    # not running the guard during setup.
    ingest = runner.invoke(
        main_app,
        ["ingest-history", "--from-dir", str(csv_root), "--out-dir", str(history_root)],
    )
    assert ingest.exit_code == 0, ingest.output

    # Install the guard. Any TCP connect attempt during the canary run
    # raises and the run aborts. Unix-domain sockets (used by some pytest
    # plugins) pass through so the test harness keeps working.
    real_connect = socket.socket.connect

    def guarded_connect(self, address, *args, **kwargs):
        family = getattr(self, "family", None)
        # AF_UNIX = 1 on Linux; let local UDS through (pytest, coverage, etc.)
        if family == socket.AF_UNIX:
            return real_connect(self, address, *args, **kwargs)
        # AF_INET / AF_INET6 attempts during the canary are forbidden.
        raise _NetworkProhibited(
            f"canary attempted outbound socket connect to {address!r}; "
            f"see contracts/canary-cli.md § Side-effect contract"
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

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
            "--skip-fuzz",  # fuzz is local; skip to keep test fast
            "--skip-shock",  # shock data absent from fixture
        ],
    )
    # The canary completed without triggering the network guard.
    assert result.exit_code == 0, result.output
    assert "CANARY_PASSED" in result.output
