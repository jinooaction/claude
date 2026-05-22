"""Optional live KIS smoke test (T064 + 회귀 방어).

Gated by KIS_LIVE_TEST=1. NEVER runs in CI without explicit opt-in.
Verifies that the overseas-equity adapter shapes match the real broker:

  - issue token + fetch one AAPL quote (T064 원본)
  - fetch USD purchasable cash (회귀: KIS 잔고 0원 표시 버그)
  - fetch positions snapshot (회귀: 보유 포트폴리오 stub)
  - fetch combined balance (cash + 평가금액 합)

Places NO orders. Read-only endpoints only.

Run via:
    KIS_LIVE_TEST=1 uv run pytest tests/integration/test_live_broker.py -v

GitHub Actions의 `KIS smoke (autonomous)` workflow가 매 main push와 매일
03:00 UTC에 인스턴스로 SSH 접속해 자동 실행한다 — 회귀가 운영자 손을
거치지 않고 즉시 잡힘 (자율 수행 정책 v3.0.0 IX.D).

토큰 발급은 module-scoped fixture로 1회만 수행. KIS OAuth API 는 짧은
시간 내 중복 토큰 발급에 대해 403 Forbidden 을 반환하므로, 4개 테스트
가 각자 토큰을 발급하면 첫 번째는 성공해도 나머지는 throttle 에 막힘.
"""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import httpx
import pytest

from auto_invest.broker.auth import issue_token
from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.broker.overseas import (
    get_balance,
    get_positions,
    get_purchasable_cash_usd,
    get_quote,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("KIS_LIVE_TEST") != "1",
    reason="Live KIS smoke test gated by KIS_LIVE_TEST=1",
)


KIS_BASE_URL = os.environ.get("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")


def _required_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        pytest.skip(f"{name} 가 환경에 없어 라이브 smoke 건너뜀")
    return val


@pytest.fixture(scope="module")
def kis_token_bundle() -> dict:
    """KIS OAuth 토큰을 module 단위 1회 발급. 4개 테스트가 공유.

    KIS API 는 짧은 시간 내 중복 토큰 발급을 403 Forbidden 으로 거부함
    (rate limit). per-test 토큰 발급 패턴은 첫 번째 테스트만 성공하고
    나머지가 throttle 에 막히는 회귀를 일으킴 (run 26311865850 에서
    실제 관측).

    Sync fixture 안에서 `asyncio.run` 으로 토큰 1회 발급 → dict 반환.
    각 async 테스트는 자기 event loop 에서 dict 의 access_token 만
    재사용해 새 KIS endpoint 호출.
    """
    app_key = _required_env("KIS_APP_KEY")
    app_secret = _required_env("KIS_APP_SECRET")

    async def _issue() -> object:
        async with httpx.AsyncClient(base_url=KIS_BASE_URL, timeout=30.0) as inner:
            return await issue_token(
                inner,
                base_url=KIS_BASE_URL,
                app_key=app_key,
                app_secret=app_secret,
            )

    token = asyncio.run(_issue())
    return {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "app_key": app_key,
        "app_secret": app_secret,
    }


def _make_broker(client: httpx.AsyncClient) -> ResilientClient:
    """모든 테스트가 동일한 ResilientClient 설정을 쓰도록 헬퍼."""
    return ResilientClient(
        client,
        rate_limiter=AsyncTokenBucket(rate_per_sec=15.0, capacity=15.0),
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0),
        max_retries=2,
    )


@pytest.mark.asyncio
async def test_live_kis_token_and_quote(kis_token_bundle: dict) -> None:
    """Token (fixture) + AAPL quote (T064 원본).

    Token 자체는 module fixture 에서 발급. 본 테스트는 토큰 형식
    검증 + 그 토큰으로 quote endpoint 호출만 검증.
    """
    access_token = kis_token_bundle["access_token"]
    app_key = kis_token_bundle["app_key"]
    app_secret = kis_token_bundle["app_secret"]
    token_type = kis_token_bundle["token_type"]

    assert access_token  # masked in logs by the redaction filter
    assert token_type.lower() in ("bearer", "bearer ")

    async with httpx.AsyncClient(base_url=KIS_BASE_URL, timeout=30.0) as inner:
        broker = _make_broker(inner)
        quote = await get_quote(
            broker,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            symbol="AAPL",
            market="NAS",
        )

    assert quote.symbol == "AAPL"
    assert quote.last_price_usd > Decimal("0")
    # Last price is non-secret market data, so printing it is fine.
    print(f"\nLive AAPL quote: ${quote.last_price_usd}")


@pytest.mark.asyncio
async def test_live_kis_purchasable_cash(kis_token_bundle: dict) -> None:
    """회귀 방어: 외화예수금 조회가 정상 응답하는지 검증.

    지난 세션 회귀: get_balance가 inquire-balance의 output2에서 존재하지
    않는 필드(frcr_dncl_amt_2)를 읽어 항상 0을 반환. 이번 PR에서는 별도
    inquire-psamount endpoint를 사용한다.

    잔고가 정말로 0인 빈 계좌도 valid이므로 어설션은 ">=0 + Decimal 형식"만.
    실제 잔고 값은 stdout에 출력되어 운영자가 사후 확인 가능.
    """
    access_token = kis_token_bundle["access_token"]
    app_key = kis_token_bundle["app_key"]
    app_secret = kis_token_bundle["app_secret"]
    account_no = _required_env("KIS_ACCOUNT_NO")

    async with httpx.AsyncClient(base_url=KIS_BASE_URL, timeout=30.0) as inner:
        broker = _make_broker(inner)
        cash = await get_purchasable_cash_usd(
            broker,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account_no,
        )

    assert isinstance(cash, Decimal)
    assert cash >= Decimal("0")
    print(f"\nLive KIS USD purchasable cash: ${cash}")


@pytest.mark.asyncio
async def test_live_kis_positions(kis_token_bundle: dict) -> None:
    """회귀 방어: 보유 종목 조회가 정상 응답하는지 검증.

    지난 세션 회귀: cli.py:_fetch_kis_account_state가 holdings를 stub
    빈 리스트로 반환. 이번 PR에서는 실제 get_positions를 호출한다.
    빈 포지션이어도 endpoint 호출 자체는 성공해야 한다.
    """
    access_token = kis_token_bundle["access_token"]
    app_key = kis_token_bundle["app_key"]
    app_secret = kis_token_bundle["app_secret"]
    account_no = _required_env("KIS_ACCOUNT_NO")

    async with httpx.AsyncClient(base_url=KIS_BASE_URL, timeout=30.0) as inner:
        broker = _make_broker(inner)
        positions = await get_positions(
            broker,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account_no,
        )

    assert isinstance(positions, tuple)
    for p in positions:
        assert p.symbol
        assert p.qty > 0
        assert p.avg_cost_usd > Decimal("0")
    print(f"\nLive KIS positions: {len(positions)}개 보유")
    for p in positions:
        print(f"  - {p.symbol}: {p.qty}주 (평단 ${p.avg_cost_usd})")


@pytest.mark.asyncio
async def test_live_kis_combined_balance(kis_token_bundle: dict) -> None:
    """회귀 방어: get_balance가 cash + 평가금액 합산으로 정상 동작하는지.

    end-to-end 검증: design 명령이 호출하는 잔고 조회와 동일한 경로.
    total_value_usd가 cash_usd 보다 크거나 같아야 함 (보유 종목 평가금액
    은 음수 아님).
    """
    access_token = kis_token_bundle["access_token"]
    app_key = kis_token_bundle["app_key"]
    app_secret = kis_token_bundle["app_secret"]
    account_no = _required_env("KIS_ACCOUNT_NO")

    async with httpx.AsyncClient(base_url=KIS_BASE_URL, timeout=30.0) as inner:
        broker = _make_broker(inner)
        balance = await get_balance(
            broker,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account_no,
        )

    assert balance.account == account_no
    assert balance.cash_usd >= Decimal("0")
    assert balance.total_value_usd >= balance.cash_usd, (
        f"total_value({balance.total_value_usd}) < cash({balance.cash_usd}) — "
        "보유 종목 평가금액이 음수가 됐다는 뜻이므로 회귀."
    )
    print(
        f"\nLive KIS balance: cash=${balance.cash_usd}, "
        f"total=${balance.total_value_usd}"
    )
