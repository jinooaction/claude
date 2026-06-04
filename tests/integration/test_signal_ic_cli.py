"""스펙 041 — signal-ic CLI 통합 테스트.

`signal-ic` 가 포트폴리오 설정(유니버스·가중치·룩백)을 읽고 price_bars 에서 바를 읽어
합성 점수의 예측 성공률(IC)을 판정하는 엔드투엔드 경로를 검증한다. 돈 0 이동(읽기 전용).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db

runner = CliRunner()


def _iso(d: date) -> str:
    return f"{d.isoformat()}T00:00:00.000Z"


def _seed(conn, *, symbol: str, growth: float, n: int = 120) -> None:
    d0 = date(2026, 1, 1)
    price = 100.0
    for i in range(n):
        price *= 1.0 + growth
        px = Decimal(str(round(price, 4)))
        insert_bar(
            conn,
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=_iso(d0 + timedelta(days=i)),
                open_usd=px,
                high_usd=px,
                low_usd=px,
                close_usd=px,
                volume=1000,
            ),
        )


def _write_portfolio(tmp_path: Path, symbols: list[str]) -> Path:
    arr = "[" + ", ".join(f'"{s}"' for s in symbols) + "]"
    p = tmp_path / "port.toml"
    p.write_text(
        f"""
[caps]
per_trade_pct                  = 60.0
per_symbol_pct                 = 60.0
global_exposure_pct            = 100.0
canary_capital_pct             = 5.0
canary_min_duration_days       = 10
canary_acceptance_drawdown_pct = 30.0

[whitelist]
symbols     = {arr}
accounts    = ["BACKTEST"]
order_types = ["MARKET", "LIMIT"]
sessions    = ["REGULAR"]

[portfolio]
id            = "test"
universe      = {arr}
weights       = {{ momentum = "1.0" }}
weight_scheme = "equal"
top_n         = 2
lookback_bars   = 30
momentum_period = 10
""",
        encoding="utf-8",
    )
    return p


def test_signal_ic_cli_detects_prediction(tmp_path: Path) -> None:
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    growths = {"AAA": 0.001, "BBB": 0.004, "CCC": 0.007, "DDD": 0.010, "EEE": 0.013, "FFF": 0.016}
    for sym, g in growths.items():
        _seed(conn, symbol=sym, growth=g)
    conn.close()

    port = _write_portfolio(tmp_path, list(growths))
    result = runner.invoke(
        app,
        [
            "signal-ic",
            "--portfolio", str(port),
            "--db", str(db_path),
            "--forward-horizon", "10",
            "--step", "10",
            "--min-symbols", "5",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["mean_ic"] > 0.8  # 성장률↔모멘텀↔미래수익 순위 일치 → 강한 양의 IC
    assert payload["n_dates"] >= 4
    assert "예측력 있음" in payload["verdict"]
