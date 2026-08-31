"""스펙 055 — 자율 전략 진화: 자동 재지정 결정 단위 테스트.

핵심 불변식: 5중 게이트 중 하나라도 불충족이면 절대 REASSIGN 아님(보수적 fail-safe).
킬스위치 최우선, 도전자 없음/운 좋은 우승=HOLD, 캐너리 미통과=WAIT, 전부 통과만 REASSIGN.
"""

from __future__ import annotations

from auto_invest.analytics.forward_tournament import (
    OBS_HEALTH_BLOCKED,
    OBS_HEALTH_DEGRADED,
    OBS_HEALTH_OK,
    TournamentLeaderboard,
)
from auto_invest.portfolio.auto_reassign import (
    ACTION_DISABLED,
    ACTION_HOLD,
    ACTION_REASSIGN,
    ACTION_WAIT_CANARY,
    decide_reassignment,
)


def _lb(
    *,
    challenger_key: str | None = None,
    champion_multiplicity_robust: bool | None = None,
    incumbent_key: str | None = "global-trend",
    observation_health: str = OBS_HEALTH_OK,
    observation_note: str = "",
) -> TournamentLeaderboard:
    """테스트용 최소 리더보드 — 재지정 결정에 쓰는 필드만 채운다."""
    return TournamentLeaderboard(
        schema_version="1.0",
        as_of_utc=None,
        rows=[],
        champion_key=challenger_key,
        incumbent_key=incumbent_key,
        challenger_key=challenger_key,
        headline="",
        note="",
        comparable_count=2,
        adjusted_dsr_threshold=None,
        champion_multiplicity_robust=champion_multiplicity_robust,
        observation_health=observation_health,
        observation_note=observation_note,
    )


def test_kill_switch_overrides_everything() -> None:
    # 5중 게이트가 다 통과해도 킬스위치면 DISABLED.
    lb = _lb(challenger_key="multi-asset-trend", champion_multiplicity_robust=True)
    d = decide_reassignment(leaderboard=lb, canary_verdict="PASS", kill_switch_present=True)
    assert d.action == ACTION_DISABLED


def test_no_challenger_holds() -> None:
    lb = _lb(challenger_key=None)
    d = decide_reassignment(leaderboard=lb, canary_verdict="PASS", kill_switch_present=False)
    assert d.action == ACTION_HOLD
    assert d.gate_challenger is False


def test_blocked_observation_quality_forbids_reassignment() -> None:
    lb = _lb(
        challenger_key="multi-asset-trend",
        champion_multiplicity_robust=True,
        observation_health=OBS_HEALTH_BLOCKED,
        observation_note="라이브 검증 트랙 판정 없음",
    )
    d = decide_reassignment(leaderboard=lb, canary_verdict="PASS", kill_switch_present=False)
    assert d.action == ACTION_HOLD
    assert d.gate_observation_quality is False
    assert "BLOCKED" in d.reason
    assert "재지정 금지" in d.reason


def test_degraded_observation_quality_holds_before_canary() -> None:
    lb = _lb(
        challenger_key="multi-asset-trend",
        champion_multiplicity_robust=True,
        observation_health=OBS_HEALTH_DEGRADED,
        observation_note="관측 뒤처짐: globalfixed",
    )
    d = decide_reassignment(leaderboard=lb, canary_verdict="PASS", kill_switch_present=False)
    assert d.action == ACTION_HOLD
    assert d.gate_observation_quality is False
    assert "DEGRADED" in d.reason
    assert "보류" in d.reason


def test_multiplicity_none_holds() -> None:
    # 도전자는 있으나 다중검정 보정 미평가(None) → 운 좋은 우승 가능 → HOLD.
    lb = _lb(challenger_key="multi-asset-trend", champion_multiplicity_robust=None)
    d = decide_reassignment(leaderboard=lb, canary_verdict="PASS", kill_switch_present=False)
    assert d.action == ACTION_HOLD
    assert d.gate_challenger is True
    assert d.gate_multiplicity is False


def test_multiplicity_false_holds() -> None:
    lb = _lb(challenger_key="multi-asset-trend", champion_multiplicity_robust=False)
    d = decide_reassignment(leaderboard=lb, canary_verdict="PASS", kill_switch_present=False)
    assert d.action == ACTION_HOLD
    assert d.gate_multiplicity is False


def test_canary_missing_waits() -> None:
    # ①②③ 통과, 캐너리 미실행(None) → WAIT_CANARY(라이브 무변경).
    lb = _lb(challenger_key="multi-asset-trend", champion_multiplicity_robust=True)
    d = decide_reassignment(leaderboard=lb, canary_verdict=None, kill_switch_present=False)
    assert d.action == ACTION_WAIT_CANARY
    assert d.gate_challenger and d.gate_multiplicity
    assert d.gate_canary is False


def test_canary_fail_waits() -> None:
    lb = _lb(challenger_key="multi-asset-trend", champion_multiplicity_robust=True)
    d = decide_reassignment(
        leaderboard=lb, canary_verdict="FAIL", kill_switch_present=False
    )
    assert d.action == ACTION_WAIT_CANARY
    assert d.gate_canary is False


def test_all_gates_pass_reassigns() -> None:
    lb = _lb(
        challenger_key="multi-asset-trend",
        champion_multiplicity_robust=True,
        incumbent_key="global-trend",
    )
    d = decide_reassignment(leaderboard=lb, canary_verdict="PASS", kill_switch_present=False)
    assert d.action == ACTION_REASSIGN
    assert d.all_gates_pass is True
    assert d.challenger_key == "multi-asset-trend"
    assert d.incumbent_key == "global-trend"
    # 포렌식 JSON 에 다섯 관문 중 코드 평가분(①③②④)이 다 담긴다.
    gates = d.to_json_dict()["gates"]
    assert gates == {
        "observation_quality_ok": True,
        "challenger_confirmed": True,
        "multiplicity_robust": True,
        "canary_pass": True,
    }


def test_reassign_reason_names_both_strategies() -> None:
    lb = _lb(
        challenger_key="multi-asset-trend",
        champion_multiplicity_robust=True,
        incumbent_key="global-trend",
    )
    d = decide_reassignment(leaderboard=lb, canary_verdict="PASS", kill_switch_present=False)
    assert "multi-asset-trend" in d.reason and "global-trend" in d.reason
    assert "rung 0" in d.reason  # ⑤ 사다리 리셋 명시
    assert "단1=10% 검증" in d.reason
    assert "단2=20% 탐색" in d.reason


def test_all_gates_pass_false_when_any_gate_open() -> None:
    lb = _lb(challenger_key="x", champion_multiplicity_robust=True)
    d = decide_reassignment(leaderboard=lb, canary_verdict=None, kill_switch_present=False)
    assert d.all_gates_pass is False


def test_execution_feedback_is_evidence_only() -> None:
    lb = _lb(challenger_key=None)
    feedback = {
        "verdict": "STRATEGY_REVIEW",
        "verdict_label_ko": "전략 검토 필요",
        "latest_signal": "INTENT_LOSS",
        "cumulative": {"total_intended_order_mark_pnl_usd": "-5.50"},
        "counts": {"records": 2, "valued_records": 2},
    }

    d = decide_reassignment(
        leaderboard=lb,
        canary_verdict="PASS",
        kill_switch_present=False,
        execution_feedback=feedback,
    )

    assert d.action == ACTION_HOLD
    out = d.to_json_dict()
    assert out["execution_feedback"]["verdict"] == "STRATEGY_REVIEW"
    assert out["execution_feedback"]["effect"] == "evidence_only_no_gate_override"
