"""Spec 014 — 라이브 손실 서킷 브레이커 (순수 평가 + 감사 기반 조립).

설계 원칙:
  - **순수 방어적**: 이 모듈은 트립 여부를 *판단만* 한다. halt 를 세우거나 감사
    row 를 쓰거나 주문을 내지 않는다 — 그 부수효과는 워커가 트립 시에만 수행한다.
  - **한 잣대(헌법 X)**: 손익은 스펙 011 성과 엔진(`performance/engine.py`)의 같은
    정의로 계산한다. 별도 손익 산식을 만들지 않는다.
  - **read-only**: `evaluate_from_audit` 는 audit_log 를 SELECT 만 한다.

비커널 모듈이다(K1 은 `risk/gates.py`·`risk/__init__.py`·`config/caps.py` 만 보호).
손실 *한도* 는 K1(`config/caps.py`)에 있어 튜너가 자동 완화 불가; 이 *평가 로직* 은
비커널이라 자유롭게 진화할 수 있다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.config.caps import SizingCaps
from auto_invest.performance.engine import (
    compute_performance,
    read_fills,
    realized_trades,
)

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class BreakerLimits:
    """caps 에서 파생된 브레이커 한도."""

    enabled: bool
    daily_loss_limit_pct: Decimal
    max_total_drawdown_pct: Decimal

    @classmethod
    def from_caps(cls, caps: SizingCaps) -> BreakerLimits:
        return cls(
            enabled=caps.circuit_breaker_enabled,
            daily_loss_limit_pct=caps.daily_loss_limit_pct,
            max_total_drawdown_pct=caps.max_total_drawdown_pct,
        )


@dataclass(frozen=True)
class BreakerDecision:
    """브레이커 한 번의 평가 결과. 순수 값."""

    tripped: bool
    breached: list[str]  # {"daily_loss", "total_drawdown"} 부분집합
    reason: str
    metadata: dict[str, str] = field(default_factory=dict)


def evaluate(
    *,
    starting_capital: Decimal,
    realized_pnl_today: Decimal,
    current_equity: Decimal,
    limits: BreakerLimits,
) -> BreakerDecision:
    """순수 결정론적 평가. 같은 입력 → 같은 결정. 부수효과 0.

    - 일일 손실: 오늘 실현 손익 ≤ -(daily_loss_limit_pct% × 시작 자본) → 트립.
    - 전체 낙폭: 현재 자산 ≤ 시작 자본 × (1 − max_total_drawdown_pct/100) → 트립.

    시작 자본이 0 이하면 비율 기준을 계산할 수 없으므로 두 점검 모두 비활성
    (트립 안 함) — 자본 미설정 워커를 오트립시키지 않는다.
    """
    metadata: dict[str, str] = {
        "enabled": str(limits.enabled),
        "starting_capital_usd": str(starting_capital),
        "realized_pnl_today_usd": str(realized_pnl_today),
        "current_equity_usd": str(current_equity),
        "daily_loss_limit_pct": str(limits.daily_loss_limit_pct),
        "max_total_drawdown_pct": str(limits.max_total_drawdown_pct),
    }

    if not limits.enabled:
        return BreakerDecision(
            tripped=False,
            breached=[],
            reason="circuit breaker disabled",
            metadata=metadata,
        )
    if starting_capital <= 0:
        return BreakerDecision(
            tripped=False,
            breached=[],
            reason="starting capital <= 0; loss limits not evaluable",
            metadata=metadata,
        )

    breached: list[str] = []

    daily_loss_limit_usd = -(starting_capital * limits.daily_loss_limit_pct / Decimal("100"))
    metadata["daily_loss_limit_usd"] = str(daily_loss_limit_usd)
    if realized_pnl_today <= daily_loss_limit_usd:
        breached.append("daily_loss")

    drawdown_floor_usd = starting_capital * (
        Decimal("1") - limits.max_total_drawdown_pct / Decimal("100")
    )
    metadata["drawdown_floor_usd"] = str(drawdown_floor_usd)
    if current_equity <= drawdown_floor_usd:
        breached.append("total_drawdown")

    if not breached:
        return BreakerDecision(
            tripped=False,
            breached=[],
            reason="within loss limits",
            metadata=metadata,
        )

    parts: list[str] = []
    if "daily_loss" in breached:
        parts.append(
            f"daily realized loss ${realized_pnl_today} <= limit "
            f"${daily_loss_limit_usd} ({limits.daily_loss_limit_pct}% of capital)"
        )
    if "total_drawdown" in breached:
        parts.append(
            f"equity ${current_equity} <= floor ${drawdown_floor_usd} "
            f"({limits.max_total_drawdown_pct}% max drawdown)"
        )
    return BreakerDecision(
        tripped=True,
        breached=breached,
        reason="circuit breaker tripped: " + "; ".join(parts),
        metadata=metadata,
    )


def evaluate_from_audit(
    conn: sqlite3.Connection,
    *,
    mode: str,
    starting_capital: Decimal,
    caps: SizingCaps,
    now: datetime,
    marks: dict[str, Decimal] | None = None,
) -> BreakerDecision:
    """audit_log 체결 + 시세(marks)로 손익을 재구성해 브레이커를 평가한다 (read-only).

    - 오늘 실현 손익: 스펙 011 `realized_trades` 에서 청산일이 `now` 의 UTC 날짜인
      거래의 손익 합. 시작 자본 이전 매수의 원가 기준도 정확히 반영된다(전체 체결
      시퀀스로 재구성).
    - 현재 자산: 시작 자본 + 전체 실현 손익 + 현재 미실현(marks 기준). 시세 없는
      보유 종목은 미실현 0 으로 보수 처리(과대 손실로 오트립하지 않음).
    """
    marks = marks or {}
    fills = read_fills(conn, mode=mode, since=_EPOCH, until=now)
    report = compute_performance(
        fills,
        marks,
        mode=mode,
        since=_EPOCH,
        until=now,
        starting_capital=starting_capital,
    )
    trades = realized_trades(fills)
    today = now.astimezone(UTC).strftime("%Y-%m-%d")
    realized_today = sum(
        (t.pnl_usd for t in trades if t.date == today), Decimal("0")
    )
    current_equity = starting_capital + report.total_pnl_usd

    decision = evaluate(
        starting_capital=starting_capital,
        realized_pnl_today=realized_today,
        current_equity=current_equity,
        limits=BreakerLimits.from_caps(caps),
    )
    if report.unmarked_symbols:
        # 시세 결측 종목은 미실현 0 으로 처리됐다는 사실을 forensic 메타데이터에 남긴다.
        decision.metadata["unmarked_symbols"] = ",".join(report.unmarked_symbols)
    return decision
