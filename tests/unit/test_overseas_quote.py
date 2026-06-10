"""get_quote 견적 파싱 강건성 (KIS 가 빈/비숫자 가격을 줄 때, 헌법 VII)."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from auto_invest.broker.overseas import (
    QUOTE_EXCHANGES,
    QuoteUnavailable,
    _opt_price,
    get_quote,
    get_quote_resolving_market,
)


def test_opt_price_parses_numeric() -> None:
    assert _opt_price("312.48") == Decimal("312.48")
    assert _opt_price(95) == Decimal("95")


def test_opt_price_blank_or_garbage_is_none() -> None:
    # KIS 가 빈 문자열·공백·비숫자를 줄 때 예외 대신 None (graceful).
    assert _opt_price("") is None
    assert _opt_price("   ") is None
    assert _opt_price(None) is None
    assert _opt_price("N/A") is None


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._p = payload

    def json(self) -> dict:
        return self._p


class _FakeClient:
    def __init__(self, output: dict) -> None:
        self._output = output

    async def request(self, method, path, *, headers=None, params=None):  # noqa: ANN001
        return _Resp({"output": self._output})


def _quote(output: dict):
    return asyncio.run(
        get_quote(
            _FakeClient(output),
            access_token="t",
            app_key="k",
            app_secret="s",
            symbol="AAPL",
        )
    )


def test_get_quote_parses_full_output() -> None:
    q = _quote({"last": "312.48", "bidp": "312.40", "askp": "312.55"})
    assert q.last_price_usd == Decimal("312.48")
    assert q.bid_usd == Decimal("312.40")
    assert q.ask_usd == Decimal("312.55")


def test_get_quote_blank_last_raises_clear_error() -> None:
    # 실제 관측된 버그: KIS 가 last="" 를 주면 decimal.InvalidOperation 대신
    # 심볼이 적힌 명확한 QuoteUnavailable 을 던져 호출자가 종목을 건너뛸 수 있어야 한다.
    with pytest.raises(QuoteUnavailable, match="AAPL"):
        _quote({"last": "", "bidp": "312.40", "askp": "312.55"})


def test_get_quote_blank_bid_ask_become_none() -> None:
    q = _quote({"last": "312.48", "bidp": "", "askp": ""})
    assert q.last_price_usd == Decimal("312.48")
    assert q.bid_usd is None
    assert q.ask_usd is None


# ── 거래소 자동 해석 (get_quote_resolving_market) — SPY·GLD 가 AMS 상장이라 NAS 고정 실패 ──


class _ExchangeAwareClient:
    """EXCD(거래소)별로 다른 output 을 돌려주는 가짜 KIS 클라이언트.

    실제 KIS 동작 모사: 심볼이 상장되지 않은 거래소로 물으면 last 가 빈 값으로 온다.
    """

    def __init__(self, output_by_excd: dict[str, dict]) -> None:
        self._by_excd = output_by_excd
        self.calls: list[str] = []

    async def request(self, method, path, *, headers=None, params=None):  # noqa: ANN001
        excd = params["EXCD"]
        self.calls.append(excd)
        # 등록 안 된 거래소는 빈 last (= 그 거래소에 미상장) 모사.
        return _Resp({"output": self._by_excd.get(excd, {"last": ""})})


def test_resolving_market_finds_symbol_on_ams() -> None:
    # SPY 는 NAS·NYS 엔 없고 AMS 에만 있다 — 고정 NAS 라면 실패했을 상황.
    client = _ExchangeAwareClient({"AMS": {"last": "540.12"}})
    q = asyncio.run(
        get_quote_resolving_market(
            client, access_token="t", app_key="k", app_secret="s", symbol="SPY"
        )
    )
    assert q.last_price_usd == Decimal("540.12")
    # NAS→NYS→AMS 순서로 시도하고 AMS 에서 멈췄어야 한다.
    assert client.calls == ["NAS", "NYS", "AMS"]


def test_resolving_market_stops_at_first_usable() -> None:
    # NAS 에서 바로 잡히면 더 시도하지 않는다(불필요한 API 호출 방지).
    client = _ExchangeAwareClient({"NAS": {"last": "290.55"}, "AMS": {"last": "1.00"}})
    q = asyncio.run(
        get_quote_resolving_market(
            client, access_token="t", app_key="k", app_secret="s", symbol="AAPL"
        )
    )
    assert q.last_price_usd == Decimal("290.55")
    assert client.calls == ["NAS"]


def test_resolving_market_all_blank_raises_quote_unavailable() -> None:
    # 어느 거래소에도 없으면 마지막 QuoteUnavailable 전파(호출자가 종목 스킵).
    client = _ExchangeAwareClient({})
    with pytest.raises(QuoteUnavailable, match="ZZZZ"):
        asyncio.run(
            get_quote_resolving_market(
                client, access_token="t", app_key="k", app_secret="s", symbol="ZZZZ"
            )
        )
    assert client.calls == list(QUOTE_EXCHANGES)
