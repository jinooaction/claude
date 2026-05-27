"""Spec 014 — 손실 서킷 브레이커 워커 통합 테스트 (T009).

트립 경로는 룰 평가(=quote fetch) 전에 반환하므로 브로커 모킹이 필요 없다.
'no trip' 경로는 룰 0개 설정으로 quote fetch 를 피한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import audit
from auto_invest.persistence.audit import OrderPaperFilledPayload, PaperRunStartedPayload
from auto_invest.worker.halt import is_halted, read_halt, set_halt
from auto_invest.worker.loop import Worker, WorkerSettings

BASE = "https://api.example"
ACCOUNT = "1234567801"
NOW = datetime(2026, 5, 26, 15, 0, tzinfo=UTC)


def _caps(*, enabled: bool = True, daily: str = "10", drawdown: str = "20") -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
        circuit_breaker_enabled=enabled,
        daily_loss_limit_pct=Decimal(daily),
        max_total_drawdown_pct=Decimal(drawdown),
    )


@asynccontextmanager
async def _worker(
    tmp_path: Path,
    *,
    rules: list[TradingRule],
    caps: SizingCaps,
    halt_set: bool = False,
) -> AsyncIterator[Worker]:
    halt_path = tmp_path / "halt.flag"
    if halt_set:
        set_halt(halt_path, "pre-existing halt")
    settings = WorkerSettings(
        config=LoadedConfig(
            caps=caps,
            whitelist=Whitelist(symbols={"AAPL"}, accounts={ACCOUNT}),
            rules=tuple(rules),
        ),
        db_path=tmp_path / "t.db",
        halt_path=halt_path,
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal("100"),
        require_session_open=False,
        paper_mode=True,
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


def _seed_paper_fill(worker: Worker, *, side: str, qty: int, price: str, ts: str, sid: int):
    audit.append(
        worker.conn,
        OrderPaperFilledPayload(
            rule_id="R", symbol="AAPL", side=side, qty=qty,
            simulated_fill_price_usd=price, quote_source="ask",
            correlation_id=f"AAPL-{side}-{ts}", paper_session_id=sid,
        ),
        rule_id="R", symbol="AAPL", correlation_id=f"AAPL-{side}-{ts}", ts_utc=ts,
    )


def _session(worker: Worker) -> int:
    return audit.append(
        worker.conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-26T00:00:00.000Z", host="t",
        ),
    )


def _breaker_rows(worker: Worker) -> list:
    return [r for r in audit.read_all(worker.conn)
            if r["event_type"] == "CIRCUIT_BREAKER_TRIPPED"]


@pytest.mark.asyncio
async def test_tick_trips_on_daily_loss(tmp_path: Path):
    """오늘 -20 실현 손실 (한도 -10) → 트립: skipped + halt 세워짐 + 감사 row 1건."""
    async with _worker(tmp_path, rules=[], caps=_caps()) as worker:
        sid = _session(worker)
        _seed_paper_fill(worker, side="BUY", qty=1, price="100",
                         ts="2026-05-26T10:00:00.000Z", sid=sid)
        _seed_paper_fill(worker, side="SELL", qty=1, price="80",
                         ts="2026-05-26T11:00:00.000Z", sid=sid)
        report = await worker.tick(NOW)
        assert report.skipped_reason == "circuit_breaker_tripped"
        assert is_halted(worker.settings.halt_path)
        halt = read_halt(worker.settings.halt_path)
        assert halt is not None and "circuit_breaker" in halt.reason
        rows = _breaker_rows(worker)
        assert len(rows) == 1
        payload = audit.parse_payload(rows[0])
        assert "daily_loss" in payload["breached"]
        assert payload["mode"] == "paper"


@pytest.mark.asyncio
async def test_tick_no_trip_within_limits(tmp_path: Path):
    """-5 실현 손실 (한도 -10 미만) → 트립 안 함, tick 정상 진행."""
    async with _worker(tmp_path, rules=[], caps=_caps()) as worker:
        sid = _session(worker)
        _seed_paper_fill(worker, side="BUY", qty=1, price="100",
                         ts="2026-05-26T10:00:00.000Z", sid=sid)
        _seed_paper_fill(worker, side="SELL", qty=1, price="95",
                         ts="2026-05-26T11:00:00.000Z", sid=sid)
        report = await worker.tick(NOW)
        assert report.skipped_reason is None
        assert not is_halted(worker.settings.halt_path)
        assert _breaker_rows(worker) == []


@pytest.mark.asyncio
async def test_tick_disabled_breaker_skips(tmp_path: Path):
    """브레이커 비활성이면 손실이 한도를 넘어도 트립 안 함."""
    async with _worker(tmp_path, rules=[], caps=_caps(enabled=False)) as worker:
        sid = _session(worker)
        _seed_paper_fill(worker, side="BUY", qty=1, price="100",
                         ts="2026-05-26T10:00:00.000Z", sid=sid)
        _seed_paper_fill(worker, side="SELL", qty=1, price="50",
                         ts="2026-05-26T11:00:00.000Z", sid=sid)
        report = await worker.tick(NOW)
        assert report.skipped_reason is None
        assert not is_halted(worker.settings.halt_path)


@pytest.mark.asyncio
async def test_already_halted_no_breaker_eval(tmp_path: Path):
    """이미 halt 면 halt_flag_set 로 먼저 끝나고 브레이커 평가/감사 0건(멱등)."""
    async with _worker(tmp_path, rules=[], caps=_caps(), halt_set=True) as worker:
        sid = _session(worker)
        _seed_paper_fill(worker, side="BUY", qty=1, price="100",
                         ts="2026-05-26T10:00:00.000Z", sid=sid)
        _seed_paper_fill(worker, side="SELL", qty=1, price="50",
                         ts="2026-05-26T11:00:00.000Z", sid=sid)
        report = await worker.tick(NOW)
        assert report.skipped_reason == "halt_flag_set"
        assert _breaker_rows(worker) == []


@pytest.mark.asyncio
async def test_trip_is_idempotent_across_ticks(tmp_path: Path):
    """트립 후 다음 틱은 halt 선점 → 중복 CIRCUIT_BREAKER_TRIPPED 0건."""
    async with _worker(tmp_path, rules=[], caps=_caps()) as worker:
        sid = _session(worker)
        _seed_paper_fill(worker, side="BUY", qty=1, price="100",
                         ts="2026-05-26T10:00:00.000Z", sid=sid)
        _seed_paper_fill(worker, side="SELL", qty=1, price="80",
                         ts="2026-05-26T11:00:00.000Z", sid=sid)
        await worker.tick(NOW)
        await worker.tick(datetime(2026, 5, 26, 15, 1, tzinfo=UTC))
        assert len(_breaker_rows(worker)) == 1
