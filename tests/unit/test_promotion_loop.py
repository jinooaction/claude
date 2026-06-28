"""스펙 068 — 자율 승격 루프 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.promotion_loop import (
    STAGE_CANARY_CANDIDATE,
    STAGE_EXISTING_GATE_READY,
    STAGE_FORWARD_REGISTRATION_READY,
    STAGE_OPERATOR_REVIEW,
    STAGE_RECENT_OOS_REQUIRED,
    backtest_vs_canary_explanation,
    scan_promotion,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "promotion_loop" / "fresh"
NOW = datetime(2026, 6, 29, 2, 0, 0, tzinfo=UTC)


def _json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _evidence() -> dict[str, str]:
    return {path.stem: path.read_text(encoding="utf-8") for path in FIXTURES.glob("*.md")}


def _summary():
    return scan_promotion(
        candidate_backlog=_json("candidate_backlog.json"),
        evolution_summary=_json("evolution_summary.json"),
        evidence_texts=_evidence(),
        now=NOW,
        commit="abc1234",
        run_id="test",
    )


def test_scan_is_deterministic() -> None:
    first = _summary().as_dict()
    second = _summary().as_dict()
    assert first == second


def test_backtest_only_candidate_cannot_skip_to_canary() -> None:
    by_id = {a.candidate_id: a for a in _summary().assessments}
    assessment = by_id["candidate-backtest-only"]
    assert assessment.stage == STAGE_RECENT_OOS_REQUIRED
    assert assessment.strategy_validation_complete is False
    assert assessment.execution_validation_complete is False
    assert "브로커" in _summary().as_markdown()


def test_oos_and_walk_forward_candidate_is_forward_registration_ready() -> None:
    by_id = {a.candidate_id: a for a in _summary().assessments}
    assert by_id["candidate-forward-ready"].stage == STAGE_FORWARD_REGISTRATION_READY


def test_existing_capital_gate_routes_to_capital_ladder_only() -> None:
    by_id = {a.candidate_id: a for a in _summary().assessments}
    assessment = by_id["candidate-capital-gate"]
    assert assessment.stage == STAGE_EXISTING_GATE_READY
    assert assessment.next_gate == "spec-050-capital-ladder"
    assert assessment.execution_validation_complete is True


def test_hard_safety_surface_goes_to_operator_review() -> None:
    by_id = {a.candidate_id: a for a in _summary().assessments}
    assessment = by_id["candidate-unsafe"]
    assert assessment.stage == STAGE_OPERATOR_REVIEW
    assert assessment.next_gate is None


def test_canary_candidate_requires_forward_pass_but_not_broker_complete() -> None:
    backlog = _json("candidate_backlog.json")
    backlog["candidates"] = [
        {
            "candidate_id": "candidate-canary",
            "title_ko": "forward 통과 후보",
            "domain_key": "strategy_design",
            "status": "new",
            "risk_grade": 2,
            "safety_impact": [],
            "evidence_refs": ["forward"],
            "composite_score": 600,
            "promotion_evidence": {
                "historical_backtest": "pass",
                "recent_oos": "pass",
                "walk_forward": "pass",
                "forward_paper": "pass"
            },
        }
    ]
    summary = scan_promotion(
        candidate_backlog=backlog,
        evidence_texts=_evidence(),
        now=NOW,
        commit="abc1234",
        run_id="test",
    )
    assessment = summary.assessments[0]
    assert assessment.stage == STAGE_CANARY_CANDIDATE
    assert assessment.strategy_validation_complete is True
    assert assessment.execution_validation_complete is False


def test_backtest_vs_canary_explanation_lists_broker_gaps() -> None:
    gaps = backtest_vs_canary_explanation()
    assert "브로커 주문 거부" in gaps
    assert "부분 체결과 미체결" in gaps
    assert "append-only 감사 로그와 일일 정산" in gaps


def test_queue_json_contains_stage_and_next_action() -> None:
    queue = _summary().queue_dict()
    assert queue["queue"]
    assert {"candidate_id", "stage", "allowed_next_action"} <= set(queue["queue"][0])
