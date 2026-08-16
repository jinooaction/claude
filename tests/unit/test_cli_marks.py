"""Performance mark lookup: quote first, KIS balance valuation fallback second."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from auto_invest import cli
from auto_invest.broker import overseas


@pytest.mark.asyncio
async def test_fetch_marks_only_fills_missing_quotes_from_balance(monkeypatch, tmp_path) -> None:
    async def _token(*args, **kwargs):
        return SimpleNamespace(access_token="token")

    async def _quote(*args, symbol: str, **kwargs):
        if symbol == "ORANY":
            raise RuntimeError("standalone quote unavailable")
        return SimpleNamespace(last_price_usd=Decimal("200"))

    async def _balance_marks(*args, **kwargs):
        return {"AAPL": Decimal("199"), "ORANY": Decimal("19.02")}

    monkeypatch.setattr(cli, "get_valid_token", _token)
    monkeypatch.setattr(overseas, "get_quote_resolving_market", _quote)
    monkeypatch.setattr(overseas, "get_position_marks_resolving_market", _balance_marks)

    marks = await cli._fetch_marks(
        ["AAPL", "ORANY"],
        base_url="https://api.example",
        app_key="key",
        app_secret="secret",
        db_path=tmp_path / "live.db",
        account_no="1234567801",
    )

    assert marks == {"AAPL": Decimal("200"), "ORANY": Decimal("19.02")}
