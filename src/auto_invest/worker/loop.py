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
import sqlite3
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
from auto_invest.execution.fill_sync import sync_fills
from auto_invest.execution.order_router import (
    OrderOutcome,
    OrderRouter,
    verify_stage_uniqueness,
)
from auto_invest.market_data.feed import store_synthetic_bar
from auto_invest.market_data.store import get_bars, get_latest_bar
from auto_invest.persistence import audit, db
from auto_invest.persistence import positions as positions_mod
from auto_invest.persistence.audit import (
    CircuitBreakerTrippedPayload,
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
from auto_invest.risk.circuit_breaker import BreakerDecision, evaluate_from_audit
from auto_invest.strategy.canary import restore_pause_status
from auto_invest.strategy.sizing import build_sizing_groups
from auto_invest.strategy.triggers import TriggerContext, evaluate
from auto_invest.worker.halt import is_halted, set_halt
from auto_invest.worker.schedule import is_session_open

logger = logging.getLogger(__name__)


def _utcnow_iso_ms_for_payload() -> str:
    """페이로드 timestamp용 — audit_log.ts_utc와 같은 ISO8601 ms-precision."""
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


_PAPER_STOP_REASONS = {"normal_shutdown", "signal_received", "mutex_conflict", "crash"}

# Spec 014: 손실 서킷 브레이커 재평가 최소 간격(초). 1Hz 틱에서 매 틱 전체 감사
# 로그를 다시 읽지 않도록 평가를 묶는다. 첫 틱은 무조건 평가한다(_last_breaker_eval_at
# 가 None). 손실 반응 지연이 수 초인 것은 안전상 충분하다.
_BREAKER_EVAL_GAP_SECONDS = 5.0

# Spec 015: 라이브 체결 동기화 재폴링 최소 간격(초). 1Hz 틱마다 브로커 체결 조회를
# 날리지 않도록 묶는다. 첫 평가는 무조건 수행(_last_fill_sync_at 가 None).
_FILL_SYNC_GAP_SECONDS = 5.0


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
        # Spec 014: 브레이커 재평가 cadence 추적. None = 아직 평가 안 함(첫 틱에 평가).
        self._last_breaker_eval_at: datetime | None = None
        # Spec 015: 체결 동기화 cadence 추적. None = 아직 안 함(첫 기회에 동기화).
        self._last_fill_sync_at: datetime | None = None
        # Spec 001 T050: 장 마감 정합성 트리거 상태. 세션이 열려 있는 틱에서 True 가
        # 되고, 열림→닫힘으로 바뀌는 첫 틱에 정합성을 1회 실행한다(startup 이 닫힘이면
        # 트리거 안 함 — 전이가 아니라 초기 상태이므로).
        self._session_was_open: bool = False
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
            # Spec 017 slice 2b: inverse-vol risk-parity groups from the rule set.
            sizing_groups=build_sizing_groups(settings.config.rules),
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
        # 종료 경로의 best-effort 감사. systemd SIGTERM 순서상 DB 연결이 이미 닫혔을 수
        # 있는데(예: `systemctl restart`), 그 경우 audit.append 가 sqlite3.ProgrammingError
        # ("Cannot operate on a closed database")로 시끄러운 트레이스백을 남기고 워커를
        # 비정상 종료(exit 1)시킨다. WORKER_STOPPED 는 best-effort 이고 다음 시작의
        # WORKER_STARTED 가 세션 경계를 표시하므로, 닫힌 DB면 조용히 건너뛴다(포렌식 손실 없음).
        try:
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
        except sqlite3.Error as exc:
            logger.warning("record_stop: 종료 감사 생략(DB 닫힘 추정): %s", exc)

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

        # Spec 001 T050(완성): 장 마감 정합성. require_session_open 라이브 워커에서
        # 세션이 열림→닫힘으로 바뀌는 첫 틱에 로컬 보유를 브로커 잔고와 1회 대조한다
        # (불일치면 halt 로 다음 세션 거래를 차단 — 조용한 상태 드리프트 방지, US2).
        # 한 번의 닫힘 구간에 정확히 1회만 실행된다: 트리거 직후 _session_was_open 이
        # False 가 되어 같은 닫힘 구간의 이후 틱은 전이 조건에 걸리지 않는다. paper 는
        # 가상 보유라 실계좌와 대조하면 오탐이므로 호출 안 함. 오류는 격리(거래 무중단).
        session_open = is_session_open(moment)
        if (
            self.settings.require_session_open
            and not self.settings.paper_mode
            and self._session_was_open
            and not session_open
        ):
            await self._reconcile_at_close()
        self._session_was_open = session_open

        if self.settings.require_session_open and not session_open:
            report.skipped_reason = "session_closed"
            return report

        # Spec 014: 손실 서킷 브레이커 — halt/세션 점검 이후. 트립이면 스스로 halt 를
        # 세우고 감사 row 를 남긴 뒤 이 틱은 새 주문 없이 끝낸다. halt 가 선점하므로
        # 다음 틱부터는 위 halt 점검에 걸려 중복 트립이 발생하지 않는다(멱등).
        if self._should_eval_breaker(moment):
            self._last_breaker_eval_at = moment
            decision = self._check_circuit_breaker(moment)
            if decision is not None and decision.tripped:
                self._trip_circuit_breaker(decision, moment)
                report.skipped_reason = "circuit_breaker_tripped"
                return report

        # Spec 015: 라이브 체결 동기화 — 접수된 주문의 실제 체결을 장부에 반영한다.
        # 라이브 모드 전용(paper 는 orders row 가 없어 호출 안 함). 오류는 격리되어
        # 거래 루프를 멈추지 않는다. 열린 주문이 0건이면 sync_fills 가 브로커를
        # 호출하지 않는다(불필요 API 절약).
        if self._should_sync_fills(moment):
            self._last_fill_sync_at = moment
            await self._sync_open_order_fills(moment)

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

    # ---------------------------------------------- fill sync (spec 015)

    def _should_sync_fills(self, now: datetime) -> bool:
        """체결 동기화를 이번 틱에 할지. paper 모드면 안 함, 아니면 cadence 적용."""
        if self.settings.paper_mode:
            return False
        last = self._last_fill_sync_at
        if last is None:
            return True
        return (now - last).total_seconds() >= _FILL_SYNC_GAP_SECONDS

    async def _sync_open_order_fills(self, now: datetime) -> None:
        """라이브 열린 주문의 체결을 브로커에서 당겨와 장부에 반영(읽기-기반 적재).

        sync_fills 가 모든 예외를 격리하므로 여기서 추가 try 는 불필요하지만,
        방어적으로 한 번 더 감싸 어떤 경우에도 틱이 깨지지 않게 한다(SC-005)."""
        try:
            await sync_fills(
                self.conn,
                self.broker,
                access_token=self.access_token,
                app_key=self.app_key,
                app_secret=self.app_secret,
                account=self.account_no,
                market=self.settings.market_order,
                now=now,
            )
        except Exception:  # pragma: no cover — 이중 안전망(거래 무중단).
            logger.warning("fill sync raised unexpectedly", exc_info=True)

    # ---------------------------------------------- circuit breaker (spec 014)

    def _should_eval_breaker(self, now: datetime) -> bool:
        """브레이커를 이번 틱에 평가할지. 비활성이면 False, 아니면 cadence 적용."""
        if not self.settings.config.caps.circuit_breaker_enabled:
            return False
        last = self._last_breaker_eval_at
        if last is None:
            return True
        return (now - last).total_seconds() >= _BREAKER_EVAL_GAP_SECONDS

    def _assemble_marks(self) -> dict[str, Decimal]:
        """보유 종목별 최근 저장 바의 종가를 미실현 손익 시세로 조립(best-effort).

        룰에서 종목→timeframe 매핑을 만든다(워커가 그 timeframe 으로 합성 바를
        저장함). 바가 없는 종목은 마크 누락 → 미실현 0 으로 보수 처리된다.
        """
        tf_by_symbol: dict[str, str] = {}
        for rule in self.settings.config.rules:
            tf_by_symbol.setdefault(
                rule.symbol, getattr(rule.trigger, "timeframe", "1d")
            )
        marks: dict[str, Decimal] = {}
        for pos in positions_mod.get_all_positions(self.conn):
            tf = tf_by_symbol.get(pos.symbol, "1d")
            bar = get_latest_bar(self.conn, symbol=pos.symbol, timeframe=tf)
            if bar is not None:
                marks[pos.symbol] = bar.close_usd
        return marks

    def _check_circuit_breaker(self, now: datetime) -> BreakerDecision | None:
        """현재 손익을 평가해 브레이커 결정을 반환(read-only). 비활성이면 None."""
        caps = self.settings.config.caps
        if not caps.circuit_breaker_enabled:
            return None
        mode = "paper" if self.settings.paper_mode else "live"
        return evaluate_from_audit(
            self.conn,
            mode=mode,
            starting_capital=self.settings.total_capital_usd,
            caps=caps,
            now=now,
            marks=self._assemble_marks(),
        )

    def _trip_circuit_breaker(self, decision: BreakerDecision, now: datetime) -> None:
        """트립 부수효과: halt 플래그 세팅 + CIRCUIT_BREAKER_TRIPPED 감사 append.

        주문/청산은 하지 않는다 — 유일한 효과는 새 주문 차단이다(FR-007).
        """
        set_halt(self.settings.halt_path, f"circuit_breaker: {decision.reason}")
        md = decision.metadata
        audit.append(
            self.conn,
            CircuitBreakerTrippedPayload(
                mode="paper" if self.settings.paper_mode else "live",
                tripped_at_utc=_utcnow_iso_ms_for_payload(),
                starting_capital_usd=md.get(
                    "starting_capital_usd", str(self.settings.total_capital_usd)
                ),
                realized_pnl_today_usd=md.get("realized_pnl_today_usd", "0"),
                current_equity_usd=md.get("current_equity_usd", "0"),
                breached=decision.breached,
                daily_loss_limit_pct=md.get("daily_loss_limit_pct", ""),
                max_total_drawdown_pct=md.get("max_total_drawdown_pct", ""),
                reason=decision.reason,
            ),
        )
        logger.warning("circuit breaker tripped: %s", decision.reason)

    # ---------------------------------------------- reconciliation

    async def _reconcile_at_close(self) -> None:
        """장 마감 전이에서 1회 정합성 검증(읽기-기반 대조 + 불일치 halt).

        `reconcile_now` → `run_reconciliation` 이 브로커 예외를 INCONCLUSIVE 로
        격리하므로 정상 경로에서 예외가 올라오지 않지만, DB 오류 등 어떤 경우에도
        틱이 깨지지 않도록 방어적으로 한 번 더 감싼다(SC: 거래 무중단)."""
        try:
            outcome = await self.reconcile_now()
            logger.info("session-close reconciliation: %s", outcome.state)
        except Exception:  # pragma: no cover — 이중 안전망(거래 무중단).
            logger.warning("session-close reconciliation raised", exc_info=True)

    async def reconcile_now(self) -> ReconciliationOutcome:
        """Run reconciliation immediately. Shared entrypoint for the
        `auto-invest reconcile` CLI (manual runs) and the automatic
        session-close trigger (`_reconcile_at_close`, spec 001 T050)."""
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
