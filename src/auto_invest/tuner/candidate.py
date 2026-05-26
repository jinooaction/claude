"""캐너리 후보 구체화 (스펙 012, FR-C12-01).

L2/L3 비커널 분류 후보를 스펙 007 하드닝 캐너리가 평가 가능한 구조화 단위
(`CanaryCandidate`)로 매핑한다. v1 구체 노브는 판단 지점 `max_tokens` 축소
(`max_tokens_reduce`)뿐 — 그 외 종류·등급은 None(기존 canary_entered 로그 유지).

순수 함수·결정론(LLM·벽시계·난수 미사용). 같은 Classification → 같은 CanaryCandidate.
"""

from __future__ import annotations

from auto_invest.tuner.models import CanaryCandidate, Classification

# 캐너리 등급별 최소 윈도(거래일) — config/canary_bands.toml 의 FR-C02 하한과 일치.
_TIER_WINDOW_DAYS = {"L2": 30, "L3": 45}


def build_canary_candidate(c: Classification) -> CanaryCandidate | None:
    """L2/L3·비커널·max_tokens_reduce 후보만 CanaryCandidate 로 구체화.

    조건 불충족(L1/L4, Kernel 교집합, 구체 노브 없음)이면 None.
    """
    if c.tier not in ("L2", "L3"):
        return None
    if c.kernel_groups:
        return None
    proposed = c.candidate.proposed
    if proposed.kind != "max_tokens_reduce":
        return None
    if proposed.config_key is None or proposed.old_value is None or proposed.new_value is None:
        return None
    if not proposed.target_paths:
        return None
    if proposed.old_value == proposed.new_value:
        return None

    return CanaryCandidate(
        candidate_id=c.candidate.candidate_id,
        detection_rule=c.candidate.detection_rule,
        authority_tier=c.tier,
        target_path=proposed.target_paths[0],
        config_key=proposed.config_key,
        old_value=proposed.old_value,
        new_value=proposed.new_value,
        recommended_tier=c.tier,
        recommended_window_days=_TIER_WINDOW_DAYS[c.tier],
        measurement_sample=c.candidate.measurement_sample,
        rationale=c.candidate.rationale,
    )


__all__ = ["build_canary_candidate"]
