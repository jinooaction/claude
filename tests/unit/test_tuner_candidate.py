"""스펙 012 T012 — 캐너리 후보 구체화 (결정론·클램프·등급 제외)."""

from __future__ import annotations

from auto_invest.tuner.candidate import build_canary_candidate
from auto_invest.tuner.models import (
    CandidateChange,
    Classification,
    ProposedChange,
)


def _max_tokens_change() -> CandidateChange:
    return CandidateChange(
        candidate_id="cost_drift:usd_per_decision_mean",
        detection_rule="cost_drift",
        kpi_name="usd_per_decision_mean",
        observed_value="0.05",
        observed_tier="C",
        window="7d",
        proposed=ProposedChange(
            kind="max_tokens_reduce",
            target_paths=("config/judgment_tunables.toml",),
            config_key="daily_summary.max_tokens",
            old_value="700",
            new_value="560",
        ),
        rationale="cost drift → daily_summary.max_tokens 700→560",
        measurement_sample=40,
    )


def _cls(tier: str, *, kernel=(), change=None) -> Classification:
    return Classification(
        candidate=change or _max_tokens_change(),
        tier=tier,  # type: ignore[arg-type]
        kernel_groups=tuple(kernel),
        reason="test",
    )


def test_l2_max_tokens_builds_candidate():
    cand = build_canary_candidate(_cls("L2"))
    assert cand is not None
    assert cand.candidate_id == "cost_drift:usd_per_decision_mean"
    assert cand.authority_tier == "L2"
    assert cand.config_key == "daily_summary.max_tokens"
    assert (cand.old_value, cand.new_value) == ("700", "560")
    assert cand.recommended_tier == "L2"
    assert cand.recommended_window_days == 30


def test_l3_window_is_45():
    cand = build_canary_candidate(_cls("L3"))
    assert cand is not None
    assert cand.recommended_window_days == 45


def test_deterministic():
    a = build_canary_candidate(_cls("L2"))
    b = build_canary_candidate(_cls("L2"))
    assert a == b


def test_l1_returns_none():
    assert build_canary_candidate(_cls("L1")) is None


def test_l4_kernel_returns_none():
    assert build_canary_candidate(_cls("L4", kernel=("K3",))) is None


def test_kernel_groups_on_l2_excluded():
    # 방어 심층화: L2 라벨이어도 kernel 교집합이 있으면 후보 제외.
    assert build_canary_candidate(_cls("L2", kernel=("K3",))) is None


def test_proposal_only_returns_none():
    change = CandidateChange(
        candidate_id="cache_miss:cache_hit_rate",
        detection_rule="cache_miss",
        kpi_name="cache_hit_rate",
        observed_value="0.1",
        observed_tier="C",
        window="7d",
        proposed=ProposedChange(kind="proposal_only", target_paths=()),
        rationale="no apply path",
        measurement_sample=40,
    )
    assert build_canary_candidate(_cls("L2", change=change)) is None
