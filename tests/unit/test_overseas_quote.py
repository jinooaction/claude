"""get_quote 견적 파싱 강건성 (KIS 가 빈/비숫자 가격을 줄 때, 헌법 VII)."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from auto_invest.broker.overseas import QuoteUnavailable, _opt_price, get_quote


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
