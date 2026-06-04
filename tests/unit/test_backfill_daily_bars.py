"""스펙 033 — backfill_daily_bars 공유 헬퍼 (KIS 일봉 → price_bars)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from auto_invest.market_data.feed import backfill_daily_bars
from auto_invest.market_data.store import bar_summary
from auto_invest.persistence import db


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._p = payload

    def json(self) -> dict:
        return self._p


class _FakeClient:
    """params['EXCD'] 로 거래소별 output2 를 반환. 호출 기록 보관."""

    def __init__(self, by_excd: dict[str, list[dict]]) -> None:
        self.by_excd = by_excd
        self.calls: list[tuple[str, str]] = []

    async def request(self, method, path, *, headers=None, params=None):  # noqa: ANN001
        excd = params["EXCD"]
        self.calls.append((excd, params["SYMB"]))
        return _Resp({"output2": self.by_excd.get(excd, [])})


def _row(xymd: str, c: str) -> dict:
    return {"xymd": xymd, "open": c, "high": c, "low": c, "clos": c, "tvol": "1000"}


def test_backfill_stores_bars_and_reports(tmp_path: Path):
    conn = db.get_connection(tmp_path / "a.db")
    db.migrate(conn)
    client = _FakeClient(
        {"NAS": [_row("20260601", "100"), _row("20260602", "101")]}
    )
    res = asyncio.run(
        backfill_daily_bars(
            conn, client, access_token="t", app_key="k", app_secret="s",
            symbols=["AAPL"], exchanges=("NAS", "NYS"),
        )
    )
    assert res == [{"symbol": "AAPL", "exchange": "NAS", "fetched": 2, "inserted": 2}]
    n, lo, hi = bar_summary(conn, symbol="AAPL", timeframe="1d")
    assert n == 2 and lo == "2026-06-01T00:00:00.000Z" and hi == "2026-06-02T00:00:00.000Z"
    conn.close()


def test_backfill_tries_exchanges_until_hit(tmp_path: Path):
    conn = db.get_connection(tmp_path / "a.db")
    db.migrate(conn)
    # NAS 빈값 → NYS 에서 적중해야 한다.
    client = _FakeClient({"NYS": [_row("20260602", "50")]})
    res = asyncio.run(
        backfill_daily_bars(
            conn, client, access_token="t", app_key="k", app_secret="s",
            symbols=["JPM"], exchanges=("NAS", "NYS", "AMS"),
        )
    )
    assert res[0]["exchange"] == "NYS" and res[0]["inserted"] == 1
    assert ("NAS", "JPM") in client.calls and ("NYS", "JPM") in client.calls
    conn.close()


def test_backfill_idempotent_second_run_inserts_zero(tmp_path: Path):
    conn = db.get_connection(tmp_path / "a.db")
    db.migrate(conn)
    client = _FakeClient({"NAS": [_row("20260602", "100")]})
    kw = dict(access_token="t", app_key="k", app_secret="s", symbols=["AAPL"], exchanges=("NAS",))
    asyncio.run(backfill_daily_bars(conn, client, **kw))
    res2 = asyncio.run(backfill_daily_bars(conn, client, **kw))
    assert res2[0]["inserted"] == 0 and res2[0]["fetched"] == 1
    conn.close()


class _PaginatingClient:
    """스펙 041 — KIS BYMD(기준일) 기준 ~page_size 세션을 준다(과거 페이지네이션 시뮬)."""

    def __init__(self, dates: list[str], page_size: int = 4) -> None:
        self.dates = sorted(dates)  # 오름차순 YYYYMMDD
        self.page_size = page_size
        self.bymds: list[str] = []

    async def request(self, method, path, *, headers=None, params=None):  # noqa: ANN001
        bymd = params["BYMD"]
        self.bymds.append(bymd)
        pool = self.dates if bymd == "" else [d for d in self.dates if d <= bymd]
        window = pool[-self.page_size :]  # bymd 이하 중 가장 최근 page_size
        return _Resp({"output2": [_row(d, "100") for d in window]})


def test_backfill_paginates_deep_to_min_bars(tmp_path: Path):
    conn = db.get_connection(tmp_path / "a.db")
    db.migrate(conn)
    # 2026-06-01 … 06-12 (연속 12일), 페이지당 4 → min_bars=10 이면 깊게 채워야 한다.
    dates = [f"202606{d:02d}" for d in range(1, 13)]
    client = _PaginatingClient(dates, page_size=4)
    res = asyncio.run(
        backfill_daily_bars(
            conn, client, access_token="t", app_key="k", app_secret="s",
            symbols=["AAPL"], exchanges=("NAS",), min_bars=10,
        )
    )
    n, lo, hi = bar_summary(conn, symbol="AAPL", timeframe="1d")
    assert n == 12  # 12일 전체 누적(중복 제거)
    assert res[0]["inserted"] == 12
    assert len(client.bymds) >= 3  # 여러 페이지(기준일 이동)로 페이지네이션 발생
    assert client.bymds[0] == "" and client.bymds[1] != ""  # 첫 최근 → 이후 과거 기준일
    conn.close()


def test_backfill_pagination_stops_when_no_older_data(tmp_path: Path):
    conn = db.get_connection(tmp_path / "a.db")
    db.migrate(conn)
    # 5일치만 존재하는데 min_bars=50 → 무한루프 없이 5개에서 멈춰야 한다.
    dates = [f"202606{d:02d}" for d in range(1, 6)]
    client = _PaginatingClient(dates, page_size=4)
    res = asyncio.run(
        backfill_daily_bars(
            conn, client, access_token="t", app_key="k", app_secret="s",
            symbols=["AAPL"], exchanges=("NAS",), min_bars=50,
        )
    )
    n, _, _ = bar_summary(conn, symbol="AAPL", timeframe="1d")
    assert n == 5 and res[0]["inserted"] == 5  # 더 과거 없음 → 종료
    conn.close()
