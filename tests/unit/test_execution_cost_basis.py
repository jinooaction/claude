"""스펙 104 - 체결 비용 기준 계약 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.execution_cost_basis import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    COST_BASIS_OBSERVATION_WAIT,
    COST_BASIS_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_execution_cost_basis_report,
)

NOW = datetime(2026, 7, 7, 1, 30, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _execution_quality(cost_basis: dict | None = None) -> str:
    payload = {
        "overall_status": "OBSERVE",
        "broker_rejections": {
            "rejected_orders": 2,
            "parsed_broker_errors": 2,
            "kis_msg_codes": {"APBK1672": 2},
        },
        "live_gate": {
            "ok": False,
            "reason": "latest_intent_loss",
            "verdict": "INSUFFICIENT_DATA",
            "latest_signal": "INTENT_LOSS",
        },
    }
    if cost_basis is not None:
        payload["execution_cost_basis"] = cost_basis
    return _markdown_json(payload)


def _kis_smoke() -> str:
    return "# KIS smoke\n\n| smoke_state | success |\n| smoke_exit | 0 |\n"


def _rebalance_micro() -> str:
    return (
        "## 라이브 전 전략 의도 게이트\n"
        "```json\n"
        + _json({"ok": False, "latest_signal": "INTENT_LOSS"})
        + "\n```\n"
    )


def _money_path(*, status: str = "PREVIEW_ONLY", accepted: int = 0) -> str:
    return _markdown_json(
        {
            "overall_status": "OK",
            "live_money_state": {
                "status": status,
                "can_submit_real_orders": False,
                "armed": False,
            },
            "last_run": {
                "last_run_status": "skipped",
                "accepted_or_filled_count": accepted,
                "broker_rejected_count": 0,
            },
        }
    )


def _released() -> str:
    return _json(
        {
            "released_work": [
                {
                    "candidate_id": COMPLETED_CANDIDATE_ID,
                    "status": "released",
                    "reason_ko": "스펙 104 완료",
                }
            ]
        }
    )


def _capital() -> str:
    return _json(
        {
            "readiness_state": "ACCUMULATING_EDGE",
            "live_money_status": "PREVIEW_ONLY",
            "capital_ladder_status": "BLOCKED",
        }
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence = {
        "execution-quality": _execution_quality(),
        "kis-smoke": _kis_smoke(),
        "rebalance-micro-gtaa": _rebalance_micro(),
        "money-path": _money_path(),
        "pipeline-liveness": _markdown_json({"overall": "OK", "checks": []}),
        "released-work": _released(),
        "capital-path-readiness": _capital(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.gate_id: gate.status for gate in report.quality_gates}


def test_ready_report_requires_measurable_accepted_fill_cost_basis():
    report = build_execution_cost_basis_report(
        _evidence(
            **{
                "execution-quality": _execution_quality(
                    {
                        "basis_complete": True,
                        "accepted_or_filled_orders": 3,
                        "measurable_fills": 3,
                        "unmeasurable_fills": 0,
                        "turnover_observed": True,
                        "avg_slippage_bps": 4.2,
                        "median_slippage_bps": 3.8,
                        "total_cost_usd": 1.23,
                    }
                ),
                "money-path": _money_path(accepted=3),
            }
        ),
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == CONTRACT_READY
    assert report.run_id == "123"
    assert report.commit == "abc123"
    assert report.completed_candidate_id == COMPLETED_CANDIDATE_ID
    assert report.next_candidate_id == NEXT_AUTONOMOUS_CANDIDATE_ID
    assert set(_gates(report).values()) == {GATE_PASS}
    assert report.cost_basis_summary["cost_basis_state"] == COST_BASIS_READY
    assert report.cost_basis_summary["accepted_or_filled_orders"] == 3
    assert report.cost_basis_summary["basis_complete"] is True
    assert report.released_work_summary["completed_candidate_released"] is True
    assert report.capital_path_summary["money_path_mutation"] is False
    assert "no orders" in report.safety_invariants
    assert "체결 비용 기준" in report.as_markdown()


def test_current_missing_cost_basis_block_waits_without_overclaiming():
    report = build_execution_cost_basis_report(_evidence(), now=NOW)

    assert report.overall_status == OBSERVATION_WAIT
    assert report.cost_basis_summary["cost_basis_state"] == COST_BASIS_OBSERVATION_WAIT
    assert report.cost_basis_summary["execution_quality_has_cost_basis"] is False
    assert report.cost_basis_summary["accepted_or_filled_orders"] == 0
    assert report.money_path_summary["live_money_status"] == "PREVIEW_ONLY"
    assert _gates(report)["execution_cost_basis_observability"] == GATE_WAIT
    assert _gates(report)["accepted_fill_cost_basis"] == GATE_WAIT


def test_accepted_sample_without_measurable_cost_basis_still_waits():
    report = build_execution_cost_basis_report(
        _evidence(
            **{
                "execution-quality": _execution_quality(
                    {
                        "basis_complete": False,
                        "accepted_or_filled_orders": 2,
                        "measurable_fills": 0,
                        "unmeasurable_fills": 2,
                    }
                ),
                "money-path": _money_path(accepted=2),
            }
        ),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert report.cost_basis_summary["accepted_or_filled_orders"] == 2
    assert report.cost_basis_summary["basis_complete"] is False
    assert _gates(report)["execution_cost_basis_observability"] == GATE_PASS
    assert _gates(report)["accepted_fill_cost_basis"] == GATE_WAIT


def test_missing_execution_quality_blocks_contract():
    report = build_execution_cost_basis_report(
        _evidence(**{"execution-quality": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["required_evidence_parse"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["execution-quality"].parse_status == "missing"


def test_missing_money_path_blocks_context():
    report = build_execution_cost_basis_report(
        _evidence(**{"money-path": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["required_evidence_parse"] == GATE_FAIL
    assert _gates(report)["money_path_context"] == GATE_FAIL
