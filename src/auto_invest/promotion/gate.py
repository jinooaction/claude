"""캐너리 → 풀라이브 승격 게이트 (스펙 026) — 순수·결정론적 판단.

헌법 VI: "풀라이브 승격은 캐너리가 사전 선언된 합격 지표를 만족한 뒤에만." 이 모듈은
라이브 캐너리의 측정 성과(스펙 011)와 설정된 합격 임계값(caps)을 받아 **승격 준비
여부**를 결정한다. 실제 스테이지 전환·자본 상향은 이 게이트 뒤에서만 일어난다.

NON-KERNEL. 게이트는 승격을 **막기만** 한다(노출을 늘리는 쪽으로 결코 통과시키지
않음). 보수적: 측정 불가(None) 지표가 하나라도 있으면 불합격.

합격 조건(전부 만족해야 ready=True):
  1. 최소 라이브 기간(헌법 VI): canary_days_elapsed ≥ min_duration_days.
  2. 실제 트랙레코드: closed_trades ≥ min_closed_trades(체결·청산이 실제로 있었음).
  3. 최대 낙폭 ≤ 허용 낙폭(acceptance_drawdown_pct).
  4. 총수익률 ≥ 0(캐너리 기간 순손실이면 승격 안 함).
  5. 서킷브레이커 트립 이력 없음(헌법 캐너리 기간 중).
  6. 정합성 불일치 이력 없음.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PromotionReadiness:
    """승격 준비 판단 결과. ready=True 면 모든 합격 조건 충족."""

    ready: bool
    reasons: list[str]  # 사람이 읽는 사유(각 조건의 충족/미달)
    checks: dict[str, bool]  # 조건명 → 통과 여부

    def to_json_dict(self) -> dict:
        return {"ready": self.ready, "checks": self.checks, "reasons": self.reasons}


def evaluate_promotion_readiness(
    *,
    canary_days_elapsed: int,
    closed_trades: int,
    max_drawdown_pct: Decimal | None,
    total_return_pct: Decimal | None,
    breaker_tripped: bool,
    reconciliation_mismatch: bool,
    min_duration_days: int,
    acceptance_drawdown_pct: Decimal,
    min_closed_trades: int = 1,
) -> PromotionReadiness:
    """라이브 캐너리가 풀라이브로 승격할 준비가 됐는지 결정한다(헌법 VI).

    모든 입력은 호출자가 라이브 audit_log(스펙 011 성과 엔진 + 감사 조회)에서
    측정해 넘긴다. 이 함수 자체는 부수효과가 없다.
    """
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    # 1) 최소 라이브 기간 (헌법 VI).
    dur_ok = canary_days_elapsed >= min_duration_days
    checks["min_duration"] = dur_ok
    reasons.append(
        f"라이브 기간 {canary_days_elapsed}/{min_duration_days}일 "
        f"{'충족' if dur_ok else '미달'}"
    )

    # 2) 실제 트랙레코드(체결·청산이 있었는가).
    trades_ok = closed_trades >= min_closed_trades
    checks["track_record"] = trades_ok
    reasons.append(
        f"청산 거래 {closed_trades}건(최소 {min_closed_trades}) "
        f"{'충족' if trades_ok else '미달'}"
    )

    # 3) 최대 낙폭 ≤ 허용. 측정 불가면 불합격(보수적).
    if max_drawdown_pct is None:
        dd_ok = False
        reasons.append("최대 낙폭 측정 불가(None) → 불합격(보수적)")
    else:
        dd_ok = max_drawdown_pct <= acceptance_drawdown_pct
        reasons.append(
            f"최대 낙폭 {max_drawdown_pct}% ≤ 허용 {acceptance_drawdown_pct}% "
            f"{'충족' if dd_ok else '초과 → 불합격'}"
        )
    checks["drawdown_within_acceptance"] = dd_ok

    # 4) 총수익률 ≥ 0. 측정 불가면 불합격(보수적).
    if total_return_pct is None:
        ret_ok = False
        reasons.append("총수익률 측정 불가(None) → 불합격(보수적)")
    else:
        ret_ok = total_return_pct >= 0
        reasons.append(
            f"총수익률 {total_return_pct}% {'≥0 충족' if ret_ok else '<0 순손실 → 불합격'}"
        )
    checks["non_negative_return"] = ret_ok

    # 5) 서킷브레이커 트립 이력 없음.
    cb_ok = not breaker_tripped
    checks["circuit_breaker_clear"] = cb_ok
    reasons.append(
        "서킷브레이커 " + ("트립 이력 없음 → 충족" if cb_ok else "트립 이력 있음 → 불합격")
    )

    # 6) 정합성 불일치 이력 없음.
    rec_ok = not reconciliation_mismatch
    checks["reconciliation_clear"] = rec_ok
    reasons.append(
        "정합성 " + ("불일치 없음 → 충족" if rec_ok else "불일치 이력 있음 → 불합격")
    )

    ready = all(checks.values())
    return PromotionReadiness(ready=ready, reasons=reasons, checks=checks)


__all__ = ["PromotionReadiness", "evaluate_promotion_readiness"]
