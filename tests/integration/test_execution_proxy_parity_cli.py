from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.backtest.data_source import trading_days_between
from auto_invest.cli import app
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db
from auto_invest.portfolio.execution_proxy_parity import (
    PREREGISTERED_EXECUTION_SYMBOL_MAP,
)

RUNNER = CliRunner()


def _portfolio(path: Path, *, spy_proxy: str = "SCHX") -> Path:
    path.write_text(
        f"""\
[execution]
symbol_map = {{ SPY = "{spy_proxy}", IEF = "SPTI", GLD = "IAUM" }}
lot_rounding = "nearest"
""",
        encoding="utf-8",
    )
    return path


def _bars_db(path: Path) -> Path:
    today = datetime.now(UTC).date()
    sessions = trading_days_between(today - timedelta(days=450), today)[-260:]
    conn = db.get_connection(path)
    db.migrate(conn)
    for pair_index, (signal, execution) in enumerate(
        PREREGISTERED_EXECUTION_SYMBOL_MAP.items()
    ):
        signal_price = Decimal(str(80 + pair_index * 20))
        execution_price = Decimal(str(25 + pair_index * 10))
        for index, session in enumerate(sessions):
            change = Decimal(str(0.0004 + 0.006 * ((index % 11) - 5) / 5))
            signal_price *= Decimal("1") + change
            execution_price *= Decimal("1") + change + Decimal(
                str(((index % 3) - 1) * 0.00005)
            )
            for symbol, close in ((signal, signal_price), (execution, execution_price)):
                insert_bar(
                    conn,
                    PriceBar(
                        symbol=symbol,
                        timeframe="1d",
                        bar_open_utc=f"{session.isoformat()}T00:00:00.000Z",
                        open_usd=close,
                        high_usd=close,
                        low_usd=close,
                        close_usd=close,
                        volume=3_000_000,
                    ),
                )
    conn.close()
    return path


def test_execution_proxy_parity_cli_emits_self_contained_pass(tmp_path: Path) -> None:
    result = RUNNER.invoke(
        app,
        [
            "execution-proxy-parity",
            "--portfolio", str(_portfolio(tmp_path / "live.toml")),
            "--bars-db", str(_bars_db(tmp_path / "bars.db")),
            "--format", "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is True
    assert payload["symbol_map"] == PREREGISTERED_EXECUTION_SYMBOL_MAP
    assert payload["evidence_digest"].startswith("sha256:")


def test_execution_proxy_parity_cli_rejects_non_preregistered_map(tmp_path: Path) -> None:
    result = RUNNER.invoke(
        app,
        [
            "execution-proxy-parity",
            "--portfolio", str(_portfolio(tmp_path / "live.toml", spy_proxy="SPYM")),
            "--bars-db", str(_bars_db(tmp_path / "bars.db")),
            "--format", "json",
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is False
    assert payload["checks"]["mapping_exact"] is False
