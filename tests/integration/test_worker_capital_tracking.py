"""스펙 029 슬라이스 2 — 워커의 자산 인식 유효 자본 통합 테스트.

게이트에 넘기는 자본 기준이 라이브 순자산(NAV = 현금 + 보유 시가평가)을 따라가는지,
방어(하락)는 항상·성장(상승)은 옵트인인지, 기본 끔이면 기존 동작 byte 동일인지 검증한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.rules import Action, PriceTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import audit
from auto_invest.worker.loop import Worker, WorkerSettings

BASE = "https://api.example"
ACCOUNT = "1234567801"
OPEN = datetime(2026, 6, 3, 15, 0, tzinfo=UTC)  # Wed 11:00 EDT — 장중.
QUOTE = "/uapi/overseas-price/v1/quotations/price"
ORDER = "/uapi/overseas-stock/v1/trading/order"
BALANCE = "/uapi/overseas-stock/v1/trading/inquire-balance"
PSAMOUNT = "/uapi/overseas-stock/v1/trading/inquire-psamount"
CCNL = "/uapi/overseas-stock/v1/trading/inquire-ccnl"


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )


def _rule(*, qty: int) -> TradingRule:
    # 항상 발화(quote <= 99999), MSFT 1주를 시장가 가까운 지정가로.
    return TradingRule(
        id="msft-rule",
        symbol="MSFT",
        stage=StrategyStage.CANARY,
        priority=10,
        enabled=True,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("99999"), cooldown_seconds=0),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=qty, limit_price="500.00"),
    )


@asynccontextmanager
async def _worker(
    tmp_path: Path,
    *,
    rules: list[TradingRule],
    starting_capital: str,
    tracking: bool,
    growth: bool = False,
    max_growth: str = "2",
    paper_mode: bool = False,
) -> AsyncIterator[Worker]:
    settings = WorkerSettings(
        config=LoadedConfig(
            caps=_caps(),
            whitelist=Whitelist(symbols={r.symbol for r in rules} or {"MSFT"}, accounts={ACCOUNT}),
            rules=tuple(rules),
        ),
        db_path=tmp_path / "t.db",
        halt_path=tmp_path / "halt.flag",
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal(starting_capital),
        require_session_open=False,
        paper_mode=paper_mode,
        capital_tracking_enabled=tracking,
        capital_growth_enabled=growth,
        capital_max_growth_factor=Decimal(max_growth),
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


def _mock_nav(mock, *, cash: str, holdings_eval: str) -> None:
    """NAV = cash + holdings_eval 가 되도록 KIS 잔고/예수금 엔드포인트를 모킹."""
    mock.get(BALANCE).mock(return_value=httpx.Response(200, json={
        "output1": [{"ovrs_pdno": "MSFT", "ovrs_cblc_qty": "1",
                     "pchs_avg_pric": "100", "frcr_evlu_amt2": holdings_eval}],
        "output2": {"tot_evlu_pfls_amt": "0"},
    }))
    mock.get(PSAMOUNT).mock(return_value=httpx.Response(
        200, json={"output": {"ord_psbl_frcr_amt": cash}}))


def _mock_quote_and_order(mock) -> None:
    mock.get(QUOTE).mock(return_value=httpx.Response(
        200, json={"output": {"last": "500.00", "bidp": "499.99", "askp": "500.01"}}))
    mock.post(ORDER).mock(return_value=httpx.Response(200, json={"output": {"ODNO": "K-1"}}))
    mock.get(CCNL).mock(return_value=httpx.Response(200, json={"output": []}))


def _gate_rejections(worker: Worker) -> list[dict]:
    rows = worker.conn.execute(
        "SELECT payload_json FROM audit_log WHERE event_type = 'ORDER_REJECTED_BY_GATE'"
    ).fetchall()
    import json
    return [json.loads(r["payload_json"]) for r in rows]


# ---------------------------------------------------- SC-15 기본 끔 = byte 동일


@pytest.mark.asyncio
async def test_sc15_tracking_off_does_not_fetch_nav(tmp_path: Path):
    """capital_tracking 끄면(기본) 워커는 NAV를 조회조차 안 한다 — 시작 자본 그대로."""
    async with _worker(
        tmp_path, rules=[_rule(qty=1)], starting_capital="100000", tracking=False
    ) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_quote_and_order(mock)
            balance_route = mock.get(BALANCE).mock(
                return_value=httpx.Response(200, json={"output1": []}))
            await worker.tick(OPEN)
        # NAV(잔고) 엔드포인트는 한 번도 안 불렸다.
        assert not balance_route.called
        # 유효 자본은 시작 자본 그대로.
        assert worker._effective_capital_usd == Decimal("100000")
        # EFFECTIVE_CAPITAL_UPDATED 이벤트 없음.
        events = [r["event_type"] for r in audit.read_all(worker.conn)]
        assert "EFFECTIVE_CAPITAL_UPDATED" not in events


# ---------------------------------------------------- SC-16 paper 비활성


@pytest.mark.asyncio
async def test_sc16_paper_mode_disables_tracking(tmp_path: Path):
    """paper 모드면 tracking을 켜도 NAV 조회 안 함(가상 계좌)."""
    async with _worker(
        tmp_path, rules=[], starting_capital="100000", tracking=True, paper_mode=True
    ) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            balance_route = mock.get(BALANCE).mock(
                return_value=httpx.Response(200, json={"output1": []}))
            await worker.tick(OPEN)
        assert not balance_route.called
        assert worker._effective_capital_usd == Decimal("100000")


# ---------------------------------------------------- SC-09/14 방어: 하락 시 캡 축소


@pytest.mark.asyncio
async def test_sc14_defense_drawdown_shrinks_caps(tmp_path: Path):
    """시작 $10,000, NAV $8,000 → 유효 자본 $8,000 → per-trade 캡 $400(=8000×5%).
    MSFT 1주 @ $500 노셔널 $500 > $400 → per-trade 게이트가 거부.
    (시작 $10,000 기준이면 캡 $500이라 통과했을 주문이 NAV 추종으로 거부됨.)"""
    async with _worker(
        tmp_path, rules=[_rule(qty=1)], starting_capital="10000", tracking=True
    ) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_quote_and_order(mock)
            _mock_nav(mock, cash="3000", holdings_eval="5000")  # NAV 8000
            report = await worker.tick(OPEN)
        # 유효 자본이 NAV로 내려갔다(방어).
        assert worker._effective_capital_usd == Decimal("8000")
        # per-trade 캡 $400 < 노셔널 $500 → 거부.
        rejections = _gate_rejections(worker)
        assert any(r["gate"] == "per_trade_cap_gate" for r in rejections)
        assert report.rules_fired == 1  # 룰은 발화했으나 게이트가 막음.
        # 감사 이벤트 기록됨.
        events = [r["event_type"] for r in audit.read_all(worker.conn)]
        assert "EFFECTIVE_CAPITAL_UPDATED" in events


@pytest.mark.asyncio
async def test_defense_event_reason(tmp_path: Path):
    """하락 시 EFFECTIVE_CAPITAL_UPDATED.reason == 'defense_drawdown'."""
    import json
    async with _worker(
        tmp_path, rules=[], starting_capital="10000", tracking=True
    ) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_nav(mock, cash="3000", holdings_eval="5000")  # NAV 8000
            await worker.tick(OPEN)
        rows = worker.conn.execute(
            "SELECT payload_json FROM audit_log "
            "WHERE event_type = 'EFFECTIVE_CAPITAL_UPDATED'"
        ).fetchall()
        assert len(rows) == 1
        p = json.loads(rows[0]["payload_json"])
        assert p["reason"] == "defense_drawdown"
        assert p["effective_capital_usd"] == "8000"
        assert p["nav_usd"] == "8000"


# ---------------------------------------------------- SC-10 성장 끔 = 시작 천장


@pytest.mark.asyncio
async def test_sc10_growth_off_keeps_starting_ceiling(tmp_path: Path):
    """tracking 켬·growth 끔, NAV $15,000 > 시작 $10,000 → 유효 자본 $10,000 유지.
    값이 안 바뀌므로 EFFECTIVE_CAPITAL_UPDATED 도 없다."""
    async with _worker(
        tmp_path, rules=[], starting_capital="10000", tracking=True, growth=False
    ) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_nav(mock, cash="5000", holdings_eval="10000")  # NAV 15000
            await worker.tick(OPEN)
        assert worker._effective_capital_usd == Decimal("10000")
        events = [r["event_type"] for r in audit.read_all(worker.conn)]
        assert "EFFECTIVE_CAPITAL_UPDATED" not in events


# ---------------------------------------------------- SC-11 성장 켬: 상승 반영


@pytest.mark.asyncio
async def test_sc11_growth_on_grows_caps(tmp_path: Path):
    """tracking·growth 켬, NAV $15,000, 상한 2배 → 유효 자본 $15,000.
    per-trade 캡 $750(=15000×5%) > 노셔널 $500 → MSFT 1주 통과."""
    import json
    async with _worker(
        tmp_path, rules=[_rule(qty=1)], starting_capital="10000",
        tracking=True, growth=True, max_growth="2",
    ) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_quote_and_order(mock)
            _mock_nav(mock, cash="5000", holdings_eval="10000")  # NAV 15000
            report = await worker.tick(OPEN)
        assert worker._effective_capital_usd == Decimal("15000")
        assert report.outcomes[0].state == "SUBMITTED"  # 캡 키워서 통과.
        rows = worker.conn.execute(
            "SELECT payload_json FROM audit_log "
            "WHERE event_type = 'EFFECTIVE_CAPITAL_UPDATED'"
        ).fetchall()
        p = json.loads(rows[0]["payload_json"])
        assert p["reason"] == "growth_applied"


# ---------------------------------------------------- SC-12 성장 상한 클램프


@pytest.mark.asyncio
async def test_sc12_growth_clamped(tmp_path: Path):
    """tracking·growth 켬, NAV $25,000, 상한 2배 → 유효 자본 $20,000 (클램프)."""
    import json
    async with _worker(
        tmp_path, rules=[], starting_capital="10000",
        tracking=True, growth=True, max_growth="2",
    ) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_nav(mock, cash="5000", holdings_eval="20000")  # NAV 25000
            await worker.tick(OPEN)
        assert worker._effective_capital_usd == Decimal("20000")
        rows = worker.conn.execute(
            "SELECT payload_json FROM audit_log "
            "WHERE event_type = 'EFFECTIVE_CAPITAL_UPDATED'"
        ).fetchall()
        p = json.loads(rows[0]["payload_json"])
        assert p["reason"] == "growth_clamped"


# ---------------------------------------------------- 폴백: NAV 조회 실패


@pytest.mark.asyncio
async def test_nav_fetch_failure_keeps_previous(tmp_path: Path):
    """NAV 조회 실패 시 유효 자본은 직전 값(시작 자본) 유지 — 거래 무중단."""
    async with _worker(
        tmp_path, rules=[], starting_capital="10000", tracking=True
    ) as worker:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            mock.get(BALANCE).mock(return_value=httpx.Response(500, json={}))
            mock.get(PSAMOUNT).mock(return_value=httpx.Response(500, json={}))
            # tick이 예외로 깨지지 않아야 한다.
            await worker.tick(OPEN)
        assert worker._effective_capital_usd == Decimal("10000")
