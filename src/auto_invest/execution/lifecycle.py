"""Order lifetime management (spec 030) — 미체결 주문 수명 관리.

세 가지 옵트인 정교화(`TradingRule.lifecycle` 가 None 이면 전부 비활성, byte 동일):

  1. **marketable-limit** — 제출 시 시장가에 가까운 공격적 지정가(매수 = ask 약간 위,
     매도 = bid 약간 아래)를 써서 빠른 체결과 슬리피지 상한을 동시에 얻는다.
  2. **TTL 취소**         — 미체결이 `ttl_seconds` 를 초과하면 취소한다.
  3. **취소-재호가**      — 지정가가 현재 중간가에서 `requote_drift_pct` 이상 벌어지면
                            취소하고 게이트 체인을 다시 통과시켜 신선한 가격으로 재제출한다.

설계는 스펙 015(fill_sync) 패턴을 따른다:
  - **순수 함수**(`marketable_limit_price`·`is_ttl_expired`·`price_drift_pct`·
    `should_requote`·`plan_order_lifecycle`)는 브로커/DB 미접근이라 결정론적으로
    테스트 가능. 부수효과(취소·재제출·감사)는 워커(`worker/loop.py`)가 수행한다.
  - **DB 리더**(`load_open_orders_for_lifecycle`)만 sqlite 를 읽고, 그 외 로직은 순수.

안전: 재호가도 K1 캡 게이트 체인을 다시 통과한다(노출 상한 무변경). 취소는 브로커
확인이 성공한 뒤에만 로컬 상태를 바꾼다 — 실패(이미 체결/종료)는 스펙 015 체결
동기화가 정합화한다.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Literal

from auto_invest.config.enums import Side
from auto_invest.config.rules import OrderLifecycleConfig

_CENT = Decimal("0.01")
_BPS = Decimal("10000")
_HUNDRED = Decimal("100")

_OPEN_STATES = ("SUBMITTED", "PARTIALLY_FILLED")


# --------------------------------------------------------------- 순수 가격 로직


def marketable_limit_price(
    side: Side,
    *,
    bid: Decimal | None,
    ask: Decimal | None,
    buffer_bps: int,
) -> Decimal | None:
    """시장가에 가까운 공격적 지정가(marketable limit). 스프레드를 건너 즉시 체결을
    노리되 슬리피지를 `buffer_bps`(basis point) 로 캡한다.

    - 매수: `ask × (1 + bps/10000)` 를 cent 단위 **올림** — ask 보다 같거나 위라 즉시
      체결 가능하면서, ask 가 살짝 올라도 버퍼만큼 따라간다.
    - 매도: `bid × (1 − bps/10000)` 를 cent 단위 **내림** — bid 보다 같거나 아래.

    필요한 호가(매수=ask, 매도=bid)가 없거나 비양수면 `None` 을 돌려준다 — 호출자는
    기존 limit_price 표현식으로 폴백한다. buffer_bps 가 음수면(방어) `None`.
    """
    if buffer_bps < 0:
        return None
    frac = Decimal(buffer_bps) / _BPS
    if side is Side.BUY:
        if ask is None or ask <= 0:
            return None
        return (ask * (Decimal(1) + frac)).quantize(_CENT, rounding=ROUND_UP)
    if bid is None or bid <= 0:
        return None
    return (bid * (Decimal(1) - frac)).quantize(_CENT, rounding=ROUND_DOWN)


def mid_price(
    *,
    bid: Decimal | None,
    ask: Decimal | None,
    last: Decimal | None,
) -> Decimal | None:
    """중간가. bid·ask 둘 다 양수면 `(bid+ask)/2`, 아니면 last 폴백, 둘 다 없으면 None."""
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        return (bid + ask) / Decimal(2)
    if last is not None and last > 0:
        return last
    return None


# --------------------------------------------------------------- 순수 판정 로직


def _parse_iso(ts: str | None) -> datetime | None:
    """ISO8601 ms-precision('...Z') → tz-aware datetime. 파싱 실패는 None."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def is_ttl_expired(
    submitted_at: datetime | None,
    now: datetime,
    ttl_seconds: int | None,
) -> bool:
    """미체결이 TTL 을 초과했는지. ttl 미설정이거나 제출시각 미상이면 False."""
    if ttl_seconds is None or submitted_at is None:
        return False
    return (now - submitted_at).total_seconds() >= ttl_seconds


def price_drift_pct(limit_price: Decimal | None, mid: Decimal | None) -> Decimal | None:
    """`|mid − limit| / limit × 100`(%). limit 이 0/None 이거나 mid 가 None 이면 None."""
    if limit_price is None or limit_price <= 0 or mid is None or mid <= 0:
        return None
    return (abs(mid - limit_price) / limit_price) * _HUNDRED


def should_requote(
    *,
    limit_price: Decimal | None,
    mid: Decimal | None,
    drift_pct_threshold: Decimal | None,
    submitted_at: datetime | None,
    now: datetime,
    requote_after_seconds: int,
) -> bool:
    """지정가를 재호가해야 하는지. 드리프트 임계 미설정이면 False. 재호가 폭주 방지를
    위해 `requote_after_seconds` 경과 전에는 재호가하지 않는다."""
    if drift_pct_threshold is None:
        return False
    if submitted_at is None:
        return False
    if (now - submitted_at).total_seconds() < requote_after_seconds:
        return False
    drift = price_drift_pct(limit_price, mid)
    return drift is not None and drift >= drift_pct_threshold


# --------------------------------------------------------------- 데이터 모델


@dataclass(frozen=True)
class OpenLifecycleOrder:
    """수명 관리 대상인 로컬 열린 주문 한 건(스펙 015 OpenOrder 의 가격·시각 확장)."""

    correlation_id: str
    kis_order_id: str
    symbol: str
    side: str  # "BUY" | "SELL"
    rule_id: str
    order_type: str  # "LIMIT" | "MARKET"
    limit_price_usd: Decimal | None
    submitted_at: datetime | None
    state: str


@dataclass(frozen=True)
class QuoteSnapshot:
    """수명 관리용 종목별 신선 호가(워커가 get_quote 로 채운다)."""

    bid_usd: Decimal | None
    ask_usd: Decimal | None
    last_usd: Decimal | None


@dataclass(frozen=True)
class LifecycleAction:
    """한 주문에 대한 수명 관리 결정 한 건."""

    kind: Literal["cancel_ttl", "requote"]
    order: OpenLifecycleOrder
    age_seconds: int
    ttl_seconds: int | None = None
    drift_pct: Decimal | None = None
    mid_usd: Decimal | None = None


# --------------------------------------------------------------- 순수 계획


def plan_order_lifecycle(
    orders: list[OpenLifecycleOrder],
    *,
    configs: Mapping[str, OrderLifecycleConfig],
    quotes: Mapping[str, QuoteSnapshot],
    now: datetime,
) -> list[LifecycleAction]:
    """각 열린 주문에 대해 취소/재호가를 결정한다(순수 — 부수효과 없음, FR-030-05).

    - `configs`: rule_id → 해당 룰의 lifecycle 설정. 없는 룰의 주문은 건너뛴다(옵트인).
    - `quotes`: symbol → 신선 호가. 없으면 재호가는 못 하지만 TTL 취소는 가능(호가 불필요).
    - TTL 만료가 재호가보다 **우선**한다(늙은 주문 정리가 먼저).
    """
    actions: list[LifecycleAction] = []
    for o in orders:
        cfg = configs.get(o.rule_id)
        if cfg is None:
            continue  # 옵트인 — lifecycle 미설정 룰은 수명 관리 안 함.
        age = (
            int((now - o.submitted_at).total_seconds())
            if o.submitted_at is not None
            else 0
        )
        # G1 — TTL 만료 취소(우선).
        if is_ttl_expired(o.submitted_at, now, cfg.ttl_seconds):
            actions.append(
                LifecycleAction(
                    kind="cancel_ttl",
                    order=o,
                    age_seconds=age,
                    ttl_seconds=cfg.ttl_seconds,
                )
            )
            continue
        # G2 — 드리프트 재호가(미체결 지정가 주문만). 부분 체결분은 잔량 재계산이 필요해
        # 재호가에서 제외하고 TTL 취소에 맡긴다(보수적 — 재제출이 잔량을 넘기지 않도록).
        if o.order_type != "LIMIT" or o.state != "SUBMITTED":
            continue
        quote = quotes.get(o.symbol)
        mid = (
            mid_price(bid=quote.bid_usd, ask=quote.ask_usd, last=quote.last_usd)
            if quote is not None
            else None
        )
        if should_requote(
            limit_price=o.limit_price_usd,
            mid=mid,
            drift_pct_threshold=cfg.requote_drift_pct,
            submitted_at=o.submitted_at,
            now=now,
            requote_after_seconds=cfg.requote_after_seconds,
        ):
            actions.append(
                LifecycleAction(
                    kind="requote",
                    order=o,
                    age_seconds=age,
                    drift_pct=price_drift_pct(o.limit_price_usd, mid),
                    mid_usd=mid,
                )
            )
    return actions


# --------------------------------------------------------------- DB 리더


def load_open_orders_for_lifecycle(
    conn: sqlite3.Connection,
) -> list[OpenLifecycleOrder]:
    """열린 주문(SUBMITTED/PARTIALLY_FILLED, kis_order_id 있음)을 가격·제출시각 포함해
    읽는다(FR-030-04). 스펙 015 `_load_open_orders` 보다 풍부한 컬럼셋."""
    placeholders = ",".join("?" for _ in _OPEN_STATES)
    rows = conn.execute(
        f"""
        SELECT correlation_id, kis_order_id, symbol, side, rule_id, order_type,
               limit_price_usd, submitted_at_utc, state
        FROM orders
        WHERE state IN ({placeholders}) AND kis_order_id IS NOT NULL
        """,
        _OPEN_STATES,
    ).fetchall()
    return [
        OpenLifecycleOrder(
            correlation_id=r["correlation_id"],
            kis_order_id=r["kis_order_id"],
            symbol=r["symbol"],
            side=r["side"],
            rule_id=r["rule_id"],
            order_type=r["order_type"],
            limit_price_usd=(
                Decimal(r["limit_price_usd"])
                if r["limit_price_usd"] is not None
                else None
            ),
            submitted_at=_parse_iso(r["submitted_at_utc"]),
            state=r["state"],
        )
        for r in rows
    ]
