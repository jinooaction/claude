"""스펙 030 — 워커 틱의 미체결 주문 수명 관리 통합 테스트 (SC-030-06/07) +
marketable-limit 제출 경로 (FR-030-03 / SC-030-08).

체결 동기화(스펙 015)는 빈 체결을 돌려주도록 목해서 주문이 SUBMITTED 로 남고,
수명 관리 경로만 검증한다.
"""

from __future__ import annotations

import json as _json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.rules import (
    Action,
    OrderLifecycleConfig,
    PriceTrigger,
    TradingRule,
)
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderRouter
from auto_invest.persistence import audit, db
from auto_invest.worker.loop import Worker, WorkerSettings

BASE = "https://api.example"
ACCOUNT = "1234567801"
NOW = datetime(2026, 5, 31, 15, 0, tzinfo=UTC)

CCNL = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
CANCEL = "/uapi/overseas-stock/v1/trading/order-rvsecncl"
QUOTE = "/uapi/overseas-price/v1/quotations/price"
PLACE = "/uapi/overseas-stock/v1/trading/order"


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )


def _rule(
    *,
    rule_id: str = "r1",
    symbol: str = "AAPL",
    lifecycle: OrderLifecycleConfig | None = None,
    enabled: bool = False,
) -> TradingRule:
    return TradingRule(
        id=rule_id,
        symbol=symbol,
        stage=StrategyStage.CANARY,
        priority=10,
        enabled=enabled,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("1"), cooldown_seconds=60),
        action=Action(
            side=Side.BUY, order_type=OrderType.LIMIT, qty=1, limit_price="100.00"
        ),
        lifecycle=lifecycle,
    )


@asynccontextmanager
async def _worker(
    tmp_path: Path, rules: tuple[TradingRule, ...]
) -> AsyncIterator[Worker]:
    settings = WorkerSettings(
        config=LoadedConfig(
            caps=_caps(),
            whitelist=Whitelist(symbols={"AAPL"}, accounts={ACCOUNT}),
            rules=rules,
        ),
        db_path=tmp_path / "t.db",
        halt_path=tmp_path / "halt.flag",
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal("100000"),
        require_session_open=False,
        paper_mode=False,
    )
    async with httpx.AsyncClient(base_url=BASE) as inner:
        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        worker = Worker(
            settings, broker=broker, access_token="tok", app_key="app",
            app_secret="sec", account_no=ACCOUNT,
        )
        try:
            yield worker
        finally:
            worker.close()


def _seed_order(
    worker: Worker,
    *,
    corr: str,
    kis: str,
    age_seconds: int,
    rule_id: str = "r1",
    symbol: str = "AAPL",
    limit: str | None = "100.00",
    order_type: str = "LIMIT",
    state: str = "SUBMITTED",
) -> None:
    submitted = (NOW - timedelta(seconds=age_seconds)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    worker.conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty,
             limit_price_usd, state, kis_order_id, submitted_at_utc)
        VALUES (?, ?, ?, 'BUY', ?, 1, ?, ?, ?, ?)
        """,
        (corr, rule_id, symbol, order_type, limit, state, kis, submitted),
    )


def _state(worker: Worker, corr: str) -> str:
    return worker.conn.execute(
        "SELECT state FROM orders WHERE correlation_id=?", (corr,)
    ).fetchone()["state"]


def _events(worker: Worker, event_type: str) -> list[dict]:
    return [
        _json.loads(r["payload_json"])
        for r in audit.read_all(worker.conn)
        if r["event_type"] == event_type
    ]


def _empty_ccnl() -> httpx.Response:
    return httpx.Response(200, json={"output": []})


# ------------------------------------------------------ SC-030-06 TTL cancel


@pytest.mark.asyncio
async def test_tick_cancels_ttl_expired_order(tmp_path: Path) -> None:
    """TTL 초과 미체결 주문 → cancel_order 호출 + CANCELLED 전이 + ORDER_TTL_CANCELLED 1건."""
    rule = _rule(lifecycle=OrderLifecycleConfig(ttl_seconds=60))
    async with _worker(tmp_path, (rule,)) as worker:
        _seed_order(worker, corr="ord-ttl", kis="K1", age_seconds=120)
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=_empty_ccnl())
            cancel_route = mock.post(CANCEL).mock(
                return_value=httpx.Response(200, json={"output": {}})
            )
            report = await worker.tick(NOW)
        assert report.skipped_reason is None
        assert cancel_route.called
        assert _state(worker, "ord-ttl") == "CANCELLED"
        evs = _events(worker, "ORDER_TTL_CANCELLED")
        assert len(evs) == 1
        assert evs[0]["kis_order_id"] == "K1"
        assert evs[0]["ttl_seconds"] == 60
        assert evs[0]["age_seconds"] >= 120


@pytest.mark.asyncio
async def test_tick_leaves_fresh_order_untouched(tmp_path: Path) -> None:
    """TTL 이내 주문은 취소되지 않는다(액션 0건)."""
    rule = _rule(lifecycle=OrderLifecycleConfig(ttl_seconds=300))
    async with _worker(tmp_path, (rule,)) as worker:
        _seed_order(worker, corr="ord-fresh", kis="K1", age_seconds=30)
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            mock.get(CCNL).mock(return_value=_empty_ccnl())
            cancel_route = mock.post(CANCEL).mock(
                return_value=httpx.Response(200, json={"output": {}})
            )
            await worker.tick(NOW)
        assert cancel_route.called is False
        assert _state(worker, "ord-fresh") == "SUBMITTED"
        assert _events(worker, "ORDER_TTL_CANCELLED") == []


# ------------------------------------------------------ SC-030-06 requote


@pytest.mark.asyncio
async def test_tick_requotes_drifted_order(tmp_path: Path) -> None:
    """드리프트 초과 지정가 → 취소 + ORDER_REQUOTED + submit_order 재호출(게이트 재통과)."""
    rule = _rule(
        lifecycle=OrderLifecycleConfig(
            requote_drift_pct=Decimal("2"), requote_after_seconds=30
        )
    )
    async with _worker(tmp_path, (rule,)) as worker:
        _seed_order(worker, corr="ord-drift", kis="K1", age_seconds=60, limit="100.00")
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=_empty_ccnl())
            mock.get(QUOTE).mock(
                return_value=httpx.Response(
                    200,
                    json={"output": {"last": "103", "bidp": "102.9", "askp": "103.1"}},
                )
            )
            cancel_route = mock.post(CANCEL).mock(
                return_value=httpx.Response(200, json={"output": {}})
            )
            place_route = mock.post(PLACE).mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K2"}})
            )
            report = await worker.tick(NOW)
        assert report.skipped_reason is None
        assert cancel_route.called
        assert place_route.called  # 재제출이 게이트 체인을 통과해 브로커에 도달.
        assert _state(worker, "ord-drift") == "CANCELLED"
        reqs = _events(worker, "ORDER_REQUOTED")
        assert len(reqs) == 1
        assert reqs[0]["old_kis_order_id"] == "K1"
        assert Decimal(reqs[0]["mid_price_usd"]) == Decimal("103")
        assert Decimal(reqs[0]["drift_pct"]) == Decimal("3")
        assert reqs[0]["old_limit_price_usd"] == "100.00"
        # 재제출된 새 주문이 INTENT→SUBMITTED 정상 경로를 탔다.
        subs = _events(worker, "ORDER_SUBMITTED")
        assert any(s["kis_order_id"] == "K2" for s in subs)


@pytest.mark.asyncio
async def test_tick_no_requote_within_tolerance(tmp_path: Path) -> None:
    """드리프트가 임계 이내면 재호가 안 함(취소·재제출 0건)."""
    rule = _rule(
        lifecycle=OrderLifecycleConfig(requote_drift_pct=Decimal("5"), requote_after_seconds=30)
    )
    async with _worker(tmp_path, (rule,)) as worker:
        _seed_order(worker, corr="ord-near", kis="K1", age_seconds=60, limit="100.00")
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            mock.get(CCNL).mock(return_value=_empty_ccnl())
            mock.get(QUOTE).mock(
                return_value=httpx.Response(
                    200, json={"output": {"last": "101", "bidp": "100.9", "askp": "101.1"}}
                )
            )
            cancel_route = mock.post(CANCEL).mock(
                return_value=httpx.Response(200, json={"output": {}})
            )
            await worker.tick(NOW)
        assert cancel_route.called is False
        assert _state(worker, "ord-near") == "SUBMITTED"
        assert _events(worker, "ORDER_REQUOTED") == []


# ------------------------------------------------------ SC-030-07 isolation


@pytest.mark.asyncio
async def test_cancel_failure_isolated(tmp_path: Path) -> None:
    """브로커 취소 실패는 격리 — 상태 안 바뀌고 틱이 안 깨진다."""
    rule = _rule(lifecycle=OrderLifecycleConfig(ttl_seconds=60))
    async with _worker(tmp_path, (rule,)) as worker:
        _seed_order(worker, corr="ord-fail", kis="K1", age_seconds=120)
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=_empty_ccnl())
            mock.post(CANCEL).mock(return_value=httpx.Response(500, json={"err": "x"}))
            report = await worker.tick(NOW)
        assert report.skipped_reason is None  # 틱 안 깨짐.
        assert _state(worker, "ord-fail") == "SUBMITTED"  # 상태 미변경.
        assert _events(worker, "ORDER_TTL_CANCELLED") == []  # 취소 실패라 감사도 없음.


@pytest.mark.asyncio
async def test_no_lifecycle_config_is_noop(tmp_path: Path) -> None:
    """lifecycle 설정 없는 룰은 수명 관리를 전혀 받지 않는다(옵트인, 호가 조회도 안 함)."""
    rule = _rule(lifecycle=None)
    async with _worker(tmp_path, (rule,)) as worker:
        _seed_order(worker, corr="ord-x", kis="K1", age_seconds=9999)
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            mock.get(CCNL).mock(return_value=_empty_ccnl())
            quote_route = mock.get(QUOTE).mock(
                return_value=httpx.Response(200, json={"output": {"last": "103"}})
            )
            cancel_route = mock.post(CANCEL).mock(
                return_value=httpx.Response(200, json={"output": {}})
            )
            await worker.tick(NOW)
        assert quote_route.called is False
        assert cancel_route.called is False
        assert _state(worker, "ord-x") == "SUBMITTED"


# ------------------------------------------------------ FR-030-03 marketable limit


@asynccontextmanager
async def _router(tmp_path: Path) -> AsyncIterator[OrderRouter]:
    conn = db.get_connection(tmp_path / "r.db")
    db.migrate(conn)
    async with httpx.AsyncClient(base_url=BASE) as inner:
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        yield OrderRouter(
            conn=conn,
            broker=client,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no=ACCOUNT,
            whitelist=Whitelist(symbols={"AAPL"}, accounts={ACCOUNT}),
            caps=_caps(),
            halt_path=tmp_path / "halt.flag",
            market="NASD",
        )
    conn.close()


@pytest.mark.asyncio
async def test_marketable_limit_used_on_submit(tmp_path: Path) -> None:
    """marketable_limit_bps 설정 시 제출 limit_price 가 ask 기반 marketable 값(표현식 무시)."""
    rule = _rule(
        rule_id="mk", lifecycle=OrderLifecycleConfig(marketable_limit_bps=20), enabled=True
    )
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post(PLACE).mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K9"}})
            )
            await router.submit_order(
                rule=rule,
                quote_price_usd=Decimal("100"),
                quote_ask_usd=Decimal("100"),
                quote_bid_usd=Decimal("99.9"),
                total_capital_usd=Decimal("100000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )
        intent = next(
            r for r in audit.read_all(router.conn) if r["event_type"] == "ORDER_INTENT"
        )
        p = _json.loads(intent["payload_json"])
        # ask 100 + 20bps = 100.20 (표현식 "100.00" 이 아님).
        assert p["limit_price_usd"] == "100.20"


@pytest.mark.asyncio
async def test_marketable_limit_falls_back_without_quote(tmp_path: Path) -> None:
    """호가가 없으면 marketable 계산 불가 → 기존 limit_price 표현식("100.00")으로 폴백."""
    rule = _rule(
        rule_id="mk2", lifecycle=OrderLifecycleConfig(marketable_limit_bps=20), enabled=True
    )
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post(PLACE).mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K8"}})
            )
            await router.submit_order(
                rule=rule,
                quote_price_usd=Decimal("100"),
                quote_ask_usd=None,
                quote_bid_usd=None,
                total_capital_usd=Decimal("100000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )
        intent = next(
            r for r in audit.read_all(router.conn) if r["event_type"] == "ORDER_INTENT"
        )
        p = _json.loads(intent["payload_json"])
        assert p["limit_price_usd"] == "100.00"  # 표현식 폴백.
