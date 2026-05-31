"""스펙 031 슬라이스 1 — KIS 실시간 웹소켓 프로토콜·feed·폴백 테스트.

가짜 전송(fake transport)으로 연결·구독·파싱·폴백을 검증한다 — 제3자 웹소켓
라이브러리·라이브 연결 없이(SC-031-01 ~ 06).
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import httpx
import pytest
import respx

from auto_invest.broker.realtime import (
    OVERSEAS_TRADE_TR_ID,
    Subscription,
    WebsocketRealtimeFeed,
    build_subscribe_frame,
    parse_realtime_frame,
    quote_from_frame,
    request_approval_key,
)

BASE = "https://api.example"

# 해외 실시간체결가 payload — 기본 field_map(symbol=1, last=11, bid=15, ask=16)에 맞춘 17필드.
_QUOTE_PAYLOAD = (
    "RSYM^AAPL^2^d^d^d^d^d^150.0^151.0^149.0^150.25^2^0.1^0.1^150.20^150.30"
)
_QUOTE_FRAME = f"0|{OVERSEAS_TRADE_TR_ID}|001|{_QUOTE_PAYLOAD}"
_PINGPONG = json.dumps({"header": {"tr_id": "PINGPONG", "datetime": "..."}})


# ------------------------------------------------------ SC-031-01 approval key


@pytest.mark.asyncio
async def test_request_approval_key():
    async with httpx.AsyncClient() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/oauth2/Approval").mock(
                return_value=httpx.Response(200, json={"approval_key": "AK-123"})
            )
            key = await request_approval_key(
                client, base_url=BASE, app_key="a", app_secret="s"
            )
        assert key == "AK-123"


# ------------------------------------------------------ SC-031-02 subscribe frame


def test_build_subscribe_frame():
    raw = build_subscribe_frame("AK", tr_id="HDFSCNT0", tr_key="DNASAAPL")
    obj = json.loads(raw)
    assert obj["header"]["approval_key"] == "AK"
    assert obj["header"]["tr_type"] == "1"
    assert obj["body"]["input"]["tr_id"] == "HDFSCNT0"
    assert obj["body"]["input"]["tr_key"] == "DNASAAPL"


def test_build_unsubscribe_frame():
    obj = json.loads(build_subscribe_frame("AK", tr_id="X", tr_key="Y", subscribe=False))
    assert obj["header"]["tr_type"] == "2"


# ------------------------------------------------------ SC-031-03 parse frame


def test_parse_data_frame():
    fr = parse_realtime_frame(_QUOTE_FRAME)
    assert fr is not None
    assert fr.tr_id == OVERSEAS_TRADE_TR_ID
    assert fr.fields[1] == "AAPL"
    assert fr.is_pingpong is False
    assert fr.is_control is False


def test_parse_pingpong():
    fr = parse_realtime_frame(_PINGPONG)
    assert fr is not None
    assert fr.is_pingpong is True
    assert fr.is_control is True


def test_parse_control_subscribe_ack():
    fr = parse_realtime_frame(json.dumps({"header": {"tr_id": "HDFSCNT0"}, "body": {"rt_cd": "0"}}))
    assert fr is not None
    assert fr.is_control is True
    assert fr.is_pingpong is False


def test_parse_garbage_and_empty():
    assert parse_realtime_frame("") is None
    assert parse_realtime_frame(None) is None
    assert parse_realtime_frame("0|TR") is None  # 필드 부족.
    assert parse_realtime_frame("{not json") is None


# ------------------------------------------------------ SC-031-04 quote_from_frame


def test_quote_from_frame():
    fr = parse_realtime_frame(_QUOTE_FRAME)
    q = quote_from_frame(fr)
    assert q is not None
    assert q.symbol == "AAPL"
    assert q.last_price_usd == Decimal("150.25")
    assert q.bid_usd == Decimal("150.20")
    assert q.ask_usd == Decimal("150.30")


def test_quote_from_frame_short_or_nonpositive():
    # last 자리가 음수/0 → 현재가 없음 → None.
    bad = "0|HDFSCNT0|001|RSYM^AAPL^2^d^d^d^d^d^o^h^l^0^s^d^r^b^a"
    assert quote_from_frame(parse_realtime_frame(bad)) is None
    # 필드 부족(종목만) → None.
    assert quote_from_frame(parse_realtime_frame("0|HDFSCNT0|001|RSYM")) is None


# ------------------------------------------------------ fake transport


class FakeTransport:
    """주입형 가짜 전송. 미리 정한 프레임을 recv 로 돌려주고, 소진되면 drained 를 세우고
    block 을 기다린다(run 루프가 available 인 채 살아있게)."""

    def __init__(self, frames: list[str]) -> None:
        self.sent: list[str] = []
        self._frames = list(frames)
        self.drained = asyncio.Event()
        self._block = asyncio.Event()
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        if self._frames:
            return self._frames.pop(0)
        self.drained.set()
        await self._block.wait()
        return ""  # stop() 후 빈 프레임 → 루프가 _stopped 보고 정상 종료.

    async def close(self) -> None:
        self.closed = True
        self._block.set()


def _feed(transport: FakeTransport) -> WebsocketRealtimeFeed:
    async def factory():
        return transport

    return WebsocketRealtimeFeed(
        transport_factory=factory,
        approval_key="AK",
        subscriptions=[Subscription(tr_id=OVERSEAS_TRADE_TR_ID, tr_key="DNASAAPL")],
    )


# ------------------------------------------------------ SC-031-05 feed run


@pytest.mark.asyncio
async def test_feed_subscribes_and_caches_quote():
    transport = FakeTransport([_QUOTE_FRAME])
    feed = _feed(transport)
    task = asyncio.create_task(feed.run())
    await asyncio.wait_for(transport.drained.wait(), timeout=1.0)

    # 구독 프레임이 전송됐다.
    assert len(transport.sent) == 1
    assert json.loads(transport.sent[0])["body"]["input"]["tr_key"] == "DNASAAPL"
    # available + 캐시된 시세.
    assert feed.available is True
    q = feed.latest_quote("AAPL")
    assert q is not None and q.last_price_usd == Decimal("150.25")
    # 미구독 종목은 None.
    assert feed.latest_quote("MSFT") is None

    await feed.stop()
    await asyncio.wait_for(task, timeout=1.0)
    assert feed.available is False


@pytest.mark.asyncio
async def test_feed_echoes_pingpong():
    transport = FakeTransport([_PINGPONG, _QUOTE_FRAME])
    feed = _feed(transport)
    task = asyncio.create_task(feed.run())
    await asyncio.wait_for(transport.drained.wait(), timeout=1.0)
    # 구독 1 + PINGPONG 에코 1 = sent 에 PINGPONG 이 들어있다.
    assert _PINGPONG in transport.sent
    await feed.stop()
    await asyncio.wait_for(task, timeout=1.0)


# ------------------------------------------------------ SC-031-06 fallback


@pytest.mark.asyncio
async def test_feed_unavailable_on_recv_error():
    class FailingTransport:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send(self, message: str) -> None:
            self.sent.append(message)

        async def recv(self) -> str:
            raise ConnectionError("stream dropped")

        async def close(self) -> None:
            pass

    transport = FailingTransport()

    async def factory():
        return transport

    feed = WebsocketRealtimeFeed(
        transport_factory=factory,
        approval_key="AK",
        subscriptions=[Subscription(tr_id="X", tr_key="Y")],
    )
    await feed.run()  # recv 즉시 예외 → 격리 → 종료.
    assert feed.available is False
    assert feed.latest_quote("AAPL") is None


@pytest.mark.asyncio
async def test_feed_unavailable_on_connect_error():
    async def failing_factory():
        raise OSError("connect refused")

    feed = WebsocketRealtimeFeed(
        transport_factory=failing_factory,
        approval_key="AK",
        subscriptions=[Subscription(tr_id="X", tr_key="Y")],
    )
    await feed.run()
    assert feed.available is False
