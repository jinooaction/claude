"""스펙 055 — 자율 전략 진화: 토너먼트 챔피언 자동 재지정 결정(순수·읽기 전용 판정).

운영자 방향(2026-06-16): "자율 전략 진화 폐회로 — 더 나은 전략을 시스템이 스스로 라이브로
교체. 완전 자율 + 5중 안전장치." 추세추종 6트랙 토너먼트에서 도전자가 검증된 현 라이브
전략(incumbent)을 강건하게 앞서면, 사람 개입 없이 라이브로 교체한다 — 단 다섯 관문을 *전부*
통과할 때만. 헌법 X.4 개정으로 전략 재지정을 운영자 단건 결정에서 이 증거 게이트 공식으로
위임한다(자본 사다리 050 과 같은 자세).

입력 품질 게이트 + 5중 안전 게이트(전부 통과해야 REASSIGN — 하나라도 불충족이면 HOLD/WAIT,
절대 재지정 아님):

  ⓪ 후보 관측 품질: forward 토너먼트 leaderboard.json 의 observation_health 가 OK.
     BLOCKED/DEGRADED/알 수 없는 값이면 재지정 판단을 진행하지 않는다.
  ① 엣지 확정: 도전자가 forward EDGE_CONFIRMED.
  ② 다중검정 보정: 여러 트랙 동시검정의 '운 좋은 우승' 배제(본페로니, champion_multiplicity_
     robust). 6트랙을 동시에 돌린 데서 우연히 1등 한 트랙으로는 재지정하지 않는다.
  ③ 사과 대 사과: 도전자가 현 라이브 검증 트랙(incumbent)을 *둘 다 비교 가능* 상태에서 앞섬.
     (forward_tournament 가 challenger_key 를 set 할 때 ①③ 을 함께 보장한다.)
  ④ 소액 실거래 검증: 하드닝 캐너리(스펙 007, 과거 리플레이+충격+퍼즈)를 PASS.
  ⑤ 교체 후 재검증: 재지정 시 자본 사다리를 rung 0 으로 리셋 → 새 전략을 forward 재검증부터
     25%·50%·100% 로 자율 재승격(capital_ladder, 실행 단계). 검증 안 한 전략에 자본이 즉시
     실리지 않게 하는 안전장치다.

이 모듈은 **결정만** 한다 — 주문 0건, 돈 0 이동, 네트워크 0. 결정의 실행(라이브 설정 교체 +
사다리 리셋 센티넬)은 워크플로가, 실주문은 시장시간 스케줄이 한다. 보수적 fail-safe:
게이트 입력이 불명/미충족이면 현 전략 유지(HOLD) 또는 캐너리 대기(WAIT_CANARY).

비위임 불변(헌법 I 캡·II 화이트리스트·IV 감사·VI 단계 승격·VIII.A 장중 배포 금지·스펙 014
서킷 브레이커)은 그대로다. 재지정은 *어떤 전략을 라이브로 쓰는가*만 바꾼다 — 자본 규모는
여전히 자본 사다리가, 장중 방어는 여전히 서킷 브레이커가 가른다.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from auto_invest.analytics.forward_tournament import (
    OBS_HEALTH_BLOCKED,
    OBS_HEALTH_DEGRADED,
    OBS_HEALTH_OK,
    TournamentLeaderboard,
)

# 하드닝 캐너리(스펙 007) 합격 라벨 — 이 값일 때만 ④ 게이트 통과.
CANARY_PASS = "PASS"

# ---- 결정 라벨 ----
ACTION_REASSIGN = "REASSIGN"  # 5중 게이트 전부 통과 → 챔피언으로 교체 + 사다리 rung0 리셋
ACTION_WAIT_CANARY = "WAIT_CANARY"  # 도전자 확정(①②③) → 하드닝 캐너리 검증 필요/진행
ACTION_HOLD = "HOLD"  # 도전자 없음 또는 ①②③ 미충족 → 현 전략 유지
ACTION_DISABLED = "DISABLED"  # 킬스위치


@dataclass(frozen=True)
class ReassignDecision:
    """자율 전략 진화의 한 줄 결정 — 헌법 X.4 재지정 게이트 포렌식 증거."""

    action: str
    incumbent_key: str | None  # 현 라이브 검증 트랙
    challenger_key: str | None  # 재지정 후보(없으면 None)
    canary_verdict: str | None  # 하드닝 캐너리 결과(PASS/그 외/None=미실행)
    reason: str
    gate_challenger: bool  # ①③ 엣지 확정 + 사과 대 사과 도전자
    gate_multiplicity: bool  # ② 다중검정 보정 통과
    gate_canary: bool  # ④ 하드닝 캐너리 PASS

    observation_health: str = OBS_HEALTH_OK  # OK 일 때만 기존 재지정 판단 진행
    observation_note: str = ""
    gate_observation_quality: bool = True  # 후보 관측 품질 입력 게이트
    execution_feedback: dict[str, Any] | None = None

    SCHEMA_VERSION = "1.2"

    @property
    def all_gates_pass(self) -> bool:
        return (
            self.gate_observation_quality
            and self.gate_challenger
            and self.gate_multiplicity
            and self.gate_canary
        )

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "action": self.action,
            "incumbent_key": self.incumbent_key,
            "challenger_key": self.challenger_key,
            "canary_verdict": self.canary_verdict,
            "observation_health": self.observation_health,
            "observation_note": self.observation_note,
            "execution_feedback": self.execution_feedback,
            "reason": self.reason,
            "gates": {
                "observation_quality_ok": self.gate_observation_quality,
                "challenger_confirmed": self.gate_challenger,
                "multiplicity_robust": self.gate_multiplicity,
                "canary_pass": self.gate_canary,
            },
        }


def decide_reassignment(
    *,
    leaderboard: TournamentLeaderboard,
    canary_verdict: str | None,
    kill_switch_present: bool,
    execution_feedback: Mapping[str, Any] | None = None,
) -> ReassignDecision:
    """토너먼트 리더보드 + 하드닝 캐너리 결과 → 자동 재지정 결정(순수·보수적 fail-safe).

    5중 게이트 ①③은 `leaderboard.challenger_key`(엣지확정 도전자가 incumbent 를 비교 가능
    상태에서 앞섬 — forward_tournament 가 보장), ②는 `champion_multiplicity_robust`,
    ④는 `canary_verdict == CANARY_PASS`. ⑤(사다리 rung0 리셋)는 REASSIGN 의 실행 단계다.

    순서(가장 강한 차단부터):
      1. 킬스위치 → DISABLED.
      2. 도전자 없음(①③ 미충족) → HOLD(현 전략이 최선이거나 아직 미확정).
      3. 다중검정 보정 미통과(②) → HOLD(운 좋은 우승 가능 — 재지정 보류).
      4. 캐너리 미통과/미실행(④) → WAIT_CANARY(도전자 확정, 실거래 검증 필요).
      5. 전부 통과 → REASSIGN.
    """
    challenger = leaderboard.challenger_key
    incumbent = leaderboard.incumbent_key
    observation_health = leaderboard.observation_health or OBS_HEALTH_OK
    observation_note = leaderboard.observation_note or ""
    feedback = _execution_feedback_summary(execution_feedback)
    g_observation = observation_health == OBS_HEALTH_OK
    g_challenger = challenger is not None
    g_mult = leaderboard.champion_multiplicity_robust is True
    g_canary = canary_verdict == CANARY_PASS

    def _d(action: str, reason: str) -> ReassignDecision:
        return ReassignDecision(
            action=action,
            incumbent_key=incumbent,
            challenger_key=challenger,
            canary_verdict=canary_verdict,
            observation_health=observation_health,
            observation_note=observation_note,
            execution_feedback=feedback,
            reason=reason,
            gate_observation_quality=g_observation,
            gate_challenger=g_challenger,
            gate_multiplicity=g_mult,
            gate_canary=g_canary,
        )

    if kill_switch_present:
        return _d(
            ACTION_DISABLED,
            "automation/AUTOARM_DISABLED 존재 — 자동 재지정 정지(운영자 킬스위치).",
        )
    if not g_observation:
        if observation_health == OBS_HEALTH_BLOCKED:
            reason = (
                "후보 관측 품질 BLOCKED — 리더보드 판정 입력을 신뢰할 수 없어 재지정 금지."
            )
        elif observation_health == OBS_HEALTH_DEGRADED:
            reason = (
                "후보 관측 품질 DEGRADED — 후보군 비교가 불완전하므로 보수적으로 재지정 보류."
            )
        else:
            reason = (
                f"후보 관측 품질 {observation_health!r} — OK 가 아니므로 재지정 보류."
            )
        if observation_note:
            reason = f"{reason} ({observation_note})"
        return _d(ACTION_HOLD, reason)
    if not g_challenger:
        return _d(
            ACTION_HOLD,
            "도전자 없음(엣지 확정 + 사과 대 사과로 incumbent 를 앞선 트랙 부재) — 현 전략 유지.",
        )
    if not g_mult:
        return _d(
            ACTION_HOLD,
            f"도전자 '{challenger}' 다중검정 보정 미통과(6트랙 동시검정의 운 좋은 우승 가능) "
            "— 재지정 보류, 현 전략 유지.",
        )
    if not g_canary:
        return _d(
            ACTION_WAIT_CANARY,
            f"도전자 '{challenger}' 엣지·다중검정 보정 통과 — 하드닝 캐너리(소액 실거래 검증) "
            f"필요(현재 판정 {canary_verdict!r}). 통과 전까지 라이브 무변경.",
        )
    return _d(
        ACTION_REASSIGN,
        f"도전자 '{challenger}'가 5중 게이트 전부 통과(엣지 확정·다중검정 보정·사과 대 사과·"
        f"하드닝 캐너리 PASS) → 라이브를 '{incumbent}'에서 '{challenger}'로 재지정 + 자본 "
        "사다리 rung 0 리셋(새 전략을 25%부터 자율 재검증).",
    )


def _execution_feedback_summary(
    feedback: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(feedback, Mapping) or not feedback:
        return None
    cumulative = feedback.get("cumulative")
    counts = feedback.get("counts")
    latest = feedback.get("latest")
    return {
        "source": "rejected_order_opportunity_monitor",
        "effect": "evidence_only_no_gate_override",
        "verdict": feedback.get("verdict"),
        "verdict_label_ko": feedback.get("verdict_label_ko"),
        "latest_signal": feedback.get("latest_signal"),
        "interpretation_ko": feedback.get("interpretation_ko"),
        "next_action_ko": feedback.get("next_action_ko"),
        "cumulative": dict(cumulative) if isinstance(cumulative, Mapping) else {},
        "counts": dict(counts) if isinstance(counts, Mapping) else {},
        "latest": dict(latest) if isinstance(latest, Mapping) else None,
    }


__all__ = [
    "ACTION_DISABLED",
    "ACTION_HOLD",
    "ACTION_REASSIGN",
    "ACTION_WAIT_CANARY",
    "CANARY_PASS",
    "ReassignDecision",
    "decide_reassignment",
]
