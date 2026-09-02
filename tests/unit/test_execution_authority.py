from __future__ import annotations

import fcntl
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.models import OrderRequest
from auto_invest.config.enums import OrderType, Side
from auto_invest.execution.authority import (
    ExecutionAuthority,
    ExecutionAuthorityBusy,
    ExecutionMaintenanceActive,
)
from auto_invest.persistence import db


def _client() -> ResilientClient:
    return ResilientClient(
        httpx.AsyncClient(base_url="https://api.example"),
        rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
        max_retries=1,
    )


def _authority(db_path: Path, *, account: str = "1234567801") -> ExecutionAuthority:
    conn = db.get_connection(db_path)
    db.migrate(conn)
    return ExecutionAuthority(
        conn=conn,
        broker=_client(),
        access_token="tok",
        app_key="app",
        app_secret="sec",
        account_no=account,
        lock_timeout_seconds=0,
        lock_ttl_seconds=30,
    )


@pytest.mark.asyncio
async def test_account_lock_is_exclusive_and_released(tmp_path: Path) -> None:
    db_path = tmp_path / "authority.db"
    first = _authority(db_path)
    second = _authority(db_path)
    try:
        async with first.account_lock("first write"):
            with pytest.raises(ExecutionAuthorityBusy):
                async with second.account_lock("second write"):
                    raise AssertionError("second lock must not be acquired")

        async with second.account_lock("after release"):
            row = second.conn.execute(
                "SELECT owner, context FROM execution_authority_locks WHERE account_no = ?",
                (second.account_no,),
            ).fetchone()
            assert row["owner"] == second.owner
            assert row["context"] == "after release"
    finally:
        await first.aclose()
        await second.aclose()


@pytest.mark.asyncio
async def test_expired_account_lock_is_reclaimed(tmp_path: Path) -> None:
    db_path = tmp_path / "authority.db"
    authority = _authority(db_path)
    expired = (datetime.now(UTC) - timedelta(minutes=5)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    authority.conn.execute(
        """
        INSERT INTO execution_authority_locks
            (account_no, owner, context, acquired_at_utc, expires_at_utc)
        VALUES (?, 'dead-owner', 'old process', ?, ?)
        """,
        (authority.account_no, expired, expired),
    )
    try:
        async with authority.account_lock("new write"):
            row = authority.conn.execute(
                "SELECT owner, context FROM execution_authority_locks WHERE account_no = ?",
                (authority.account_no,),
            ).fetchone()
            assert row["owner"] == authority.owner
            assert row["context"] == "new write"
    finally:
        await authority.aclose()


@pytest.mark.asyncio
async def test_maintenance_interlock_blocks_submit_and_cancel_before_broker_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "live-order-maintenance.lock"
    marker.write_text("HALTED\n", encoding="utf-8")
    monkeypatch.setattr(
        "auto_invest.execution.authority.DEFAULT_MAINTENANCE_INTERLOCK", marker
    )
    calls: list[str] = []

    async def fake_place_order(*args: object, **kwargs: object) -> None:
        calls.append("place")

    async def fake_cancel_order(*args: object, **kwargs: object) -> None:
        calls.append("cancel")

    monkeypatch.setattr("auto_invest.execution.authority.place_order", fake_place_order)
    monkeypatch.setattr(
        "auto_invest.execution.authority.cancel_order", fake_cancel_order
    )
    authority = _authority(tmp_path / "authority.db")
    authority.broker_write_lock_path = tmp_path / "broker-write.lock"
    authority.broker_write_lock_path.touch()
    request = OrderRequest(
        account=authority.account_no,
        symbol="SCHX",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        qty=1,
        limit_price_usd=Decimal("30.00"),
    )
    try:
        with pytest.raises(ExecutionMaintenanceActive):
            await authority.submit_broker_order(request=request, market="NYSE")
        with pytest.raises(ExecutionMaintenanceActive):
            await authority.cancel_broker_order(kis_order_id="K-1", market="NYSE")
        assert calls == []
        assert (
            authority.conn.execute(
                "SELECT COUNT(*) FROM execution_authority_locks"
            ).fetchone()[0]
            == 0
        )
    finally:
        await authority.aclose()


@pytest.mark.asyncio
async def test_exclusive_deploy_lock_blocks_broker_write_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock_path = tmp_path / "broker-write.lock"
    lock_path.touch()
    calls: list[str] = []

    async def fake_place_order(*args: object, **kwargs: object) -> None:
        calls.append("place")

    monkeypatch.setattr("auto_invest.execution.authority.place_order", fake_place_order)
    authority = _authority(tmp_path / "authority.db")
    authority.broker_write_lock_path = lock_path
    request = OrderRequest(
        account=authority.account_no,
        symbol="SCHX",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        qty=1,
        limit_price_usd=Decimal("30.00"),
    )
    try:
        with lock_path.open("r+") as exclusive:
            fcntl.flock(exclusive.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with pytest.raises(ExecutionMaintenanceActive):
                    await authority.submit_broker_order(request=request, market="NYSE")
            finally:
                fcntl.flock(exclusive.fileno(), fcntl.LOCK_UN)
        assert calls == []
    finally:
        await authority.aclose()


@pytest.mark.asyncio
async def test_missing_production_coordination_lock_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    async def fake_place_order(*args: object, **kwargs: object) -> None:
        calls.append("place")

    monkeypatch.setattr("auto_invest.execution.authority.place_order", fake_place_order)
    authority = _authority(tmp_path / "authority.db")
    authority.broker_write_lock_path = tmp_path / "missing-broker-write.lock"
    request = OrderRequest(
        account=authority.account_no,
        symbol="SCHX",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        qty=1,
        limit_price_usd=Decimal("30.00"),
    )
    try:
        with pytest.raises(ExecutionMaintenanceActive):
            await authority.submit_broker_order(request=request, market="NYSE")
        assert calls == []
    finally:
        await authority.aclose()
