"""백테스트 앵커드 엣지 판정 — 깊은 walk-forward 표본외(OOS) 증거 + 짧은 forward 지속성 확인.

운영자 지적(2026-06-15): 전략 규칙이 이미 깊은 OOS(스펙 047 등 150년)로 검증됐는데,
forward 판정이 그걸 무시하고 *일별 20일* 로 엣지를 처음부터 재발견하려는 건 비효율이다.
신규 전략이라도 규칙 자체가 깊은 표본외로 검증돼 있으면 라이브에서 *살아있는지* 만 짧게
확인하면 된다.

세계 최고 수준 설계:
  - 엣지의 증거 = 깊은 walk-forward OOS 백테스트(params 는 이전 fold 에서만 적합 = 진짜
    표본외 → in-sample 과장 아님, HANDOFF-039 교훈 준수).
  - forward 페이퍼의 역할 = 그 검증된 엣지가 라이브 파이프라인에서 *지속* 하는지(레짐
    붕괴·구현 버그 없는지) 확인. 재발견(20일)이 아니라 지속 확인(5~10일)이라 훨씬 빠르다.

엄밀성(돈을 잃지 않게):
  - OOS 가 충분히 깊고(min_oos_obs) 유의해야(PSR/DSR ≥ 임계) 앵커로 인정. 약하면 NO_EDGE.
  - 다중검정(여러 설정 시도)은 DSR num_trials 가, 여러 트랙 선택은 교차-트랙 보정(스펙 053)이
    처벌 — 선택편향을 통계로 깎는다.
  - forward 지속성: 라이브 평균 일수익률이 OOS 평균보다 *유의하게 나쁘면*(z < −임계) NO_EDGE.
    아니면(검증된 엣지가 깨지지 않음) EDGE_CONFIRMED. 적은 forward 표본으로 *재발견* 하는 게
    아니라 *반증이 없음* 을 확인하는 것이라 표본이 적어도 정당하다(증거는 깊은 OOS 가 제공).
  - 보수적 fail-safe: OOS 부족/약함 또는 forward 부족이면 절대 EDGE 선언 안 함.

읽기 전용·순수·결정론. 주문 0·돈 0 이동. EDGE_CONFIRMED 는 자본 사다리(헌법 X.4)에 올릴
증거이지 자동 배포가 아니다. 이 모듈은 라이브 동작을 바꾸지 않는다(게이트 배선은 별도).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal

from auto_invest.backtest.significance import significance_summary

EDGE_CONFIRMED = "EDGE_CONFIRMED"
NO_EDGE = "NO_EDGE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# 앵커 인정 최소 OOS 관측(일). walk-forward 표본외가 이만큼은 깊어야 엣지를 신뢰.
DEFAULT_MIN_OOS_OBS = 60
# forward 지속성 확인 최소 관측(일). 재발견이 아니라 반증 확인이라 적어도 정당.
DEFAULT_MIN_FORWARD_OBS = 5
# forward 평균이 OOS 평균보다 이 z 이상 나쁘면 지속 실패(레짐 붕괴·버그) → NO_EDGE.
DEFAULT_CONSISTENCY_Z = Decimal("2.0")
DEFAULT_DSR_THRESHOLD = Decimal("0.95")


def _floats(returns: list[Decimal]) -> list[float]:
    return [float(r) for r in returns]


@dataclass(frozen=True)
class AnchoredVerdict:
    """백테스트 앵커드 판정 — 깊은 OOS 증거 + forward 지속성의 결합 결과."""

    verdict: str  # EDGE_CONFIRMED | NO_EDGE | INSUFFICIENT_DATA
    reason: str
    oos_n_obs: int
    oos_sharpe_annual: Decimal | None
    oos_significance: Decimal | None  # PSR(num_trials=1) 또는 DSR(>1) — 깊은 엣지 신뢰도
    forward_n_obs: int
    forward_mean_daily: Decimal | None
    oos_mean_daily: Decimal | None
    consistency_z: Decimal | None  # (forward 평균 − OOS 평균)/SE. 음수 클수록 라이브 악화
    dsr_threshold: Decimal
    num_trials: int

    SCHEMA_VERSION = "1.0"

    def to_json_dict(self) -> dict:
        def _s(v: Decimal | None) -> str | None:
            return None if v is None else str(v)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "method": "backtest_anchored",
            "verdict": self.verdict,
            "reason": self.reason,
            "oos_n_obs": self.oos_n_obs,
            "oos_sharpe_annual": _s(self.oos_sharpe_annual),
            "oos_significance": _s(self.oos_significance),
            "forward_n_obs": self.forward_n_obs,
            "forward_mean_daily": _s(self.forward_mean_daily),
            "oos_mean_daily": _s(self.oos_mean_daily),
            "consistency_z": _s(self.consistency_z),
            "dsr_threshold": str(self.dsr_threshold),
            "num_trials": self.num_trials,
        }


def _insufficient(
    reason: str, *, oos_n: int, fwd_n: int, num_trials: int, dsr_threshold: Decimal
) -> AnchoredVerdict:
    return AnchoredVerdict(
        verdict=INSUFFICIENT_DATA,
        reason=reason,
        oos_n_obs=oos_n,
        oos_sharpe_annual=None,
        oos_significance=None,
        forward_n_obs=fwd_n,
        forward_mean_daily=None,
        oos_mean_daily=None,
        consistency_z=None,
        dsr_threshold=dsr_threshold,
        num_trials=num_trials,
    )


def backtest_anchored_verdict(
    *,
    oos_returns: list[Decimal],
    forward_returns: list[Decimal],
    oos_edge_confirmed: bool = True,
    oos_rejection_reason: str | None = None,
    num_trials: int = 1,
    trial_sharpe_std_annual: Decimal | float | int | None = None,
    dsr_threshold: Decimal = DEFAULT_DSR_THRESHOLD,
    min_oos_obs: int = DEFAULT_MIN_OOS_OBS,
    min_forward_obs: int = DEFAULT_MIN_FORWARD_OBS,
    consistency_z: Decimal = DEFAULT_CONSISTENCY_Z,
) -> AnchoredVerdict:
    """깊은 OOS 일수익률 + 짧은 forward 일수익률 → 엣지 판정(순수·결정론·보수적).

    1. OOS 가 얕으면(< min_oos_obs) INSUFFICIENT — 앵커 불가.
    2. OOS walk-forward 가 벤치마크 대비 강건한 엣지를 못 세우면 NO_EDGE.
    3. OOS 유의성(PSR/DSR) < 임계 또는 샤프 ≤ 0 → NO_EDGE(백테스트가 엣지를 못 세움).
    4. forward 가 부족하면(< min_forward_obs) INSUFFICIENT — 지속 확인 불가.
    5. 지속성 z = (forward 평균 − OOS 평균)/(OOS 표준편차/√forward수). z < −consistency_z 면
       라이브가 유의하게 악화 → NO_EDGE. 아니면 EDGE_CONFIRMED(검증 엣지가 지속).
    """
    oos_n = len(oos_returns)
    fwd_n = len(forward_returns)

    if oos_n < min_oos_obs:
        return _insufficient(
            f"OOS 관측 {oos_n} < 최소 {min_oos_obs} — 깊은 표본외 증거 부족(앵커 불가).",
            oos_n=oos_n,
            fwd_n=fwd_n,
            num_trials=num_trials,
            dsr_threshold=dsr_threshold,
        )

    sig = significance_summary(
        oos_returns, num_trials=num_trials, trial_sharpe_std_annual=trial_sharpe_std_annual
    )
    if sig is None:
        return _insufficient(
            "OOS 유의성 계산 불가(관측<2 또는 분산 0).",
            oos_n=oos_n,
            fwd_n=fwd_n,
            num_trials=num_trials,
            dsr_threshold=dsr_threshold,
        )
    # 다중검정 보정: 여러 설정을 시도했으면(num_trials>1) DSR, 아니면 PSR.
    oos_signif = sig.dsr if (num_trials > 1 and sig.dsr is not None) else sig.psr
    oos_sharpe = sig.sharpe_annual
    oos_mean = Decimal(str(statistics.fmean(_floats(oos_returns))))

    if not oos_edge_confirmed:
        return AnchoredVerdict(
            verdict=NO_EDGE,
            reason=(
                "OOS walk-forward 엣지 미확정 — "
                f"{oos_rejection_reason or '벤치마크 대비 강건한 우위 없음'}"
            ),
            oos_n_obs=oos_n,
            oos_sharpe_annual=oos_sharpe,
            oos_significance=oos_signif,
            forward_n_obs=fwd_n,
            forward_mean_daily=None,
            oos_mean_daily=oos_mean,
            consistency_z=None,
            dsr_threshold=dsr_threshold,
            num_trials=num_trials,
        )

    if oos_signif is None or oos_signif < dsr_threshold or oos_sharpe <= 0:
        return AnchoredVerdict(
            verdict=NO_EDGE,
            reason=(
                f"OOS 엣지 미확정 — 유의성 {oos_signif} < {dsr_threshold} 또는 샤프 "
                f"{oos_sharpe} ≤ 0. 깊은 표본외에서도 우연과 구별 안 됨."
            ),
            oos_n_obs=oos_n,
            oos_sharpe_annual=oos_sharpe,
            oos_significance=oos_signif,
            forward_n_obs=fwd_n,
            forward_mean_daily=None,
            oos_mean_daily=oos_mean,
            consistency_z=None,
            dsr_threshold=dsr_threshold,
            num_trials=num_trials,
        )

    if fwd_n < min_forward_obs:
        return _insufficient(
            f"forward 관측 {fwd_n} < 최소 {min_forward_obs} — 라이브 지속 확인 부족.",
            oos_n=oos_n,
            fwd_n=fwd_n,
            num_trials=num_trials,
            dsr_threshold=dsr_threshold,
        )

    # 지속성 z-검정: forward 평균이 OOS 평균보다 유의하게 나쁜가(라이브 붕괴/버그).
    oos_std = statistics.stdev(_floats(oos_returns))  # 표본 표준편차(ddof=1)
    fwd_mean_f = statistics.fmean(_floats(forward_returns))
    fwd_mean = Decimal(str(fwd_mean_f))
    if oos_std <= 0.0:
        return AnchoredVerdict(
            verdict=NO_EDGE,
            reason="OOS 표준편차 0 — 수익률 변동이 없어 지속성 검정 불가(보수적 거부).",
            oos_n_obs=oos_n,
            oos_sharpe_annual=oos_sharpe,
            oos_significance=oos_signif,
            forward_n_obs=fwd_n,
            forward_mean_daily=fwd_mean,
            oos_mean_daily=oos_mean,
            consistency_z=None,
            dsr_threshold=dsr_threshold,
            num_trials=num_trials,
        )
    se = oos_std / math.sqrt(fwd_n)
    z = Decimal(str((fwd_mean_f - float(oos_mean)) / se))

    if z < -consistency_z:
        return AnchoredVerdict(
            verdict=NO_EDGE,
            reason=(
                f"라이브 지속 실패 — forward 평균 일수익 {fwd_mean} 이 OOS 평균 {oos_mean} "
                f"보다 유의하게 나쁨(z {z} < −{consistency_z}). 레짐 붕괴·구현 버그 의심."
            ),
            oos_n_obs=oos_n,
            oos_sharpe_annual=oos_sharpe,
            oos_significance=oos_signif,
            forward_n_obs=fwd_n,
            forward_mean_daily=fwd_mean,
            oos_mean_daily=oos_mean,
            consistency_z=z,
            dsr_threshold=dsr_threshold,
            num_trials=num_trials,
        )

    return AnchoredVerdict(
        verdict=EDGE_CONFIRMED,
        reason=(
            f"깊은 OOS 엣지(유의성 {oos_signif} ≥ {dsr_threshold}, 샤프 {oos_sharpe}, "
            f"관측 {oos_n}) + 라이브 지속 확인(forward {fwd_n}일, z {z} ≥ −{consistency_z}). "
            "검증된 엣지가 라이브에서 깨지지 않음."
        ),
        oos_n_obs=oos_n,
        oos_sharpe_annual=oos_sharpe,
        oos_significance=oos_signif,
        forward_n_obs=fwd_n,
        forward_mean_daily=fwd_mean,
        oos_mean_daily=oos_mean,
        consistency_z=z,
        dsr_threshold=dsr_threshold,
        num_trials=num_trials,
    )


def combine_edge_verdicts(
    standard: dict | None, anchored: dict | None
) -> dict:
    """표준 forward 판정과 백테스트 앵커드 판정의 원본 증거를 보존해 결합한다.

    연구 판정은 둘 중 하나가 확정이면 ``EDGE_CONFIRMED``로 남긴다. 자본 소비자는 경로별
    전체 교정을 별도로 요구하므로, 교정되지 않은 앵커드 확정만으로 노출이 늘지는 않는다.

    결합 규칙(순수·결정론·보수적 fail-safe):
      1. 앵커드 또는 표준이 EDGE_CONFIRMED → EDGE_CONFIRMED(source 로 어느 쪽인지 기록).
      2. 아니면 둘 중 하나라도 NO_EDGE → NO_EDGE(엣지 없음 증거 있음).
      3. 그 외(둘 다 미확정/입력 없음) → INSUFFICIENT_DATA(게이트는 무장 안 함 — 안전).
    입력이 None/파싱 불가여도 안전하게 흡수한다(누락 = 미확정으로 취급).

    반환: 소비자가 읽는 형태({"verdict", "n_obs", ...})에 source·원본 방법·근거를 덧붙인 dict.
    """
    s = standard if isinstance(standard, dict) else {}
    a = anchored if isinstance(anchored, dict) else {}
    s_v = s.get("verdict")
    a_v = a.get("verdict")

    if a_v == EDGE_CONFIRMED or s_v == EDGE_CONFIRMED:
        verdict = EDGE_CONFIRMED
        if a_v == EDGE_CONFIRMED and s_v == EDGE_CONFIRMED:
            source = "both"
        elif a_v == EDGE_CONFIRMED:
            source = "anchored"
        else:
            source = "standard"
    elif a_v == NO_EDGE or s_v == NO_EDGE:
        verdict = NO_EDGE
        source = "none"
    else:
        verdict = INSUFFICIENT_DATA
        source = "none"

    # 게이트가 읽는 n_obs: 확정원의 forward 관측(앵커드는 forward_n_obs, 표준은 n_obs).
    if source in ("anchored", "both"):
        n_obs = _int_or_none(a.get("forward_n_obs"))
    elif source == "standard":
        n_obs = _int_or_none(s.get("n_obs"))
    else:
        n_obs = _int_or_none(s.get("n_obs")) or _int_or_none(a.get("forward_n_obs"))

    return {
        "schema_version": "1.0",
        "method": "combined_edge",
        "verdict": verdict,
        "source": source,  # anchored | standard | both | none
        "n_obs": n_obs,
        "significance_method": (
            s.get("significance_method") if source in ("standard", "both") else None
        ),
        "standard_significance_method": s.get("significance_method"),
        "standard_psr_vs_benchmark": s.get("psr_vs_benchmark"),
        "standard_verdict": s_v,
        "anchored_verdict": a_v,
        "anchored_method": a.get("method"),
        "anchored_oos_n_obs": _int_or_none(a.get("oos_n_obs")),
        "anchored_significance": a.get("oos_significance"),
        "anchored_dsr_threshold": a.get("dsr_threshold"),
        "anchored_num_trials": _int_or_none(a.get("num_trials")),
        "reason": (
            f"유효 판정 {verdict} (출처={source}; 표준={s_v}, 앵커드={a_v}). "
            "연구 확정은 보존하되 자본 증거는 각 경로의 전체 교정을 따로 요구한다."
        ),
    }


def _int_or_none(v: object) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


__all__ = [
    "DEFAULT_CONSISTENCY_Z",
    "DEFAULT_DSR_THRESHOLD",
    "DEFAULT_MIN_FORWARD_OBS",
    "DEFAULT_MIN_OOS_OBS",
    "EDGE_CONFIRMED",
    "INSUFFICIENT_DATA",
    "NO_EDGE",
    "AnchoredVerdict",
    "backtest_anchored_verdict",
    "combine_edge_verdicts",
]
