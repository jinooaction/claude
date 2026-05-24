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
    PaperRunStartedPayload,
    PaperRunStoppedPayload,
    RuleLoadPayload,
    SecretsLoadedPayload,
    WorkerStartedPayload,
    WorkerStoppedPayload,
)
from auto_invest.reconciliation.runner import (
    ReconciliationOutcome,
    run_reconciliation,
)
from auto_invest.strategy.canary import restore_pause_status
from auto_invest.strategy.triggers import TriggerContext, evaluate
from auto_invest.worker.halt import is_halted
from auto_invest.worker.schedule import is_session_open

logger = logging.getLogger(__name__)


def _utcnow_iso_ms_for_payload() -> str:
    """페이로드 timestamp용 — audit_log.ts_utc와 같은 ISO8601 ms-precision."""
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


_PAPER_STOP_REASONS = {"normal_shutdown", "signal_received", "mutex_conflict", "crash"}


def _normalize_paper_stop_reason(reason: str) -> str:
    """live record_stop은 임의 문자열을 받지만 paper 페이로드는 enum-only.

    인식 못 한 사유는 보수적으로 'crash'로 매핑한다 (best-effort audit).
    """
    return reason if reason in _PAPER_STOP_REASONS else "crash"


@dataclass
class WorkerSettings:
    """Runtime configuration for one Worker instance.

    spec 009: `paper_mode=True`면 데몬이 paper-trading 모드로 동작한다 —
    quote는 실제 KIS에서 받지만 broker 주문 호출은 OrderRouter의 단일
    차단 지점에서 시뮬 체결로 분기된다 (FR-004).
    """

    config: LoadedConfig
    db_path: Path
    halt_path: Path
    config_path: Path
    total_capital_usd: Decimal
    market_quote: str = "NAS"
    market_order: str = "NASD"
    tick_interval_seconds: float = 1.0
    require_session_open: bool = True
    paper_mode: bool = False
    # paper-mode일 때 PAPER_RUN_STARTED 페이로드의 ruleset_sha256 필드에 들어감.
    # paper-run CLI(cli.py)가 룰 파일 바이트의 SHA-256으로 계산해 주입한다.
    # live-mode에서는 사용되지 않음.
    ruleset_sha256: str | None = None


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
        judgment_runner: Any | None = None,
    ) -> None:
        self.settings = settings
        self.broker = broker
        self.access_token = access_token
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no
        # Spec 004: optional volatility judgment runner. None(기본)이면 v1 동작
        # — 판단 지점 비활성, 거래 루프는 LLM 을 전혀 부르지 않는다.
        self.judgment_runner = judgment_runner

        self.conn = db.get_connection(settings.db_path)
        db.migrate(self.conn)

        self._stop_requested = asyncio.Event()
        self._last_fired: dict[str, datetime] = {}
        self._paused_rules: set[str] = {
            r.id for r in settings.config.rules if restore_pause_status(self.conn, r.id)
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
            paper_mode=settings.paper_mode,
        )

    # ---------------------------------------------- lifecycle audit

    def record_start(self, *, secret_keys: Iterable[str]) -> None:
        audit.append(
            self.conn,
            SecretsLoadedPayload(keys=sorted(secret_keys)),
        )
        if self.settings.paper_mode:
            import socket

            started_at = _utcnow_iso_ms_for_payload()
            ruleset_sha = self.settings.ruleset_sha256 or ("0" * 64)
            session_id = audit.append(
                self.conn,
                PaperRunStartedPayload(
                    pid=os.getpid(),
                    config_path=str(self.settings.config_path),
                    ruleset_sha256=ruleset_sha,
                    started_at_utc=started_at,
                    host=socket.gethostname(),
                ),
            )
            # OrderRouter가 후속 ORDER_PAPER_FILLED row를 이 세션에 묶을 수 있도록
            # paper_session_id를 즉시 갱신한다.
            self.router.paper_session_id = session_id
        else:
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
        if self.settings.paper_mode:
            audit.append(
                self.conn,
                PaperRunStoppedPayload(
                    reason=_normalize_paper_stop_reason(reason),
                    stopped_at_utc=_utcnow_iso_ms_for_payload(),
                    session_started_event_id=self.router.paper_session_id or 0,
                ),
            )
        else:
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

        # Spec 004: 변동성 판단 지점도 최근 바가 필요하므로 judgment 활성 룰에도
        # 바를 가져온다(IndicatorTrigger 외).
        _needs_bars = isinstance(rule.trigger, IndicatorTrigger) or (
            self.judgment_runner is not None
            and rule.judgment is not None
            and rule.judgment.enabled
        )
        bars = (
            tuple(get_bars(self.conn, symbol=rule.symbol, timeframe=timeframe))
            if _needs_bars
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

        # Spec 004: trigger 발화 후 주문 라우팅 직전에 변동성 판단 지점을 호출.
        # runner 가 없거나(=v1) 판단 지점이 비활성/폴백이면 advisory 는 None 이고
        # submit_order 는 v1 그대로 동작한다 — 거래는 절대 막히지 않는다(SC-001).
        volatility_advisory = None
        judgment_correlation_id = None
        if self.judgment_runner is not None:
            volatility_advisory, judgment_correlation_id = (
                await self.judgment_runner.assess(
                    rule, bars, current_price=quote.last_price_usd
                )
            )

        outcome = await self.router.submit_order(
            rule=rule,
            quote_price_usd=quote.last_price_usd,
            quote_ask_usd=quote.ask_usd,
            quote_bid_usd=quote.bid_usd,
            total_capital_usd=self.settings.total_capital_usd,
            current_symbol_exposure_usd=self._symbol_exposure_usd(
                rule.symbol, quote.last_price_usd
            ),
            current_global_exposure_usd=self._global_exposure_usd(
                symbol=rule.symbol,
                quote_price=quote.last_price_usd,
            ),
            volatility_advisory=volatility_advisory,
            judgment_correlation_id=judgment_correlation_id,
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

    # ---------------------------------------------- reconciliation

    async def reconcile_now(self) -> ReconciliationOutcome:
        """Run reconciliation immediately. Used by tests and the
        CLI's `reconcile` subcommand; the scheduled session-close
        path uses the same entrypoint."""
        return await run_reconciliation(
            self.conn,
            self.broker,
            access_token=self.access_token,
            app_key=self.app_key,
            app_secret=self.app_secret,
            account=self.account_no,
            halt_path=self.settings.halt_path,
            market=self.settings.market_order,
        )

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
