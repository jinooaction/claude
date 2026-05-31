"""스펙 030 — 미체결 주문 수명 관리 순수 로직 단위 테스트.

브로커/DB 미접근. marketable-limit 가격·TTL 만료·드리프트·계획을 결정론적으로 검증한다
(SC-030-01 ~ 05, 08).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from auto_invest.config.enums import Side
from auto_invest.config.rules import OrderLifecycleConfig
from auto_invest.execution.lifecycle import (
    OpenLifecycleOrder,
    QuoteSnapshot,
    is_ttl_expired,
    marketable_limit_price,
    mid_price,
    plan_order_lifecycle,
    price_drift_pct,
    should_requote,
)

NOW = datetime(2026, 5, 31, 15, 0, tzinfo=UTC)


def _q(bid: str, ask: str, last: str) -> QuoteSnapshot:
    return QuoteSnapshot(
        bid_usd=Decimal(bid), ask_usd=Decimal(ask), last_usd=Decimal(last)
    )


def _order(
    *,
    corr: str = "ord-1",
    kis: str = "K1",
    symbol: str = "AAPL",
    side: str = "BUY",
    rule_id: str = "r1",
    order_type: str = "LIMIT",
    limit: str | None = "100.00",
    age_seconds: int = 90,
    state: str = "SUBMITTED",
) -> OpenLifecycleOrder:
    return OpenLifecycleOrder(
        correlation_id=corr,
        kis_order_id=kis,
        symbol=symbol,
        side=side,
        rule_id=rule_id,
        order_type=order_type,
        limit_price_usd=Decimal(limit) if limit is not None else None,
        submitted_at=NOW - timedelta(seconds=age_seconds),
        state=state,
    )


# ------------------------------------------------------ SC-030-01 marketable limit


def test_marketable_limit_buy_rounds_up():
    # ask 100 + 20bps = 100.20 (올림).
    assert marketable_limit_price(
        Side.BUY, bid=Decimal("99.90"), ask=Decimal("100"), buffer_bps=20
    ) == Decimal("100.20")


def test_marketable_limit_sell_rounds_down():
    # bid 100 - 20bps = 99.80 (내림).
    assert marketable_limit_price(
        Side.SELL, bid=Decimal("100"), ask=Decimal("100.10"), buffer_bps=20
    ) == Decimal("99.80")


def test_marketable_limit_zero_bps_is_touch():
    assert marketable_limit_price(
        Side.BUY, bid=None, ask=Decimal("100"), buffer_bps=0
    ) == Decimal("100.00")
    assert marketable_limit_price(
        Side.SELL, bid=Decimal("100"), ask=None, buffer_bps=0
    ) == Decimal("100.00")


def test_marketable_limit_missing_quote_returns_none():
    # 매수인데 ask 없음, 매도인데 bid 없음 → None (호출자가 표현식 폴백).
    assert marketable_limit_price(Side.BUY, bid=Decimal("99"), ask=None, buffer_bps=20) is None
    assert marketable_limit_price(Side.SELL, bid=None, ask=Decimal("99"), buffer_bps=20) is None
    assert marketable_limit_price(Side.BUY, bid=None, ask=Decimal("0"), buffer_bps=20) is None


def test_marketable_limit_negative_bps_returns_none():
    assert marketable_limit_price(
        Side.BUY, bid=None, ask=Decimal("100"), buffer_bps=-1
    ) is None


# ------------------------------------------------------ mid price


def test_mid_price_from_bid_ask():
    assert mid_price(bid=Decimal("99"), ask=Decimal("101"), last=Decimal("105")) == Decimal("100")


def test_mid_price_falls_back_to_last():
    assert mid_price(bid=None, ask=None, last=Decimal("100")) == Decimal("100")
    assert mid_price(bid=Decimal("0"), ask=Decimal("0"), last=Decimal("100")) == Decimal("100")


def test_mid_price_none_when_no_data():
    assert mid_price(bid=None, ask=None, last=None) is None


# ------------------------------------------------------ SC-030-02 TTL


def test_ttl_expired_true_past_ttl():
    submitted = NOW - timedelta(seconds=120)
    assert is_ttl_expired(submitted, NOW, 60) is True


def test_ttl_not_expired_within_ttl():
    submitted = NOW - timedelta(seconds=30)
    assert is_ttl_expired(submitted, NOW, 60) is False


def test_ttl_none_or_missing_submitted_never_expires():
    assert is_ttl_expired(NOW - timedelta(seconds=999), NOW, None) is False
    assert is_ttl_expired(None, NOW, 60) is False


# ------------------------------------------------------ drift + SC-030-03 requote


def test_price_drift_pct():
    assert price_drift_pct(Decimal("100"), Decimal("103")) == Decimal("3")
    assert price_drift_pct(Decimal("100"), Decimal("99")) == Decimal("1")


def test_price_drift_pct_guards():
    assert price_drift_pct(None, Decimal("100")) is None
    assert price_drift_pct(Decimal("0"), Decimal("100")) is None
    assert price_drift_pct(Decimal("100"), None) is None


def test_should_requote_when_drift_exceeds_threshold():
    submitted = NOW - timedelta(seconds=60)
    assert should_requote(
        limit_price=Decimal("100"),
        mid=Decimal("103"),
        drift_pct_threshold=Decimal("2"),
        submitted_at=submitted,
        now=NOW,
        requote_after_seconds=30,
    ) is True


def test_should_not_requote_below_threshold():
    submitted = NOW - timedelta(seconds=60)
    assert should_requote(
        limit_price=Decimal("100"),
        mid=Decimal("101"),  # drift 1% < 2%
        drift_pct_threshold=Decimal("2"),
        submitted_at=submitted,
        now=NOW,
        requote_after_seconds=30,
    ) is False


def test_should_not_requote_before_min_age():
    submitted = NOW - timedelta(seconds=10)  # 10s < 30s
    assert should_requote(
        limit_price=Decimal("100"),
        mid=Decimal("103"),
        drift_pct_threshold=Decimal("2"),
        submitted_at=submitted,
        now=NOW,
        requote_after_seconds=30,
    ) is False


def test_should_not_requote_when_threshold_none():
    submitted = NOW - timedelta(seconds=60)
    assert should_requote(
        limit_price=Decimal("100"),
        mid=Decimal("200"),
        drift_pct_threshold=None,
        submitted_at=submitted,
        now=NOW,
        requote_after_seconds=30,
    ) is False


# ------------------------------------------------------ plan_order_lifecycle


def _cfg(**kw) -> OrderLifecycleConfig:
    return OrderLifecycleConfig(**kw)


def test_plan_ttl_cancel():
    """SC-030-02 — TTL 만료 주문은 cancel_ttl 액션."""
    o = _order(age_seconds=120)
    actions = plan_order_lifecycle(
        [o], configs={"r1": _cfg(ttl_seconds=60)}, quotes={}, now=NOW
    )
    assert len(actions) == 1
    assert actions[0].kind == "cancel_ttl"
    assert actions[0].ttl_seconds == 60
    assert actions[0].age_seconds == 120


def test_plan_requote_on_drift():
    """SC-030-03 — 드리프트 초과 지정가는 requote 액션(drift_pct·mid 기록)."""
    o = _order(age_seconds=60, limit="100.00")
    quotes = {"AAPL": _q("102.9", "103.1", "103")}
    actions = plan_order_lifecycle(
        [o], configs={"r1": _cfg(requote_drift_pct=Decimal("2"), requote_after_seconds=30)},
        quotes=quotes, now=NOW,
    )
    assert len(actions) == 1
    assert actions[0].kind == "requote"
    assert actions[0].mid_usd == Decimal("103")
    assert actions[0].drift_pct == Decimal("3")


def test_plan_ttl_takes_priority_over_requote():
    """SC-030-04 — TTL 만료 + 드리프트 동시면 cancel_ttl 우선."""
    o = _order(age_seconds=120, limit="100.00")
    quotes = {"AAPL": _q("110", "112", "111")}
    actions = plan_order_lifecycle(
        [o],
        configs={"r1": _cfg(ttl_seconds=60, requote_drift_pct=Decimal("2"))},
        quotes=quotes, now=NOW,
    )
    assert len(actions) == 1
    assert actions[0].kind == "cancel_ttl"


def test_plan_skips_rule_without_config():
    """SC-030-05 — lifecycle 설정 없는 룰의 주문은 계획에서 제외(옵트인)."""
    o = _order(age_seconds=999, rule_id="no-cfg")
    actions = plan_order_lifecycle([o], configs={"r1": _cfg(ttl_seconds=60)}, quotes={}, now=NOW)
    assert actions == []


def test_plan_market_order_not_requoted():
    """SC-030-08 — 시장가 주문은 재호가 대상 아님(limit 없음). TTL 은 적용."""
    o = _order(order_type="MARKET", limit=None, age_seconds=60)
    quotes = {"AAPL": _q("110", "112", "111")}
    actions = plan_order_lifecycle(
        [o], configs={"r1": _cfg(requote_drift_pct=Decimal("1"))}, quotes=quotes, now=NOW
    )
    assert actions == []  # 재호가 안 됨, TTL 미설정이라 아무 액션 없음.


def test_plan_partially_filled_not_requoted():
    """부분 체결 주문은 재호가에서 제외(잔량 재계산 필요 — TTL 취소에만 맡김)."""
    o = _order(state="PARTIALLY_FILLED", age_seconds=60, limit="100.00")
    quotes = {"AAPL": _q("110", "112", "111")}
    actions = plan_order_lifecycle(
        [o], configs={"r1": _cfg(requote_drift_pct=Decimal("1"))}, quotes=quotes, now=NOW
    )
    assert actions == []
