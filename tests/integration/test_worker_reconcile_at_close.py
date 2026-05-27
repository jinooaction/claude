"""스펙 001 T050/T052 — 워커 틱의 장 마감 정합성 자동 트리거 통합 테스트.

세션이 열림→닫힘으로 바뀌는 첫 틱에 로컬 보유를 브로커 잔고와 1회 대조하고,
불일치면 halt 로 다음 거래를 차단한다(조용한 상태 드리프트 방지, US2). 룰 0개
설정으로 quote fetch 경로를 피하고 정합성 경로만 검증한다.
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

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import Side
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import audit
from auto_invest.persistence import positions as positions_mod
from auto_invest.worker.halt import is_halted
from auto_invest.worker.loop import Worker, WorkerSettings

BASE = "https://api.example"
ACCOUNT = "1234567801"
OPEN = datetime(2026, 6, 3, 15, 0, tzinfo=UTC)  # Wed 11:00 EDT — 장중.
CLOSED = datetime(2026, 6, 3, 21, 0, tzinfo=UTC)  # Wed 17:00 EDT — 장마감 후.
BALANCE = "/uapi/overseas-stock/v1/trading/inquire-balance"
PSAMOUNT = "/uapi/overseas-stock/v1/trading/inquire-psamount"


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )


@asynccontextmanager
async def _worker(tmp_path: Path, *, paper_mode: bool) -> AsyncIterator[Worker]:
    settings = WorkerSettings(
        config=LoadedConfig(
            caps=_caps(),
            whitelist=Whitelist(symbols={"AAPL"}, accounts={ACCOUNT}),
            rules=(),
        ),
        db_path=tmp_path / "t.db",
        halt_path=tmp_path / "halt.flag",
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal("100"),
        require_session_open=True,
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


def _seed_local(worker: Worker, *, symbol: str, qty: int) -> None:
    positions_mod.update_from_fill(
        worker.conn, symbol=symbol, side=Side.BUY, qty=qty,
        price_usd=Decimal("100"), ts_utc="2026-06-03T13:31:00.000Z",
    )


def _mock_balance(mock, *, broker_qty: int) -> object:
    route = mock.get(BALANCE).mock(return_value=httpx.Response(200, json={
        "output1": [{"ovrs_pdno": "AAPL", "ovrs_cblc_qty": str(broker_qty),
                     "pchs_avg_pric": "100"}],
        "output2": {"tot_evlu_pfls_amt": "0", "tot_pftrt": "0"},
    }))
    mock.get(PSAMOUNT).mock(return_value=httpx.Response(
        200, json={"output": {"ord_psbl_frcr_amt": "1000"}}))
    return route


def _events(worker: Worker) -> list[str]:
    return [r["event_type"] for r in audit.read_all(worker.conn)]


def _run_results(worker: Worker) -> list[str]:
    return [
        r["result"]
        for r in worker.conn.execute(
            "SELECT result FROM reconciliation_runs ORDER BY seq"
        ).fetchall()
    ]


@pytest.mark.asyncio
async def test_session_close_triggers_reconciliation_ok(tmp_path: Path) -> None:
    """장중→마감 전이에서 정합성이 자동 실행되고, 일치하면 OK 를 기록한다."""
    async with _worker(tmp_path, paper_mode=False) as worker:
        _seed_local(worker, symbol="AAPL", qty=10)
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_balance(mock, broker_qty=10)
            await worker.tick(OPEN)  # 세션 열림 — 트리거 안 함.
            assert _run_results(worker) == []
            report = await worker.tick(CLOSED)  # 마감 전이 — 정합성 실행.
        assert report.skipped_reason == "session_closed"
        assert _run_results(worker) == ["OK"]
        assert "RECONCILIATION_OK" in _events(worker)
        assert is_halted(worker.settings.halt_path) is False


@pytest.mark.asyncio
async def test_session_close_mismatch_halts(tmp_path: Path) -> None:
    """마감 정합성이 불일치를 발견하면 halt 를 세워 다음 거래를 차단한다(US2)."""
    async with _worker(tmp_path, paper_mode=False) as worker:
        _seed_local(worker, symbol="AAPL", qty=10)  # 로컬 10.
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_balance(mock, broker_qty=7)  # 브로커 7 → 불일치.
            await worker.tick(OPEN)
            await worker.tick(CLOSED)
        assert _run_results(worker) == ["MISMATCH"]
        assert "RECONCILIATION_MISMATCH" in _events(worker)
        assert is_halted(worker.settings.halt_path) is True


@pytest.mark.asyncio
async def test_paper_mode_does_not_reconcile_at_close(tmp_path: Path) -> None:
    """paper 모드는 가상 보유라 마감 정합성을 호출하지 않는다(라이브 전용)."""
    async with _worker(tmp_path, paper_mode=True) as worker:
        _seed_local(worker, symbol="AAPL", qty=10)
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            route = _mock_balance(mock, broker_qty=10)
            await worker.tick(OPEN)
            await worker.tick(CLOSED)
        assert route.called is False
        assert _run_results(worker) == []


@pytest.mark.asyncio
async def test_reconcile_fires_once_per_close(tmp_path: Path) -> None:
    """한 번의 닫힘 구간에 정합성은 정확히 1회만 실행된다(이후 닫힘 틱은 전이 아님)."""
    async with _worker(tmp_path, paper_mode=False) as worker:
        _seed_local(worker, symbol="AAPL", qty=10)
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            _mock_balance(mock, broker_qty=10)
            await worker.tick(OPEN)
            await worker.tick(CLOSED)
            await worker.tick(CLOSED)  # 이미 닫힘 — 전이 아님 → 재실행 안 함.
        # 정합성 실행 행이 정확히 1건 — 두 번째 닫힘 틱은 재실행하지 않았다.
        assert _run_results(worker) == ["OK"]


@pytest.mark.asyncio
async def test_startup_while_closed_does_not_reconcile(tmp_path: Path) -> None:
    """시작 시 이미 닫혀 있으면 전이가 아니므로 정합성을 실행하지 않는다."""
    async with _worker(tmp_path, paper_mode=False) as worker:
        _seed_local(worker, symbol="AAPL", qty=10)
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            route = _mock_balance(mock, broker_qty=10)
            report = await worker.tick(CLOSED)  # 첫 틱이 닫힘 — 초기 상태.
        assert report.skipped_reason == "session_closed"
        assert route.called is False
        assert _run_results(worker) == []
