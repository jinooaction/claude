"""SqliteBarDataSource — 라이브/페이퍼 워커의 price_bars 를 백테스트 데이터소스로 노출.

재지정 캐너리(스펙 055 ④)가 인스턴스 DB 바(토너먼트·라이브와 같은 바)로 챔피언을 검증할 수
있게 하는 어댑터. list_symbols / session_dates / read_bars / coverage_holes 를 검증한다.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from auto_invest.backtest.data_source import SqliteBarDataSource, trading_days_between
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db


def _insert_daily(conn, symbol: str, days: list[date], price_of) -> None:
    for i, d in enumerate(days):
        c = Decimal(str(price_of(i)))
        insert_bar(
            conn,
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=f"{d.isoformat()}T00:00:00.000Z",
                open_usd=c,
                high_usd=(c * Decimal("1.01")).quantize(Decimal("0.0001")),
                low_usd=(c * Decimal("0.99")).quantize(Decimal("0.0001")),
                close_usd=c,
                volume=1_000_000,
            ),
        )


def test_sqlite_bar_data_source_reads_bars(tmp_path: Path):
    conn = db.get_connection(tmp_path / "bars.db")
    db.migrate(conn)
    days = trading_days_between(date(2024, 1, 1), date(2024, 2, 15))
    _insert_daily(conn, "SPY", days, lambda i: 400 + i)
    _insert_daily(conn, "IEF", days, lambda i: 95 + i)

    src = SqliteBarDataSource(conn, timeframe="1d")
    assert src.list_symbols() == ["IEF", "SPY"]
    assert src.dataset_version == "sqlite-price_bars-1d"
    assert src.session_dates("SPY") == days

    bars = src.read_bars("SPY", days[0], days[4])
    assert len(bars) == 5
    assert bars[0].symbol == "SPY"
    assert bars[0].session_date == days[0]
    assert bars[0].close == Decimal("400")
    assert bars[0].session_schedule_tag == "regular"
    conn.close()


def test_sqlite_bar_data_source_coverage_holes(tmp_path: Path):
    conn = db.get_connection(tmp_path / "bars.db")
    db.migrate(conn)
    days = trading_days_between(date(2024, 1, 1), date(2024, 1, 31))
    # 앞쪽 절반만 적재 → 뒤쪽 거래일은 결손으로 잡혀야 한다.
    present = days[:8]
    _insert_daily(conn, "SPY", present, lambda i: 400 + i)

    src = SqliteBarDataSource(conn, timeframe="1d")
    holes = src.coverage_holes(["SPY"], days[0], days[-1])
    missing = {d for (_s, d) in holes}
    assert missing == set(days[8:])  # 적재 안 한 거래일이 정확히 결손
    # 적재 구간만 조회하면 결손 0.
    assert src.coverage_holes(["SPY"], days[0], present[-1]) == []
    conn.close()


def test_sqlite_bar_data_source_timeframe_filter(tmp_path: Path):
    conn = db.get_connection(tmp_path / "bars.db")
    db.migrate(conn)
    days = trading_days_between(date(2024, 1, 1), date(2024, 1, 10))
    _insert_daily(conn, "SPY", days, lambda i: 400 + i)
    # 다른 timeframe 의 어댑터는 일봉을 안 본다.
    src_intraday = SqliteBarDataSource(conn, timeframe="1h")
    assert src_intraday.list_symbols() == []
    assert src_intraday.read_bars("SPY", days[0], days[-1]) == []
    conn.close()
