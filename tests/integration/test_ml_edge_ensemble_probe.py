"""Spec 145 CLI, workflow, and autonomous input boundary tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.autonomous_work_execution import build_autonomous_work_execution

ROOT = Path(__file__).resolve().parents[2]


def _report(*, eligible: bool) -> str:
    return json.dumps(
        {
            "verdict": "ML_EDGE_CANDIDATE_READY" if eligible else "NO_EDGE",
            "candidate_package": {
                "eligible": eligible,
                "candidate_id": "candidate-ml-edge-ensemble-v1",
                "title_ko": "AI 확신도 기반 추세 앙상블 재현 검증",
                "domain_key": "investment_edge",
                "status": "new" if eligible else "rejected",
                "risk_grade": 2,
                "priority_score": 700,
            },
        }
    )


def test_no_edge_report_is_evidence_only_but_ready_report_becomes_work_packet():
    now = datetime(2026, 8, 16, tzinfo=UTC)
    blocked = build_autonomous_work_execution(
        {"ml-edge-ensemble": _report(eligible=False)}, now=now
    )
    ready = build_autonomous_work_execution(
        {"ml-edge-ensemble": _report(eligible=True)}, now=now
    )

    assert all(
        packet.candidate_id != "candidate-ml-edge-ensemble-v1"
        for packet in blocked.ranked_work
    )
    assert any(
        packet.candidate_id == "candidate-ml-edge-ensemble-v1"
        for packet in ready.ranked_work
    )


def test_workflow_publishes_only_candidate_object_and_has_no_live_commands():
    workflow = (ROOT / ".github/workflows/ml-edge-ensemble.yml").read_text(encoding="utf-8")
    module = (ROOT / "src/auto_invest/analytics/ml_edge_ensemble.py").read_text(
        encoding="utf-8"
    )
    probe = (ROOT / "scripts/ml_edge_ensemble_probe.py").read_text(encoding="utf-8")

    assert "jq '.candidate_package'" in workflow
    assert "automation/ml-edge-ensemble-last-run" in workflow
    combined = (module + probe).lower()
    for forbidden in ("submit_order", "cancel_order", "kisbroker", "live_money_state"):
        assert forbidden not in combined

