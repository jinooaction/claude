from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.execution.authority import ExecutionAuthority, ExecutionAuthorityBusy
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
