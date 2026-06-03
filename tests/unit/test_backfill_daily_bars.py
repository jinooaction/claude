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
