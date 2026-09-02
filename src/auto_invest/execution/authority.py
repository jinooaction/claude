"""Single broker-write authority for live execution.

All live broker mutations pass through this module. The authority owns an
account-scoped SQLite lock so independent worker/rebalance processes cannot
evaluate and submit broker writes from the same stale account snapshot.
"""

from __future__ import annotations

import asyncio
import fcntl
import sqlite3
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.models import OrderRequest, OrderResult
from auto_invest.broker.overseas import cancel_order, place_order

DEFAULT_MAINTENANCE_INTERLOCK = Path(
    "/run/auto-invest-deploy/live-order-maintenance.lock"
)
DEFAULT_BROKER_WRITE_LOCK = Path("/run/auto-invest-deploy/broker-write.lock")


def maintenance_interlock_refusal() -> str | None:
    """Return a fail-closed reason while an owner emergency deploy is active."""

    try:
        DEFAULT_MAINTENANCE_INTERLOCK.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        return f"cannot verify deploy maintenance interlock: {type(exc).__name__}"
    return "live broker writes are halted for an owner emergency deploy"


class ExecutionMaintenanceActive(RuntimeError):
    """Raised before a broker mutation while the deploy interlock exists."""


@contextmanager
def broker_write_coordination(path: Path | None):
    """Hold the shared broker-write side of the deploy exclusion lock.

    Production entry points pass the fixed root-prepared path. ``None`` exists
    only for paper/test authorities that cannot write to a live broker.
    """

    if path is None:
        yield
        return
    try:
        lock_file = path.open("r+")
    except OSError as exc:
        raise ExecutionMaintenanceActive(
            f"cannot open broker-write coordination lock: {type(exc).__name__}"
        ) from exc
    try:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            raise ExecutionMaintenanceActive(
                "owner emergency deploy owns the broker-write coordination lock"
            ) from exc
        if refusal := maintenance_interlock_refusal():
            raise ExecutionMaintenanceActive(refusal)
        yield
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso_ms(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{moment.astimezone(UTC).microsecond // 1000:03d}Z"
    )


class ExecutionAuthorityBusy(RuntimeError):
    """Raised when another process already owns the account write lock."""

    def __init__(self, account_no: str, context: str) -> None:
        super().__init__(f"execution authority busy for account {account_no}: {context}")
        self.account_no = account_no
        self.context = context


@dataclass
class ExecutionAuthority:
    """Owns live broker write credentials plus an account-scoped lock."""

    conn: sqlite3.Connection
    broker: ResilientClient
    access_token: str
    app_key: str
    app_secret: str
    account_no: str
    lock_timeout_seconds: float = 5.0
    lock_ttl_seconds: int = 120
    lock_poll_seconds: float = 0.05
    now: Callable[[], datetime] = field(default=_utcnow)
    owner: str = field(default_factory=lambda: f"authority-{uuid.uuid4().hex}")
    broker_write_lock_path: Path | None = None

    @asynccontextmanager
    async def account_lock(self, context: str) -> AsyncIterator[None]:
        """Acquire the account lock for one broker-write decision scope."""
        acquired = await self._acquire(context)
        if not acquired:
            raise ExecutionAuthorityBusy(self.account_no, context)
        try:
            yield
        finally:
            self.release()

    async def submit_broker_order(
        self,
        *,
        request: OrderRequest,
        market: str,
    ) -> OrderResult:
        """Submit a live order through the single broker-write surface."""
        with broker_write_coordination(self.broker_write_lock_path):
            return await place_order(
                self.broker,
                access_token=self.access_token,
                app_key=self.app_key,
                app_secret=self.app_secret,
                request=request,
                market=market,
            )

    async def cancel_broker_order(
        self,
        *,
        kis_order_id: str,
        market: str,
    ) -> None:
        """Cancel a live order through the single broker-write surface."""
        async with self.account_lock(f"cancel:{kis_order_id}:{market}"):
            with broker_write_coordination(self.broker_write_lock_path):
                await cancel_order(
                    self.broker,
                    access_token=self.access_token,
                    app_key=self.app_key,
                    app_secret=self.app_secret,
                    account=self.account_no,
                    kis_order_id=kis_order_id,
                    market=market,
                )

    def release(self) -> None:
        """Release this authority's row if it still owns it."""
        self.conn.execute(
            """
            DELETE FROM execution_authority_locks
            WHERE account_no = ? AND owner = ?
            """,
            (self.account_no, self.owner),
        )

    async def aclose(self) -> None:
        """Best-effort cleanup for tests that create standalone clients."""
        self.release()
        client = getattr(self.broker, "_client", None)
        if client is not None and hasattr(client, "aclose"):
            await client.aclose()

    async def _acquire(self, context: str) -> bool:
        deadline = asyncio.get_running_loop().time() + max(
            0.0, self.lock_timeout_seconds
        )
        while True:
            try:
                if self._try_acquire_once(context):
                    return True
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(max(0.0, self.lock_poll_seconds))

    def _try_acquire_once(self, context: str) -> bool:
        now = self.now().astimezone(UTC)
        acquired_at = _iso_ms(now)
        expires_at = _iso_ms(now + timedelta(seconds=self.lock_ttl_seconds))
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                """
                DELETE FROM execution_authority_locks
                WHERE account_no = ? AND expires_at_utc <= ?
                """,
                (self.account_no, acquired_at),
            )
            row = self.conn.execute(
                """
                SELECT owner FROM execution_authority_locks
                WHERE account_no = ?
                """,
                (self.account_no,),
            ).fetchone()
            if row is not None:
                self.conn.execute("ROLLBACK")
                return False
            self.conn.execute(
                """
                INSERT INTO execution_authority_locks
                    (account_no, owner, context, acquired_at_utc, expires_at_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.account_no, self.owner, context, acquired_at, expires_at),
            )
            self.conn.execute("COMMIT")
            return True
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
