"""KIS 실시간 웹소켓 시세 수신 (스펙 031, 체결 정교화 P3) — 슬라이스 1.

REST 폴링(get_quote)의 지연을 없애기 위해 KIS 실시간 웹소켓으로 시세를 받는다. 이
슬라이스는 **전송(transport) 주입형**으로 설계해 제3자 웹소켓 라이브러리 의존 없이
프로토콜·폴백·워커 연동을 전부 테스트한다. 실제 웹소켓 전송 어댑터(websockets 등)는
후속 슬라이스에서 주입한다(공급망 결정 — 운영자 확인 후).

안전(헌법):
  - **수신 전용** — 주문 경로를 한 바이트도 안 바꾼다(시세 사실만 받음).
  - **폴백 보장(외부 API 강건성)** — 연결·구독·수신 중 어떤 예외도 격리되어 feed 를
    `available=False` 로 내려 워커가 기존 REST 폴링으로 자동 폴백한다(거래 무중단).
  - **시크릿 격리** — approval_key 는 받는 즉시 register_secret 로 로그에서 가린다.
  - **기본 끔** — 워커는 realtime_feed 가 주입됐을 때만 사용(byte 동일이 기본).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

import httpx

from auto_invest.broker.models import Quote
from auto_invest.logging_config import register_secret

logger = logging.getLogger(__name__)


# --------------------------------------------------------------- approval key


async def request_approval_key(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    app_key: str,
    app_secret: str,
) -> str:
    """KIS `/oauth2/Approval` 로 실시간 웹소켓 approval-key 를 발급받는다(FR-031-01).

    REST 토큰(`issue_token`)과 별개의 웹소켓 전용 키다. 받는 즉시 register_secret 로
    로그에서 가린다(시크릿 격리)."""
    response = await client.post(
        f"{base_url}/oauth2/Approval",
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": app_secret,
        },
        headers={"content-type": "application/json"},
    )
    response.raise_for_status()
    key = str(response.json()["approval_key"])
    register_secret(key)
    return key


# --------------------------------------------------------------- subscribe frame


def build_subscribe_frame(
    approval_key: str,
    *,
    tr_id: str,
    tr_key: str,
    subscribe: bool = True,
) -> str:
    """KIS 실시간 구독/해지 JSON 프레임을 만든다(FR-031-02).

    `tr_type` "1"=구독, "2"=해지. `tr_id` 는 실시간 항목(예: 해외체결가 HDFSCNT0),
    `tr_key` 는 구독 대상(예: 거래소+종목 "DNASAAPL")."""
    return json.dumps(
        {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1" if subscribe else "2",
                "content-type": "utf-8",
            },
            "body": {"input": {"tr_id": tr_id, "tr_key": tr_key}},
        }
    )


# --------------------------------------------------------------- frame parsing


@dataclass(frozen=True)
class RealtimeFrame:
    """파싱된 실시간 프레임 한 건. 데이터 프레임은 `fields`(^ 구분 payload)를 담고,
    제어 프레임(PINGPONG/구독응답)은 `fields=[]` + 플래그."""

    tr_id: str
    fields: list[str]
    is_pingpong: bool = False
    is_control: bool = False


@dataclass(frozen=True)
class RealtimeFieldMap:
    """해외 실시간체결가 프레임의 필드 인덱스 맵. **KIS 명세(HDFSCNT0)에 맞춰 검증 후
    라이브 활성화할 것** — 잘못된 인덱스는 잘못된 시세를 주문 경로에 줄 수 있다(기본 끔이라
    슬라이스 2 에서 실제 전송 붙일 때 검증). 기본값은 KIS 해외주식 실시간체결가 표준 순서."""

    symbol_idx: int = 1  # SYMB 종목코드
    last_idx: int = 11  # LAST 현재가(체결가)
    bid_idx: int = 15  # PBID 매수호가
    ask_idx: int = 16  # PASK 매도호가


OVERSEAS_TRADE_TR_ID = "HDFSCNT0"
OVERSEAS_TRADE_FIELDS = RealtimeFieldMap()


def parse_realtime_frame(raw: str | bytes | None) -> RealtimeFrame | None:
    """실시간 프레임 파서(순수, FR-031-03).

    - JSON 제어 프레임(`{...}`): PINGPONG·구독응답. `is_control=True`,
      PINGPONG 이면 `is_pingpong=True`.
    - 파이프 데이터 프레임(`0|TR_ID|cnt|f1^f2^...`): `tr_id` + `^` 구분 fields.
    - 형식 불량/빈 입력 → None.
    """
    if raw is None:
        return None
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    text = text.strip()
    if not text:
        return None

    if text[0] == "{":
        try:
            obj = json.loads(text)
        except (ValueError, TypeError):
            return None
        tr_id = str(obj.get("header", {}).get("tr_id", ""))
        return RealtimeFrame(
            tr_id=tr_id,
            fields=[],
            is_pingpong=(tr_id == "PINGPONG"),
            is_control=True,
        )

    parts = text.split("|")
    if len(parts) < 4:
        return None
    tr_id = parts[1]
    fields = parts[3].split("^")
    return RealtimeFrame(tr_id=tr_id, fields=fields)


def _decimal_or_none(values: list[str], idx: int) -> Decimal | None:
    if idx < 0 or idx >= len(values):
        return None
    try:
        d = Decimal(values[idx])
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d > 0 else None


def quote_from_frame(
    frame: RealtimeFrame,
    *,
    field_map: RealtimeFieldMap = OVERSEAS_TRADE_FIELDS,
) -> Quote | None:
    """해외 실시간체결가 프레임에서 Quote 를 만든다(FR-031-04). 종목/현재가가 없거나
    비양수면 None(매수/매도호가는 선택)."""
    f = frame.fields
    if field_map.symbol_idx >= len(f):
        return None
    symbol = f[field_map.symbol_idx].strip()
    last = _decimal_or_none(f, field_map.last_idx)
    if not symbol or last is None:
        return None
    return Quote(
        symbol=symbol,
        last_price_usd=last,
        bid_usd=_decimal_or_none(f, field_map.bid_idx),
        ask_usd=_decimal_or_none(f, field_map.ask_idx),
        quoted_at_utc=datetime.now(UTC),
    )


# --------------------------------------------------------------- transport + feed


class RealtimeTransport(Protocol):
    """주입 가능한 웹소켓 전송. 실제 어댑터(websockets 등)는 슬라이스 2 에서 제공하고,
    테스트는 가짜 전송을 넣는다 — 의존성·라이브 연결 없이 프로토콜을 검증한다."""

    async def send(self, message: str) -> None: ...

    async def recv(self) -> str: ...

    async def close(self) -> None: ...


class RealtimeQuoteSource(Protocol):
    """워커가 보는 최소 인터페이스. 이것만 의존해 realtime 구현과 결합을 끊는다."""

    @property
    def available(self) -> bool: ...

    def latest_quote(self, symbol: str) -> Quote | None: ...


# transport_factory: () -> awaitable[RealtimeTransport]. 슬라이스 2 에서 실제 어댑터를,
# 테스트는 가짜 전송을 돌려준다.
TransportFactory = Callable[[], Awaitable[RealtimeTransport]]


@dataclass(frozen=True)
class Subscription:
    """구독 한 건: 실시간 항목(tr_id)과 대상(tr_key, 예: 'DNASAAPL')."""

    tr_id: str
    tr_key: str


class WebsocketRealtimeFeed:
    """전송 주입형 실시간 시세 feed(FR-031-05).

    `run()` 이 전송을 열고 구독 프레임을 보낸 뒤 수신 루프에서 시세 캐시를 갱신한다.
    어떤 단계든 예외가 나면 `available` 을 False 로 내리고 조용히 끝낸다 — 워커는 그
    신호를 보고 REST 폴링으로 폴백한다(거래 무중단). PINGPONG 은 그대로 에코한다."""

    def __init__(
        self,
        *,
        transport_factory: TransportFactory,
        approval_key: str,
        subscriptions: list[Subscription],
        field_map: RealtimeFieldMap = OVERSEAS_TRADE_FIELDS,
    ) -> None:
        self._transport_factory = transport_factory
        self._approval_key = approval_key
        self._subscriptions = subscriptions
        self._field_map = field_map
        self._quotes: dict[str, Quote] = {}
        self._available = False
        self._stopped = False
        self._transport: RealtimeTransport | None = None

    @property
    def available(self) -> bool:
        return self._available

    def latest_quote(self, symbol: str) -> Quote | None:
        """캐시된 최신 실시간 시세. 없거나 unavailable 이면 None(워커가 REST 폴백)."""
        if not self._available:
            return None
        return self._quotes.get(symbol)

    async def stop(self) -> None:
        self._stopped = True
        self._available = False
        if self._transport is not None:
            try:
                await self._transport.close()
            except Exception:  # noqa: BLE001 — 종료 best-effort.
                logger.warning("realtime: transport close failed", exc_info=True)

    async def run(self) -> None:
        """연결 → 구독 → 수신 루프. 모든 예외 격리(폴백 신호로 available=False)."""
        try:
            self._transport = await self._transport_factory()
        except Exception:  # noqa: BLE001 — 연결 실패는 폴백(거래 무중단).
            logger.warning("realtime: connect failed — REST 폴백 유지", exc_info=True)
            self._available = False
            return

        try:
            for sub in self._subscriptions:
                await self._transport.send(
                    build_subscribe_frame(
                        self._approval_key, tr_id=sub.tr_id, tr_key=sub.tr_key
                    )
                )
            self._available = True
            while not self._stopped:
                raw = await self._transport.recv()
                await self._handle_frame(raw)
        except Exception:  # noqa: BLE001 — 구독/수신 실패는 폴백(거래 무중단).
            logger.warning("realtime: stream error — REST 폴백 전환", exc_info=True)
        finally:
            self._available = False

    async def _handle_frame(self, raw: str) -> None:
        frame = parse_realtime_frame(raw)
        if frame is None:
            return
        if frame.is_pingpong:
            if self._transport is not None:
                await self._transport.send(raw)  # 그대로 에코(연결 유지).
            return
        if frame.is_control:
            return
        quote = quote_from_frame(frame, field_map=self._field_map)
        if quote is not None:
            self._quotes[quote.symbol] = quote
