"""라이브 캐너리 → 풀라이브 승격 준비 평가 (스펙 026) — read-only.

라이브 audit_log 에서 헌법 VI 합격 입력을 측정해 promotion.gate.evaluate_promotion_readiness
에 넘긴다:
  - 라이브 기간(가장 이른 라이브 체결 → now, 일 단위)
  - 청산 거래 수 / 최대 낙폭 / 총수익률 (스펙 011 성과 엔진)
  - 서킷브레이커 트립 / 정합성 불일치 이력 (감사 조회)

어떤 row 도 수정하지 않는다(SELECT 만).

주의(헌법 IX.B-2): 이건 헌법 VI(라이브 캐너리 트랙레코드) 게이트의 평가다. **실제
풀라이브 승격**은 여기에 더해 스펙 007 하드닝 캐너리(다중 지표·충격·퍼즈, ≥30/45
거래일)도 통과해야 한다(production-deploy 게이트). 이 모듈은 VI 절반만 측정한다.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.config.caps import SizingCaps
from auto_invest.performance.engine import _fmt_ts, build_performance_report, read_fills
from auto_invest.promotion.gate import PromotionReadiness, evaluate_promotion_readiness

_EPOCH0 = datetime(2000, 1, 1, tzinfo=UTC)


def _count_event(
    conn: sqlite3.Connection, event_type: str, since: datetime, until: datetime
) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM audit_log "
        "WHERE event_type = ? AND ts_utc >= ? AND ts_utc <= ?",
        (event_type, _fmt_ts(since), _fmt_ts(until)),
    ).fetchone()
    return int(row[0]) if row else 0


def _parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def compute_readiness(
    conn: sqlite3.Connection,
    *,
    caps: SizingCaps,
    starting_capital: Decimal,
    mode: str = "live",
    now: datetime | None = None,
    min_closed_trades: int = 1,
) -> PromotionReadiness:
    """라이브 audit_log 를 읽어 승격 준비 여부를 평가한다(헌법 VI 절반)."""
    now = now or datetime.now(UTC)
    fills = read_fills(conn, mode=mode, since=_EPOCH0, until=now)

    # 서킷브레이커·정합성 이력은 트랙레코드 유무와 무관하게 전 기간을 본다.
    breaker = _count_event(conn, "CIRCUIT_BREAKER_TRIPPED", _EPOCH0, now) > 0
    recon = _count_event(conn, "RECONCILIATION_MISMATCH", _EPOCH0, now) > 0

    if not fills:
        # 라이브 체결 없음 → 트랙레코드 없음. 0일·0거래로 보수적 불합격.
        return evaluate_promotion_readiness(
            canary_days_elapsed=0,
            closed_trades=0,
            max_drawdown_pct=None,
            total_return_pct=None,
            breaker_tripped=breaker,
            reconciliation_mismatch=recon,
            min_duration_days=caps.canary_min_duration_days,
            acceptance_drawdown_pct=caps.canary_acceptance_drawdown_pct,
            min_closed_trades=min_closed_trades,
        )

    earliest_dt = min(_parse_ts(f.ts_utc) for f in fills)
    days_elapsed = (now - earliest_dt).days

    report = build_performance_report(
        conn, mode=mode, since=_EPOCH0, until=now, starting_capital=starting_capital
    )
    rm = report.risk  # RiskMetrics | None (청산 0건이면 None)
    closed = rm.closed_trades if rm is not None else 0
    max_dd = rm.max_drawdown_pct if rm is not None else None
    total_ret = rm.total_return_pct if rm is not None else None

    return evaluate_promotion_readiness(
        canary_days_elapsed=days_elapsed,
        closed_trades=closed,
        max_drawdown_pct=max_dd,
        total_return_pct=total_ret,
        breaker_tripped=breaker,
        reconciliation_mismatch=recon,
        min_duration_days=caps.canary_min_duration_days,
        acceptance_drawdown_pct=caps.canary_acceptance_drawdown_pct,
        min_closed_trades=min_closed_trades,
    )


__all__ = ["compute_readiness"]
