"""스펙 067 — 자율 성장 루프 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from auto_invest.analytics.evolution_loop import (
    STATUS_EVIDENCE_DEPENDENT,
    STATUS_NEW,
    STATUS_OPERATOR_REVIEW,
    STATUS_RELEASED,
    BreakthroughCandidate,
    EvidencePackage,
    LearningLedgerEntry,
    assert_no_secret_like_values,
    classify_safety_surfaces,
    decide_promotion,
    default_domains,
    generate_experiment_plan,
    mask_sensitive_values,
    scan_evolution,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "evolution_loop" / "fresh"
NOW = datetime(2026, 6, 29, 1, 0, 0, tzinfo=UTC)
SOURCE_DIVERSIFICATION_ID = "candidate-source-diversification-sidecar-bottleneck"


def _fixture_evidence() -> dict[str, str]:
    return {path.stem: path.read_text(encoding="utf-8") for path in FIXTURES.glob("*.md")}


def _fixture_dir_evidence(name: str) -> dict[str, str]:
    fixture_dir = ROOT / "tests" / "fixtures" / "evolution_loop" / name
    return {path.stem: path.read_text(encoding="utf-8") for path in fixture_dir.glob("*.md")}


def _agent_ops_candidate(summary):
    return next(c for c in summary.candidates if c.candidate_id == "candidate-88a7e7f07361")


def _candidate_by_id(summary, candidate_id: str):
    return next(c for c in summary.candidates if c.candidate_id == candidate_id)


def _closed_static_inputs() -> tuple[dict[str, str], dict[str, object]]:
    evidence = _fixture_evidence()
    base = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="base")
    evidence["released-work"] = json.dumps(
        {
            "schema_version": "1.0",
            "released_work": [
                {
                    "candidate_id": candidate.candidate_id,
                    "status": "released",
                    "reason_ko": "테스트에서 정적 후보 포화를 재현했다.",
                }
                for candidate in base.candidates
            ],
        },
        ensure_ascii=False,
    )
    evidence["capital-path-readiness"] = json.dumps(
        {
            "timestamp_utc": "2026-06-29T00:55:00Z",
            "observability_issues": [
                {
                    "issue_id": "released-candidate-echo:candidate-facf2fa31834",
                    "issue_type": "released_candidate_echo",
                    "source_key": "released-work",
                    "summary_ko": (
                        "released-work 장부가 완료로 기록한 후보가 "
                        "upstream 후보 목록에 남았다."
                    ),
                }
            ],
        },
        ensure_ascii=False,
    )
    evidence["promotion-summary"] = json.dumps(
        {
            "run_id": "run-source-diversification",
            "assessments": [
                {
                    "candidate_id": "candidate-1ed634d8bf6d",
                    "stage": "DISCARD",
                    "blocked_reason_ko": "전략 후보 검증 실패가 반복됐다.",
                    "candidate": {
                        "candidate_id": "candidate-1ed634d8bf6d",
                        "domain_key": "strategy_design",
                        "title_ko": "micro GTAA 의도 손익 재검토와 대체 전략 연구",
                    },
                }
            ],
        },
        ensure_ascii=False,
    )
    ledger = {
        "entries": [
            LearningLedgerEntry(
                entry_id="ledger-source-rejected",
                candidate_id="candidate-1ed634d8bf6d",
                decision="rejected",
                reason_ko="반복 실패",
                evidence_package_id="autonomous-promotion:run-source-diversification",
                next_recheck_condition=None,
                created_at_utc="2026-07-03T00:00:00Z",
            ).to_dict(),
            LearningLedgerEntry(
                entry_id="ledger-source-hold",
                candidate_id="candidate-dff4f9344b02",
                decision="evidence_dependent",
                reason_ko="다음 sidecar 재검토 전 보류",
                evidence_package_id="candidate-result-executor:pkg-test",
                next_recheck_condition="released-work 최신 실행 뒤 재검토",
                created_at_utc="2026-07-03T00:00:00Z",
            ).to_dict(),
        ]
    }
    return evidence, ledger


def _candidate(**overrides) -> BreakthroughCandidate:
    values = {
        "candidate_id": "candidate-test",
        "domain_key": "strategy_design",
        "title_ko": "테스트 후보",
        "problem_ko": "문제",
        "evidence_refs": ("money-path",),
        "expected_benefit": "profit",
        "breakthrough_type": "profit_power",
        "growth_leverage": 80,
        "capability_compounding": 80,
        "capital_path_alignment": 80,
        "evidence_confidence": 80,
        "safety_preservation": 90,
        "learning_velocity": 80,
        "repeatability": 80,
        "evidence_dependency": "none",
        "confidence": "high",
        "risk_grade": 2,
        "safety_impact": (),
        "status": "new",
        "next_action_ko": "읽기 전용 실험",
        "expires_at_utc": None,
        "recheck_condition": None,
    }
    values.update(overrides)
    return BreakthroughCandidate(**values)


def test_domain_registry_covers_required_domains() -> None:
    keys = {domain.key for domain in default_domains()}
    assert {
        "data_collection",
        "data_quality",
        "analysis",
        "strategy_design",
        "portfolio_design",
        "execution_quality",
        "live_readiness",
        "review",
        "agent_ops",
    } <= keys


@pytest.mark.parametrize(
    ("text", "surface"),
    [
        ("submit order to broker", "orders"),
        ("increase capital after success", "capital"),
        ("widen whitelist for new ETF", "whitelist"),
        ("relax cap for position", "caps"),
        ("secret handling change", "secrets"),
        ("market-hours deploy guard", "deploy"),
        ("constitution kernel update", "kernel"),
        ("live strategy swap", "live_strategy"),
        ("paid data provider", "paid_service"),
    ],
)
def test_classifies_safety_surfaces(text: str, surface: str) -> None:
    assert surface in classify_safety_surfaces(text)


def test_masks_and_rejects_secret_like_output() -> None:
    text = "KIS_APP_SECRET=abcdef123456 account_no: 123456789-01"
    masked = mask_sensitive_values(text)
    assert "abcdef123456" not in masked
    assert "123456789-01" not in masked
    with pytest.raises(ValueError):
        assert_no_secret_like_values(text)
    assert_no_secret_like_values(masked)


def test_scan_is_deterministic_and_covers_all_domains() -> None:
    evidence = _fixture_evidence()
    first = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    second = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    assert first.as_dict() == second.as_dict()
    candidate_domains = {candidate.domain_key for candidate in first.candidates}
    assert {domain.key for domain in default_domains()} <= candidate_domains
    assert first.top_breakthrough_candidates[0]
    assert "실주문 재개" not in first.candidates[0].title_ko
    assert first.safe_high_leverage_work
    assert "operator_review" in first.as_dict()


def test_agent_ops_candidate_is_released_when_liveness_and_handoff_are_satisfied() -> None:
    evidence = _fixture_evidence()
    evidence["pipeline-liveness"] = """
# 파이프라인 생존 감시

| 사이드카 | 핵심 | 상태 | 나이(h) | 한계(h) | 마지막 갱신 |
|----------|:----:|:----:|--------:|--------:|-------------|
| autonomous-evolution |  | 🟢 OK | 0.7 | 30 | 2026-06-29T00:20:00Z |

## 결정 JSON

```json
{
  "overall": "OK",
  "checks": [
    {"key": "autonomous-evolution", "status": "OK"}
  ]
}
```
"""
    evidence["handoff"] = """
# auto-invest — 다음 세션 인수인계 (main 베이스라인)

## 세션 시작 절차 (필수)

세션 시작 훅은 로컬 git 상태를 출력한다. 무엇이 머지됐고 무엇이 진행 중인지
불확실하면 HANDOFF.md와 `/sync` 스킬로 원격 브랜치와 열린 PR을 확인한다.
"""

    summary = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    candidate = _agent_ops_candidate(summary)

    assert candidate.status == STATUS_RELEASED
    assert "candidate-88a7e7f07361" not in summary.safe_high_leverage_work
    assert "이미 충족" in candidate.next_action_ko


def test_agent_ops_candidate_stays_actionable_when_handoff_entrypoint_is_missing() -> None:
    evidence = _fixture_evidence()
    evidence["pipeline-liveness"] = """
{"timestamp_utc":"2026-06-29T00:20:00Z","overall":"OK","checks":[{"key":"autonomous-evolution","status":"OK"}]}
"""
    evidence["handoff"] = "오래된 노트. 세션 시작 절차와 sync 경로가 없다."

    summary = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    candidate = _agent_ops_candidate(summary)

    assert candidate.status == STATUS_NEW
    assert "candidate-88a7e7f07361" in summary.safe_high_leverage_work


def test_agent_ops_candidate_stays_actionable_when_liveness_registration_is_missing() -> None:
    evidence = _fixture_evidence()
    evidence["handoff"] = """
# auto-invest — 다음 세션 인수인계 (main 베이스라인)

## 세션 시작 절차 (필수)

세션 시작 훅과 HANDOFF.md, `/sync`로 현재 git 상태를 확인한다.
"""

    summary = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    candidate = _agent_ops_candidate(summary)

    assert candidate.status == STATUS_NEW
    assert "candidate-88a7e7f07361" in summary.safe_high_leverage_work


def test_scan_separates_stale_evidence_from_strategy_failure() -> None:
    evidence = _fixture_evidence()
    evidence["public-data"] = (
        ROOT / "tests" / "fixtures" / "evolution_loop" / "stale" / "public-data.md"
    ).read_text(encoding="utf-8")
    summary = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    assert "public-data" in summary.stale_evidence
    data_quality = [c for c in summary.candidates if c.domain_key == "data_quality"][0]
    assert data_quality.evidence_dependency == "sidecar_freshness"


def test_scan_reports_missing_evidence_as_freshness_issue() -> None:
    summary = scan_evolution(
        _fixture_dir_evidence("missing"),
        now=NOW,
        commit="abc1234",
        run_id="test",
    )
    assert summary.overall_status == "degraded"
    assert "money-path" not in summary.stale_evidence
    assert {"reassign", "public-data", "regime-stratify"} <= set(summary.stale_evidence)
    data_quality = [c for c in summary.candidates if c.domain_key == "data_quality"][0]
    assert data_quality.evidence_dependency == "sidecar_freshness"
    assert summary.safe_high_leverage_work


def test_market_observation_dependency_is_not_loop_purpose() -> None:
    summary = scan_evolution(_fixture_evidence(), now=NOW, commit="abc1234", run_id="test")
    deps = summary.evidence_dependencies
    assert "market_observation" in deps
    assert summary.safe_high_leverage_work


def test_analysis_candidate_uses_regime_and_performance_evidence() -> None:
    summary = scan_evolution(_fixture_evidence(), now=NOW, commit="abc1234", run_id="test")
    candidate = next(
        c for c in summary.candidates if c.candidate_id == "candidate-e481b0309206"
    )
    assert candidate.evidence_refs == (
        "regime-stratify",
        "public-data",
        "promote-readiness",
    )
    assert candidate.evidence_dependency == "none"
    assert candidate.status == "new"
    assert candidate.composite_score >= 560
    assert "레짐·성과 sidecar" in candidate.next_action_ko


def test_execution_quality_candidate_uses_packaged_evidence() -> None:
    summary = scan_evolution(_fixture_evidence(), now=NOW, commit="abc1234", run_id="test")
    candidate = next(
        c for c in summary.candidates if c.candidate_id == "candidate-dff4f9344b02"
    )

    assert candidate.evidence_refs == (
        "execution-quality",
        "rebalance-micro-gtaa",
        "kis-smoke",
    )
    assert candidate.evidence_dependency == "none"
    assert candidate.status == "new"
    assert candidate.evidence_confidence >= 80
    assert "execution-quality sidecar" in candidate.next_action_ko


def test_missing_execution_quality_evidence_lowers_execution_candidate_confidence() -> None:
    fresh = scan_evolution(_fixture_evidence(), now=NOW, commit="abc1234", run_id="test")
    missing_evidence = _fixture_evidence()
    missing_evidence.pop("execution-quality")
    missing = scan_evolution(missing_evidence, now=NOW, commit="abc1234", run_id="test")

    fresh_candidate = next(
        c for c in fresh.candidates if c.candidate_id == "candidate-dff4f9344b02"
    )
    missing_candidate = next(
        c for c in missing.candidates if c.candidate_id == "candidate-dff4f9344b02"
    )
    assert "execution-quality" in missing.stale_evidence
    assert missing_candidate.evidence_dependency == "sidecar_freshness"
    assert missing_candidate.status == "evidence_dependent"
    assert missing_candidate.composite_score < fresh_candidate.composite_score
    assert "신선도" in missing_candidate.next_action_ko


def test_missing_performance_evidence_lowers_analysis_confidence() -> None:
    fresh = scan_evolution(_fixture_evidence(), now=NOW, commit="abc1234", run_id="test")
    missing_evidence = _fixture_evidence()
    missing_evidence.pop("promote-readiness")
    missing = scan_evolution(missing_evidence, now=NOW, commit="abc1234", run_id="test")

    fresh_candidate = next(
        c for c in fresh.candidates if c.candidate_id == "candidate-e481b0309206"
    )
    missing_candidate = next(
        c for c in missing.candidates if c.candidate_id == "candidate-e481b0309206"
    )
    assert "promote-readiness" in missing.stale_evidence
    assert missing_candidate.evidence_dependency == "sidecar_freshness"
    assert missing_candidate.status == "evidence_dependent"
    assert missing_candidate.composite_score < fresh_candidate.composite_score
    assert "신선도" in missing_candidate.next_action_ko


def test_stale_performance_evidence_lowers_analysis_confidence() -> None:
    fresh = scan_evolution(_fixture_evidence(), now=NOW, commit="abc1234", run_id="test")
    stale_evidence = _fixture_evidence()
    stale_evidence["promote-readiness"] = (
        ROOT / "tests" / "fixtures" / "evolution_loop" / "stale" / "promote-readiness.md"
    ).read_text(encoding="utf-8")
    stale = scan_evolution(stale_evidence, now=NOW, commit="abc1234", run_id="test")

    fresh_candidate = next(
        c for c in fresh.candidates if c.candidate_id == "candidate-e481b0309206"
    )
    stale_candidate = next(
        c for c in stale.candidates if c.candidate_id == "candidate-e481b0309206"
    )
    assert "promote-readiness" in stale.stale_evidence
    assert stale_candidate.evidence_dependency == "sidecar_freshness"
    assert stale_candidate.status == "evidence_dependent"
    assert stale_candidate.composite_score < fresh_candidate.composite_score
    assert "신선도" in stale_candidate.next_action_ko


def test_setup_error_performance_evidence_does_not_boost_analysis_candidate() -> None:
    evidence = _fixture_evidence()
    evidence["promote-readiness"] = """
# 풀라이브 승격 준비(헌법 VI 게이트) — 최신 평가

| 항목 | 값 |
|------|-----|
| timestamp_utc | 2026-06-29T00:50:00Z |
| READY (VI 트랙레코드) | false |
| ssh_exit | 2 (0=READY,1=NOT READY,그외=셋업/오류) |
"""
    summary = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    candidate = next(
        c for c in summary.candidates if c.candidate_id == "candidate-e481b0309206"
    )
    assert candidate.evidence_dependency == "sidecar_freshness"
    assert candidate.status == "evidence_dependent"
    assert candidate.evidence_confidence <= 42


def test_experiment_plan_keeps_trading_changes_out_of_goal() -> None:
    candidate = _candidate(evidence_dependency="market_observation")
    plan = generate_experiment_plan(candidate)
    assert plan.allowed_stage == "read_only"
    assert "실주문" in plan.non_goals_ko
    assert any("추가 관측" in item for item in plan.failure_criteria)


def test_strategy_swap_routes_to_reassignment_gate() -> None:
    candidate = _candidate(safety_impact=("live_strategy",), risk_grade=4)
    package = EvidencePackage(
        package_id="pkg",
        experiment_id="exp",
        result="pass",
        baseline="baseline",
        measurements={},
        limitations_ko="없음",
        safety_review_ko="live 전략 교체",
        recommended_decision="feed_existing_gate",
    )
    decision = decide_promotion(candidate, package)
    assert decision.decision == "feed_existing_gate"
    assert decision.next_gate == "spec-055-autonomous-reassignment"


def test_capital_scaling_routes_to_capital_ladder() -> None:
    candidate = _candidate(safety_impact=("capital",), risk_grade=4)
    package = EvidencePackage(
        package_id="pkg",
        experiment_id="exp",
        result="pass",
        baseline="baseline",
        measurements={},
        limitations_ko="없음",
        safety_review_ko="자본 확대",
        recommended_decision="feed_existing_gate",
    )
    decision = decide_promotion(candidate, package)
    assert decision.decision == "feed_existing_gate"
    assert decision.next_gate == "spec-050-capital-ladder"


def test_rejected_ledger_entry_prevents_reactivation() -> None:
    evidence = _fixture_evidence()
    first = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    rejected_id = first.candidates[0].candidate_id
    ledger = {
        "entries": [
            LearningLedgerEntry(
                entry_id="ledger-1",
                candidate_id=rejected_id,
                decision="rejected",
                reason_ko="기준 미달",
                evidence_package_id=None,
                next_recheck_condition=None,
                created_at_utc="2026-06-28T00:00:00Z",
            ).to_dict()
        ]
    }
    second = scan_evolution(evidence, ledger_doc=ledger, now=NOW, commit="abc1234", run_id="test")
    by_id = {candidate.candidate_id: candidate for candidate in second.candidates}
    assert by_id[rejected_id].status == "rejected"


def test_evidence_dependent_ledger_entry_blocks_safe_reactivation() -> None:
    evidence = _fixture_evidence()
    candidate_id = "candidate-fa66202bf496"
    ledger = {
        "entries": [
            LearningLedgerEntry(
                entry_id="ledger-fa66202bf496-hold",
                candidate_id=candidate_id,
                decision="evidence_dependent",
                reason_ko="결과 실행기가 package pkg-ae5a47448ec9만 확인했으므로 재검증 전 보류",
                evidence_package_id="candidate-result-executor:pkg-ae5a47448ec9",
                next_recheck_condition=(
                    "released-work와 promotion sidecar가 같은 커밋을 소비한 뒤 재검토"
                ),
                created_at_utc="2026-07-03T00:00:00Z",
            ).to_dict()
        ]
    }

    summary = scan_evolution(
        evidence, ledger_doc=ledger, now=NOW, commit="abc1234", run_id="test"
    )
    candidate = _candidate_by_id(summary, candidate_id)

    assert candidate.status == STATUS_EVIDENCE_DEPENDENT
    assert candidate_id not in summary.safe_high_leverage_work
    assert "pkg-ae5a47448ec9" in candidate.next_action_ko
    assert "released-work" in candidate.next_action_ko


def test_operator_review_ledger_entry_blocks_autonomous_start() -> None:
    evidence = _fixture_evidence()
    candidate_id = "candidate-e481b0309206"
    ledger = {
        "entries": [
            LearningLedgerEntry(
                entry_id="ledger-e481b0309206-review",
                candidate_id=candidate_id,
                decision="operator_review",
                reason_ko="분석 후보가 운영 판단 없이 자동 시작되면 범위가 과해진다.",
                evidence_package_id="manual-review:2026-07-03",
                next_recheck_condition="운영자가 분석 범위를 확정한 뒤 재검토",
                created_at_utc="2026-07-03T00:00:00Z",
            ).to_dict()
        ]
    }

    summary = scan_evolution(
        evidence, ledger_doc=ledger, now=NOW, commit="abc1234", run_id="test"
    )
    candidate = _candidate_by_id(summary, candidate_id)

    assert candidate.status == STATUS_OPERATOR_REVIEW
    assert candidate_id in summary.operator_review
    assert candidate_id not in summary.safe_high_leverage_work
    assert "운영자" in candidate.next_action_ko
    assert "manual-review:2026-07-03" in candidate.next_action_ko


def test_promotion_discard_entries_become_rejected_learning_ledger_entries() -> None:
    evidence = _fixture_evidence()
    evidence["promotion-summary"] = json.dumps(
        {
            "schema_version": "1.0",
            "run_id": "28504209238",
            "assessments": [
                {
                    "candidate_id": "candidate-1ed634d8bf6d",
                    "stage": "DISCARD",
                    "allowed_next_action": "재설계 후보로 보낸다.",
                    "blocked_reason_ko": "전략 백테스트 실패",
                    "candidate": {
                        "candidate_id": "candidate-1ed634d8bf6d",
                        "domain_key": "strategy_design",
                        "title_ko": "micro GTAA 의도 손익 재검토와 대체 전략 연구",
                    },
                },
                {
                    "candidate_id": "candidate-cc96b35062da",
                    "stage": "DISCARD",
                    "allowed_next_action": "재설계 후보로 보낸다.",
                    "blocked_reason_ko": "포트폴리오 백테스트 실패",
                    "candidate": {
                        "candidate_id": "candidate-cc96b35062da",
                        "domain_key": "portfolio_design",
                        "title_ko": "비상관 포트폴리오 후보 비교력 강화",
                    },
                },
            ],
        },
        ensure_ascii=False,
    )

    summary = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    ledger = {
        (entry.candidate_id, entry.decision): entry for entry in summary.learning_ledger
    }

    strategy = ledger[("candidate-1ed634d8bf6d", "rejected")]
    portfolio = ledger[("candidate-cc96b35062da", "rejected")]
    assert strategy.reason_ko == "전략 백테스트 실패"
    assert portfolio.reason_ko == "포트폴리오 백테스트 실패"
    assert strategy.evidence_package_id == "autonomous-promotion:28504209238"
    assert portfolio.evidence_package_id == "autonomous-promotion:28504209238"
    by_id = {candidate.candidate_id: candidate for candidate in summary.candidates}
    assert by_id["candidate-1ed634d8bf6d"].status == "rejected"
    assert by_id["candidate-cc96b35062da"].status == "rejected"


def test_promotion_discard_entries_do_not_duplicate_existing_rejections() -> None:
    evidence = _fixture_evidence()
    evidence["promotion-summary"] = json.dumps(
        {
            "run_id": "run-new",
            "assessments": [
                {
                    "candidate_id": "candidate-1ed634d8bf6d",
                    "stage": "DISCARD",
                    "blocked_reason_ko": "전략 백테스트 실패",
                    "candidate": {
                        "candidate_id": "candidate-1ed634d8bf6d",
                        "domain_key": "strategy_design",
                    },
                }
            ],
        },
        ensure_ascii=False,
    )
    ledger = {
        "entries": [
            LearningLedgerEntry(
                entry_id="ledger-old",
                candidate_id="candidate-1ed634d8bf6d",
                decision="rejected",
                reason_ko="기존 실패",
                evidence_package_id="autonomous-promotion:old",
                next_recheck_condition=None,
                created_at_utc="2026-06-28T00:00:00Z",
            ).to_dict()
        ]
    }

    summary = scan_evolution(
        evidence,
        ledger_doc=ledger,
        now=NOW,
        commit="abc1234",
        run_id="test",
    )
    entries = [
        entry
        for entry in summary.learning_ledger
        if entry.candidate_id == "candidate-1ed634d8bf6d"
        and entry.decision == "rejected"
    ]
    assert len(entries) == 1
    assert entries[0].reason_ko == "기존 실패"


def test_malformed_promotion_summary_fails_open() -> None:
    evidence = _fixture_evidence()
    evidence["promotion-summary"] = "{not-json"

    summary = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")

    assert summary.candidates
    assert summary.learning_ledger
    assert not any(
        entry.evidence_package_id == "autonomous-promotion"
        for entry in summary.learning_ledger
    )


def test_summary_json_is_secret_safe() -> None:
    evidence = _fixture_evidence()
    evidence["manual"] = "KIS_APP_KEY=abcdef123456"
    summary = scan_evolution(evidence, now=NOW, commit="abc1234", run_id="test")
    payload = json.dumps(summary.as_dict(), ensure_ascii=False)
    assert "abcdef123456" not in payload


def test_closed_static_candidate_set_creates_source_diversification_candidate() -> None:
    evidence, ledger = _closed_static_inputs()

    summary = scan_evolution(
        evidence,
        ledger_doc=ledger,
        now=NOW,
        commit="abc1234",
        run_id="test",
    )
    candidate = _candidate_by_id(summary, SOURCE_DIVERSIFICATION_ID)

    assert candidate.status == STATUS_NEW
    assert candidate.risk_grade == 2
    assert candidate.safety_impact == ()
    assert candidate.candidate_id in summary.safe_high_leverage_work
    assert "정적 후보" in candidate.problem_ko
    assert "released-work" in candidate.evidence_refs
    assert "capital-path-readiness" in candidate.evidence_refs


def test_existing_safe_static_candidate_prevents_source_diversification_noise() -> None:
    summary = scan_evolution(_fixture_evidence(), now=NOW, commit="abc1234", run_id="test")

    assert any(candidate.status == STATUS_NEW for candidate in summary.candidates)
    assert not any(
        candidate.candidate_id == SOURCE_DIVERSIFICATION_ID for candidate in summary.candidates
    )


def test_source_diversification_reason_names_ledger_and_observation_bottlenecks() -> None:
    evidence, ledger = _closed_static_inputs()

    summary = scan_evolution(
        evidence,
        ledger_doc=ledger,
        now=NOW,
        commit="abc1234",
        run_id="test",
    )
    candidate = _candidate_by_id(summary, SOURCE_DIVERSIFICATION_ID)

    assert "rejected 1건" in candidate.problem_ko
    assert "evidence_dependent 1건" in candidate.problem_ko
    assert "promotion failure 1건" in candidate.problem_ko
    assert "관찰 병목 1건" in candidate.problem_ko
    assert "학습 장부" in candidate.next_action_ko
    assert "sidecar" in candidate.next_action_ko
