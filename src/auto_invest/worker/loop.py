"""Worker main loop (T044).

Coordinates the per-tick rule-evaluation pipeline:

  fetch quote -> evaluate trigger -> route order through gates+broker
                                                    -> audit log

Designed so the long-running `run_forever` is a thin loop around
`tick`, which can be driven directly by tests for deterministic
assertions (no real sleeping, no timing dependence).
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.overseas import get_quote
from auto_invest.config.loader import LoadedConfig
from auto_invest.config.rules import IndicatorTrigger, TradingRule
from auto_invest.execution.order_router import (
    OrderOutcome,
    OrderRouter,
    verify_stage_uniqueness,
)
from auto_invest.market_data.feed import store_synthetic_bar
from auto_invest.market_data.store import get_bars
from auto_invest.persistence import audit, db
from auto_invest.persistence import positions as positions_mod
from auto_invest.persistence.audit import (
    RuleLoadPayload,
    SecretsLoadedPayload,
    WorkerStartedPayload,
    WorkerStoppedPayload,
)
from auto_invest.strategy.canary import restore_pause_status
from auto_invest.strategy.triggers import TriggerContext, evaluate
from auto_invest.worker.halt import is_halted
from auto_invest.worker.schedule import is_session_open

logger = logging.getLogger(__name__)


@dataclass
class WorkerSettings:
    """Runtime configuration for one Worker instance."""

    config: LoadedConfig
    db_path: Path
    halt_path: Path
    config_path: Path
    total_capital_usd: Decimal
    market_quote: str = "NAS"
    market_order: str = "NASD"
    tick_interval_seconds: float = 1.0
    require_session_open: bool = True


@dataclass
class TickReport:
    """Diagnostic outcome of one tick — used by tests and the CLI."""

    skipped_reason: str | None = None
    rules_evaluated: int = 0
    rules_fired: int = 0
    outcomes: list[OrderOutcome] = field(default_factory=list)


class Worker:
    """Holds the connection, broker client, router, and per-rule fire history."""

    def __init__(
        self,
        settings: WorkerSettings,
        *,
        broker: ResilientClient,
        access_token: str,
        app_key: str,
        app_secret: str,
        account_no: str,
    ) -> None:
        self.settings = settings
        self.broker = broker
        self.access_token = access_token
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no

        self.conn = db.get_connection(settings.db_path)
        db.migrate(self.conn)

        self._stop_requested = asyncio.Event()
        self._last_fired: dict[str, datetime] = {}
        self._paused_rules: set[str] = {
            r.id for r in settings.config.rules
            if restore_pause_status(self.conn, r.id)
        }

        self.router = OrderRouter(
            conn=self.conn,
            broker=broker,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            account_no=account_no,
            whitelist=settings.config.whitelist,
            caps=settings.config.caps,
            halt_path=settings.halt_path,
            market=settings.market_order,
            quote_market=settings.market_quote,
        )

    # ---------------------------------------------- lifecycle audit

    def record_start(self, *, secret_keys: Iterable[str]) -> None:
        audit.append(
            self.conn,
            SecretsLoadedPayload(keys=sorted(secret_keys)),
        )
        audit.append(
            self.conn,
            WorkerStartedPayload(
                pid=os.getpid(),
                config_path=str(self.settings.config_path),
            ),
        )
        audit.append(
            self.conn,
            RuleLoadPayload(
                rule_count=len(self.settings.config.rules),
                rule_ids=[r.id for r in self.settings.config.rules],
            ),
        )

    def record_stop(self, reason: str) -> None:
        audit.append(self.conn, WorkerStoppedPayload(reason=reason))

    def request_stop(self) -> None:
        self._stop_requested.set()

    # ---------------------------------------------- per-tick logic

    async def tick(self, now: datetime | None = None) -> TickReport:
        """One pass: skip-checks, then evaluate every enabled, unpaused rule."""
        moment = now or datetime.now(UTC)
        report = TickReport()

        if is_halted(self.settings.halt_path):
            report.skipped_reason = "halt_flag_set"
            return report
        if self.settings.require_session_open and not is_session_open(moment):
            report.skipped_reason = "session_closed"
            return report

        for rule in self.settings.config.rules:
            if not rule.enabled:
                continue
            if rule.id in self._paused_rules:
                continue
            report.rules_evaluated += 1
            outcome = await self._evaluate_and_route(rule, moment)
            if outcome is not None:
                report.rules_fired += 1
                report.outcomes.append(outcome)
        return report

    async def _evaluate_and_route(
        self,
        rule: TradingRule,
        now: datetime,
    ) -> OrderOutcome | None:
        # Fetch a fresh quote (also accumulates a synthetic bar for indicators).
        quote = await get_quote(
            self.broker,
            access_token=self.access_token,
            app_key=self.app_key,
            app_secret=self.app_secret,
            symbol=rule.symbol,
            market=self.settings.market_quote,
        )
        timeframe = getattr(rule.trigger, "timeframe", "1d")
        store_synthetic_bar(
            self.conn,
            symbol=rule.symbol,
            timeframe=timeframe,
            bar_open_utc=now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            last_price_usd=quote.last_price_usd,
        )

        bars = (
            tuple(get_bars(self.conn, symbol=rule.symbol, timeframe=timeframe))
            if isinstance(rule.trigger, IndicatorTrigger)
            else ()
        )
        ctx = TriggerContext(
            now=now,
            current_price_usd=quote.last_price_usd,
            bars=bars,
            last_fired_at_utc=self._last_fired.get(rule.id),
        )
        if not evaluate(rule.trigger, ctx):
            return None

        outcome = await self.router.submit_order(
            rule=rule,
            quote_price_usd=quote.last_price_usd,
            total_capital_usd=self.settings.total_capital_usd,
            current_symbol_exposure_usd=self._symbol_exposure_usd(
                rule.symbol, quote.last_price_usd
            ),
            current_global_exposure_usd=self._global_exposure_usd(
                symbol=rule.symbol,
                quote_price=quote.last_price_usd,
            ),
        )
        self._last_fired[rule.id] = now
        return outcome

    # ---------------------------------------------- exposure helpers

    def _symbol_exposure_usd(self, symbol: str, current_price: Decimal) -> Decimal:
        pos = positions_mod.get_position(self.conn, symbol)
        return Decimal(pos.qty) * current_price if pos else Decimal("0")

    def _global_exposure_usd(
        self,
        *,
        symbol: str,
        quote_price: Decimal,
    ) -> Decimal:
        """Estimate total exposure using the live price for the symbol being
        traded and avg_cost for the rest. avg_cost is a conservative
        underestimate during uptrends but adequate for the v1 cap."""
        total = Decimal("0")
        for pos in positions_mod.get_all_positions(self.conn):
            price = quote_price if pos.symbol == symbol else pos.avg_cost_usd
            total += Decimal(pos.qty) * price
        return total

    # ---------------------------------------------- forever loop

    async def run_forever(self) -> None:
        try:
            while not self._stop_requested.is_set():
                await self.tick()
                try:
                    await asyncio.wait_for(
                        self._stop_requested.wait(),
                        timeout=self.settings.tick_interval_seconds,
                    )
                except TimeoutError:
                    continue
        finally:
            self.close()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover  — close is best-effort.
            logger.warning("error closing db connection", exc_info=True)


# ---------------------------------------------- module-level helpers


def preflight_stage_uniqueness(rules: list[TradingRule]) -> tuple[bool, list[Any]]:
    """Convenience wrapper around verify_stage_uniqueness for the CLI."""
    decisions = verify_stage_uniqueness(rules)
    return all(d.allow for d in decisions), decisions
