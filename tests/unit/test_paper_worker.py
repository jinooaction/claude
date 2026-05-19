"""Spec 009 T009 — Worker paper_mode 단위 테스트.

`WorkerSettings(paper_mode=True)`에서:
  - `record_start`가 PAPER_RUN_STARTED를 기록 (WORKER_STARTED 아님).
  - `record_stop`이 PAPER_RUN_STOPPED를 기록 (WORKER_STOPPED 아님).
  - OrderRouter에 paper_mode=True와 paper_session_id가 전달된다.

대응 변경: `src/auto_invest/worker/loop.py`의 WorkerSettings + Worker.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.worker.loop import Worker, WorkerSettings


def _settings(tmp_path: Path, *, paper_mode: bool = False) -> WorkerSettings:
    caps = SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )
    whitelist = Whitelist(symbols=set(), accounts=set())
    config = LoadedConfig(
        rules=(),
        whitelist=whitelist,
        caps=caps,
    )
    return WorkerSettings(
        config=config,
        db_path=tmp_path / "t.db",
        halt_path=tmp_path / "halt.flag",
        config_path=tmp_path / "rules.toml",
        total_capital_usd=Decimal("100000"),
        require_session_open=False,
        paper_mode=paper_mode,
        ruleset_sha256="a" * 64 if paper_mode else None,
    )


@pytest_asyncio.fixture
async def paper_worker(tmp_path):
    async with httpx.AsyncClient(base_url="https://api.example") as inner:
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        worker = Worker(
            _settings(tmp_path, paper_mode=True),
            broker=client,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no="1234567801",
        )
        yield worker
        worker.close()


@pytest_asyncio.fixture
async def live_worker(tmp_path):
    async with httpx.AsyncClient(base_url="https://api.example") as inner:
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        worker = Worker(
            _settings(tmp_path, paper_mode=False),
            broker=client,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no="1234567801",
        )
        yield worker
        worker.close()


# ----------------------------------------------------------- record_start


@pytest.mark.asyncio
async def test_paper_worker_record_start_uses_paper_payload(paper_worker):
    paper_worker.record_start(secret_keys=["KIS_APP_KEY"])

    rows = list(paper_worker.conn.execute(
        "SELECT event_type FROM audit_log ORDER BY seq"
    ))
    event_types = [r["event_type"] for r in rows]
    # paper-mode면 WORKER_STARTED 대신 PAPER_RUN_STARTED
    assert "PAPER_RUN_STARTED" in event_types
    assert "WORKER_STARTED" not in event_types


@pytest.mark.asyncio
async def test_live_worker_record_start_uses_worker_payload(live_worker):
    live_worker.record_start(secret_keys=["KIS_APP_KEY"])

    rows = list(live_worker.conn.execute(
        "SELECT event_type FROM audit_log ORDER BY seq"
    ))
    event_types = [r["event_type"] for r in rows]
    assert "WORKER_STARTED" in event_types
    assert "PAPER_RUN_STARTED" not in event_types


# ----------------------------------------------------------- record_stop


@pytest.mark.asyncio
async def test_paper_worker_record_stop_uses_paper_payload(paper_worker):
    paper_worker.record_start(secret_keys=["KIS_APP_KEY"])
    paper_worker.record_stop("normal_shutdown")

    rows = list(paper_worker.conn.execute(
        "SELECT event_type FROM audit_log ORDER BY seq"
    ))
    event_types = [r["event_type"] for r in rows]
    assert "PAPER_RUN_STOPPED" in event_types
    assert "WORKER_STOPPED" not in event_types


# ----------------------------------------------------------- router wiring


@pytest.mark.asyncio
async def test_paper_worker_propagates_paper_mode_to_router(paper_worker):
    """Worker가 OrderRouter 생성 시 paper_mode=True를 전달."""
    assert paper_worker.router.paper_mode is True


@pytest.mark.asyncio
async def test_live_worker_router_is_not_paper(live_worker):
    assert live_worker.router.paper_mode is False


# ----------------------------------------------------------- session id linking


@pytest.mark.asyncio
async def test_paper_worker_sets_paper_session_id_after_start(paper_worker):
    """record_start로 PAPER_RUN_STARTED를 남긴 직후, router의 paper_session_id가
    그 row의 seq로 갱신되어야 ORDER_PAPER_FILLED가 같은 세션에 묶일 수 있다.
    """
    paper_worker.record_start(secret_keys=["KIS_APP_KEY"])
    rows = list(paper_worker.conn.execute(
        "SELECT seq FROM audit_log WHERE event_type = 'PAPER_RUN_STARTED'"
    ))
    assert len(rows) == 1
    expected_session = rows[0]["seq"]
    assert paper_worker.router.paper_session_id == expected_session
