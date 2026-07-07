"""스펙 103 — 브로커 거부 분류 계약 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.broker_rejection_taxonomy import (
    ACTION_NO_AUTO_RETRY,
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_broker_rejection_taxonomy_report,
)

NOW = datetime(2026, 7, 7, 0, 20, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _execution_quality(
    *,
    rejected_orders: int = 2,
    parsed_broker_errors: int = 2,
    codes: dict[str, int] | None = None,
    smoke_state: str = "success",
) -> str:
    codes = {"APBK1672": 2} if codes is None else codes
    return _markdown_json(
        {
            "overall_status": "OBSERVE",
            "broker_rejections": {
                "rejected_orders": rejected_orders,
                "parsed_broker_errors": parsed_broker_errors,
                "unparsed_reasons": 0,
                "broker_error_observation_rate": "1.0000",
                "kis_msg_codes": codes,
                "exception_types": {"KisOrderResponseError": parsed_broker_errors},
                "http_statuses": {"200": parsed_broker_errors},
            },
            "broker_smoke": {
                "present": True,
                "smoke_state": smoke_state,
                "smoke_exit": 0 if smoke_state == "success" else 1,
                "tests_total": 4,
                "tests_failed": 0 if smoke_state == "success" else 1,
                "smoke_error_rate": "0.0000" if smoke_state == "success" else "0.2500",
                "key_valid": True,
            },
            "live_gate": {
                "present": True,
                "ok": False,
                "reason": "latest_intent_loss",
                "verdict": "INSUFFICIENT_DATA",
                "latest_signal": "INTENT_LOSS",
                "next_action_ko": "실주문을 멈추고 forward 토너먼트·전략 검토 증거를 확인합니다.",
            },
        }
    )


def _kis_smoke(*, smoke_state: str = "success", smoke_exit: int = 0) -> str:
    return (
        "# KIS smoke\n\n"
        "| 변수 | 값 |\n"
        "|------|-----|\n"
        "| key_valid | true |\n"
        f"| smoke_state | {smoke_state} |\n"
        f"| smoke_exit | {smoke_exit} |\n"
    )


def _rebalance_micro(*, latest_signal: str = "INTENT_LOSS") -> str:
    return (
        "## 라이브 전 전략 의도 게이트\n"
        "```json\n"
        + _json(
            {
                "ok": False,
                "reason": "latest_intent_loss",
                "verdict": "INSUFFICIENT_DATA",
                "latest_signal": latest_signal,
                "next_action_ko": "실주문을 멈추고 forward 토너먼트·전략 검토 증거를 확인합니다.",
            }
        )
        + "\n```\n"
    )


def _released() -> str:
    return _json(
        {
            "released_work": [
                {
                    "candidate_id": COMPLETED_CANDIDATE_ID,
                    "status": "released",
                    "reason_ko": "스펙 103 완료",
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
        "pipeline-liveness": _markdown_json({"overall": "OK", "checks": []}),
        "released-work": _released(),
        "capital-path-readiness": _capital(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.gate_id: gate.status for gate in report.quality_gates}


def test_ready_report_classifies_apbk1672_and_preserves_no_retry_boundary():
    report = build_broker_rejection_taxonomy_report(
        _evidence(),
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
    assert report.released_work_summary["completed_candidate_released"] is True
    assert report.capital_path_summary["live_money_status"] == "PREVIEW_ONLY"
    assert report.capital_path_summary["money_path_mutation"] is False

    row = report.taxonomy[0]
    assert row.signature == "APBK1672"
    assert row.taxonomy_key == "kis_order_response_rejection"
    assert row.count == 2
    assert row.confidence == "HIGH"
    assert row.recurrence_risk == "OBSERVED_RECURRENT"
    assert row.action_category == ACTION_NO_AUTO_RETRY
    assert report.live_intent_context["blocks_live_orders"] is True
    assert "no orders" in report.safety_invariants
    assert "브로커 거부 분류" in report.as_markdown()


def test_unknown_kis_code_is_classified_without_overclaiming_outage():
    report = build_broker_rejection_taxonomy_report(
        _evidence(**{"execution-quality": _execution_quality(codes={"ZZ9999": 1})}),
        now=NOW,
    )

    assert report.overall_status == CONTRACT_READY
    assert report.taxonomy[0].signature == "ZZ9999"
    assert report.taxonomy[0].taxonomy_key == "unknown_broker_response"
    assert "전체 브로커 장애" not in report.taxonomy[0].reason_ko


def test_missing_execution_quality_blocks_contract():
    report = build_broker_rejection_taxonomy_report(
        _evidence(**{"execution-quality": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["required_evidence_parse"] == GATE_FAIL
    assert _gates(report)["broker_rejection_evidence"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["execution-quality"].parse_status == "missing"


def test_no_rejections_waits_without_suggesting_retry():
    report = build_broker_rejection_taxonomy_report(
        _evidence(
            **{
                "execution-quality": _execution_quality(
                    rejected_orders=0,
                    parsed_broker_errors=0,
                    codes={},
                )
            }
        ),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["broker_rejection_evidence"] == GATE_WAIT
    assert _gates(report)["taxonomy_classification"] == GATE_WAIT
    assert report.taxonomy == ()


def test_kis_smoke_failure_waits_even_with_classified_rejection():
    report = build_broker_rejection_taxonomy_report(
        _evidence(
            **{
                "execution-quality": _execution_quality(smoke_state="failed"),
                "kis-smoke": _kis_smoke(smoke_state="failed", smoke_exit=1),
            }
        ),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["kis_smoke_health"] == GATE_WAIT
    assert report.broker_smoke_summary["healthy"] is False
