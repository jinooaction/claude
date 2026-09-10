"""User launch entry: existing ledger/configuration, fixed production transports."""

import re
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.intraday_inputs import REST_URL
from auto_invest.config.loader import load_config, load_secrets
from auto_invest.execution.authority import DEFAULT_BROKER_WRITE_LOCK
from auto_invest.execution.intraday_program import build_kis_program
from auto_invest.execution.order_router import OrderRouter
from auto_invest.execution.preparation import confirmed_budget
from auto_invest.market_data.intraday import CALENDAR, NY, DataError, ReadTransport, collect_kis
from auto_invest.persistence.db import pending_migrations
from auto_invest.reconciliation.external_holdings import load_external_holdings

ROOT = Path(__file__).resolve().parents[3]


def _open_existing(database):
    path = Path(database).resolve(strict=True)
    if not path.is_file() or path.stat().st_nlink != 1:
        raise DataError("LAUNCH_EXISTING_LEDGER_REQUIRED")
    conn = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        if pending_migrations(conn):
            raise DataError("LAUNCH_LEDGER_MIGRATION_REQUIRED")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
    except BaseException:
        conn.close()
        raise


async def launch(*, database, rules, archives, forward_database, registration,
                 external_holdings, halt_path, token_cache, stop_event):
    """No new ledger, imported plugin, approval override, or live service setup.

    The caller is the explicit execution-start command. Tests replace only the
    transport/evidence dependencies; this function has no bypass/live-test flags.
    """
    conn = None
    try:
        secrets = load_secrets()
        config = load_config(rules)
        # Missing baseline must be explicit, rather than silently becoming {}.
        if not Path(external_holdings).is_file():
            raise DataError("LAUNCH_HOLDINGS_BASELINE_REQUIRED")
        baseline = load_external_holdings(external_holdings)
        budget = confirmed_budget(
            ROOT / "specs/182-intraday-kis-execution/contracts/confirmed-budget.json",
        )
        conn = _open_existing(database)
        async with httpx.AsyncClient(
            base_url=REST_URL, timeout=10, follow_redirects=False,
        ) as http:
            broker = ResilientClient(
                http, rate_limiter=AsyncTokenBucket(1, 1),
                breaker=CircuitBreaker(3, 30), max_retries=2,
            )
            router = OrderRouter(
                conn=conn, broker=broker, access_token="",
                app_key=secrets["KIS_APP_KEY"], app_secret=secrets["KIS_APP_SECRET"],
                account_no=secrets["KIS_ACCOUNT_NO"], whitelist=config.whitelist, caps=config.caps,
                halt_path=halt_path, paper_mode=False,
                broker_write_lock_path=DEFAULT_BROKER_WRITE_LOCK,
            )
            transport = ReadTransport(http)

            async def collect():
                now = datetime.now(UTC)
                session = now.astimezone(NY).date()
                if not CALENDAR.is_session(str(session)):
                    raise DataError("LAUNCH_WAIT_SESSION")
                opening = CALENDAR.session_open(str(session)).to_pydatetime()
                closing = CALENDAR.session_close(str(session)).to_pydatetime()
                end = min(now.replace(minute=now.minute // 5 * 5, second=0, microsecond=0), closing)
                if end <= opening:
                    raise DataError("LAUNCH_WAIT_COMPLETE_BAR")
                batch = await collect_kis(transport, secrets, opening, end, now, token_cache)
                return batch["bars"]

            program = await build_kis_program(
                router=router, token_cache=token_cache, archives=archives,
                forward_database=forward_database, registration=registration,
                collect_bars=collect, capital_limit=Decimal(budget["capital_limit_usd"]),
                external_holdings=baseline, now=lambda: datetime.now(UTC),
            )
            return await program.run(stop_event=stop_event)
    except DataError:
        raise
    except ValueError as exc:
        if re.fullmatch(r"(?:PROGRAM|QUALIFICATION|ACCOUNT)_[A-Z_]+", str(exc)):
            raise DataError(str(exc)) from None
        raise DataError("LAUNCH_CONFIGURATION_INVALID") from None
    except (OSError, sqlite3.Error):
        raise DataError("LAUNCH_LOCAL_INPUT_UNAVAILABLE") from None
    finally:
        if conn is not None:
            conn.close()
