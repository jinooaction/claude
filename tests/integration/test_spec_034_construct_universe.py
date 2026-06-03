"""스펙 034 — rebalance-once --construct-universe-top-n CLI 배선 테스트.

현재 저장된 바에서 유동성(중앙값 달러 거래대금) 상위로 유니버스를 *구성*하는 옵션이
dry-run 경로에서 의도대로 동작하는지 확인한다: 가장 유동성 높은 N개를 고르고, 기본값
(0=off)이면 설정 유니버스 무변경. 돈 안 움직임(dry-run — 라우터 미호출).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db

runner = CliRunner()
_D0 = datetime(2023, 1, 3, tzinfo=UTC)


def _seed(conn, symbol: str, volume: int, n: int = 35, base: float = 100.0) -> None:
    for i in range(n):
        price = Decimal(str(base + i * 0.1))
        insert_bar(
            conn,
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=(_D0 + timedelta(days=i)).strftime(
                    "%Y-%m-%dT00:00:00.000Z"
                ),
                open_usd=price,
                high_usd=price,
                low_usd=price,
                close_usd=price,
                volume=volume,
            ),
        )


_PORTFOLIO = """
[caps]
per_trade_pct = 10.0
per_symbol_pct = 12.0
global_exposure_pct = 100.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 40.0

[whitelist]
symbols = ["AAA", "BBB", "CCC", "DDD"]
accounts = ["BACKTEST"]
order_types = ["LIMIT"]
sessions = ["REGULAR"]

[portfolio]
id = "construct-test"
universe = ["AAA", "BBB", "CCC", "DDD"]
weights = { momentum = "1.0" }
weight_scheme = "equal"
top_n = 2
lookback_bars = 30
momentum_period = 10
"""


def _prep(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "data" / "auto_invest.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    # Distinct liquidity: AAA > BBB > CCC > DDD (median dollar volume = close × volume).
    _seed(conn, "AAA", 1_000_000)
    _seed(conn, "BBB", 500_000)
    _seed(conn, "CCC", 100_000)
    _seed(conn, "DDD", 1_000)
    conn.close()
    pf = tmp_path / "pf.toml"
    pf.write_text(_PORTFOLIO, encoding="utf-8")
    return db_path, pf


def test_construct_universe_keeps_most_liquid(tmp_path: Path) -> None:
    db_path, pf = _prep(tmp_path)
    result = runner.invoke(
        app,
        [
            "rebalance-once",
            "--dry-run",
            "--portfolio",
            str(pf),
            "--db",
            str(db_path),
            "--capital",
            "100000",
            "--construct-universe-top-n",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    line = next(
        ln for ln in result.output.splitlines() if "construct-universe:" in ln
    )
    # Top-2 by liquidity = AAA, BBB; least-liquid DDD excluded.
    assert "AAA" in line and "BBB" in line
    assert "DDD" not in line
    assert "2/4" in line  # 2 of 4 candidates kept


def test_construct_universe_off_by_default(tmp_path: Path) -> None:
    db_path, pf = _prep(tmp_path)
    result = runner.invoke(
        app,
        [
            "rebalance-once",
            "--dry-run",
            "--portfolio",
            str(pf),
            "--db",
            str(db_path),
            "--capital",
            "100000",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "construct-universe:" not in result.output


def test_construct_universe_keeps_original_when_too_few_eligible(tmp_path: Path) -> None:
    # min_history_bars = lookback_bars(30); ask for top-3 but only AAA has >=30 bars
    # → fewer than 2 eligible → keep the configured universe unchanged (with a note).
    db_path = tmp_path / "data" / "auto_invest.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    _seed(conn, "AAA", 1_000_000, n=35)
    _seed(conn, "BBB", 500_000, n=5)  # too little history
    _seed(conn, "CCC", 100_000, n=5)
    _seed(conn, "DDD", 1_000, n=5)
    conn.close()
    pf = tmp_path / "pf.toml"
    pf.write_text(_PORTFOLIO, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "rebalance-once",
            "--dry-run",
            "--portfolio",
            str(pf),
            "--db",
            str(db_path),
            "--capital",
            "100000",
            "--construct-universe-top-n",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "적격 종목이 2개 미만" in result.output
