"""Spec 015 — 워커 틱의 라이브 체결 동기화 통합 테스트 (T009/T010).

룰 0개 설정으로 quote fetch 경로를 피하고, 체결 동기화 경로만 검증한다.
"""

from __future__ import annotations

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
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import audit
from auto_invest.persistence import positions as positions_mod
from auto_invest.persistence.audit import OrderIntentPayload
from auto_invest.worker.halt import is_halted
from auto_invest.worker.loop import Worker, WorkerSettings

BASE = "https://api.example"
ACCOUNT = "1234567801"
NOW = datetime(2026, 5, 26, 15, 0, tzinfo=UTC)
CCNL = "/uapi/overseas-stock/v1/trading/inquire-ccnl"


def _caps(*, breaker: bool = False) -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
        circuit_breaker_enabled=breaker,
        daily_loss_limit_pct=Decimal("10"),
        max_total_drawdown_pct=Decimal("20"),
    )


@asynccontextmanager
async def _worker(
    tmp_path: Path, *, paper_mode: bool, breaker: bool = False
) -> AsyncIterator[Worker]:
    settings = WorkerSettings(
        config=LoadedConfig(
            caps=_caps(breaker=breaker),
            whitelist=Whitelist(symbols={"AAPL"}, accounts={ACCOUNT}),
            rules=(),
        ),
        db_path=tmp_path / "t.db",
        halt_path=tmp_path / "halt.flag",
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal("100"),
        require_session_open=False,
        paper_mode=paper_mode,
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
    worker: Worker, *, corr: str, kis: str, symbol: str, side: str, qty: int
) -> None:
    worker.conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty, state, kis_order_id)
        VALUES (?, 'r1', ?, ?, 'LIMIT', ?, 'SUBMITTED', ?)
        """,
        (corr, symbol, side, qty, kis),
    )
    audit.append(
        worker.conn,
        OrderIntentPayload(
            rule_id="r1", symbol=symbol, side=side, order_type="LIMIT", qty=qty
        ),
        rule_id="r1", symbol=symbol, correlation_id=corr,
    )


def _ccnl(rows: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"output": rows})


def _state(worker: Worker, corr: str) -> str:
    return worker.conn.execute(
        "SELECT state FROM orders WHERE correlation_id=?", (corr,)
    ).fetchone()["state"]


@pytest.mark.asyncio
async def test_live_tick_pulls_fills(tmp_path: Path) -> None:
    """라이브 워커 틱이 열린 주문의 체결을 당겨 보유/상태에 반영한다."""
    async with _worker(tmp_path, paper_mode=False) as worker:
        _seed_order(worker, corr="ord-1", kis="K1", symbol="AAPL", side="BUY", qty=10)
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=_ccnl(
                [{"odno": "K1", "pdno": "AAPL", "ft_ccld_qty": "10", "ft_ccld_unpr3": "150"}]
            ))
            report = await worker.tick(NOW)
        assert report.skipped_reason is None
        assert _state(worker, "ord-1") == "FILLED"
        pos = positions_mod.get_position(worker.conn, "AAPL")
        assert pos is not None and pos.qty == 10


@pytest.mark.asyncio
async def test_paper_tick_does_not_sync_fills(tmp_path: Path) -> None:
    """paper 모드 틱은 체결 동기화를 호출하지 않는다(라이브 전용)."""
    async with _worker(tmp_path, paper_mode=True) as worker:
        _seed_order(worker, corr="ord-1", kis="K1", symbol="AAPL", side="BUY", qty=10)
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            route = mock.get(CCNL).mock(return_value=_ccnl([]))
            await worker.tick(NOW)
        assert route.called is False
        assert _state(worker, "ord-1") == "SUBMITTED"


@pytest.mark.asyncio
async def test_fill_sync_activates_live_breaker(tmp_path: Path) -> None:
    """체결 동기화가 라이브 매도 손실을 기록 → 다음 틱에 스펙 014 브레이커 트립.

    이 기능 없이는 라이브 FILL 이 0건이라 브레이커가 손실을 볼 수 없었다(US3).
    """
    async with _worker(tmp_path, paper_mode=False, breaker=True) as worker:
        # BUY 1 @ 100, SELL 1 @ 80 → 실현 -20 (한도 시작자본 100 의 10% = -10 초과).
        _seed_order(worker, corr="ord-buy", kis="KB", symbol="AAPL", side="BUY", qty=1)
        _seed_order(worker, corr="ord-sell", kis="KS", symbol="AAPL", side="SELL", qty=1)
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=_ccnl([
                {"odno": "KB", "pdno": "AAPL", "ft_ccld_qty": "1", "ft_ccld_unpr3": "100"},
                {"odno": "KS", "pdno": "AAPL", "ft_ccld_qty": "1", "ft_ccld_unpr3": "80"},
            ]))
            # 틱 1: 브레이커는 아직 체결 전 평가(무트립) → 체결 동기화가 손실 기록.
            r1 = await worker.tick(NOW)
            assert r1.skipped_reason is None
            assert not is_halted(worker.settings.halt_path)
            # 틱 2(cadence 경과): 브레이커가 기록된 손실을 보고 트립.
            r2 = await worker.tick(NOW + timedelta(seconds=6))
        assert r2.skipped_reason == "circuit_breaker_tripped"
        assert is_halted(worker.settings.halt_path)
        rows = [r for r in audit.read_all(worker.conn)
                if r["event_type"] == "CIRCUIT_BREAKER_TRIPPED"]
        assert len(rows) == 1
        assert audit.parse_payload(rows[0])["mode"] == "live"
