"""스펙 105 - 브로커 진단 생존성 계약 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.broker_diagnostic_liveness import (
    BLOCKED,
    BROKER_DIAGNOSTIC_LIVE,
    BROKER_DIAGNOSTIC_OBSERVATION_WAIT,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_broker_diagnostic_liveness_report,
)

NOW = datetime(2026, 7, 8, 1, 30, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _kis_smoke(
    *,
    state: str = "success",
    exit_code: int = 0,
    key_valid: bool | None = True,
    tests_failed: int = 0,
) -> str:
    key_value = "" if key_valid is None else str(key_valid).lower()
    return "\n".join(
        [
            "# KIS smoke",
            "",
            "| 변수 | 값 |",
            "|------|-----|",
            "| secrets_present | true |",
            f"| key_valid | {key_value} |",
            f"| smoke_state | {state} |",
            f"| smoke_exit | {exit_code} |",
            "| tests_total | 4 |",
            f"| tests_failed | {tests_failed} |",
            "| timestamp_utc | 2026-07-07T06:48:04Z |",
            "",
        ]
    )


def _execution_quality(broker_smoke: dict | None = None) -> str:
    payload = {
        "overall_status": "OBSERVE",
        "live_gate": {
            "ok": False,
            "reason": "latest_intent_loss",
            "verdict": "INSUFFICIENT_DATA",
            "latest_signal": "INTENT_LOSS",
        },
    }
    if broker_smoke is not None:
        payload["broker_smoke"] = broker_smoke
    return _markdown_json(payload)


def _broker_smoke(**overrides) -> dict:
    payload = {
        "key_valid": True,
        "smoke_state": "success",
        "smoke_exit": 0,
        "tests_total": 4,
        "tests_failed": 0,
        "timestamp_utc": "2026-07-07T06:48:04Z",
    }
    payload.update(overrides)
    return payload


def _pipeline(*, kis_status: str = "OK", execution_status: str = "OK") -> str:
    return _markdown_json(
        {
            "overall": "OK",
            "checks": [
                {
                    "key": "kis-smoke",
                    "status": kis_status,
                    "critical": True,
                    "age_hours": 5.4,
                    "max_age_hours": 30,
                    "timestamp_utc": "2026-07-07T06:48:04Z",
                },
                {
                    "key": "execution-quality",
                    "status": execution_status,
                    "critical": False,
                    "age_hours": 5.4,
                    "max_age_hours": 30,
                    "timestamp_utc": "2026-07-07T06:48:20Z",
                },
            ],
        }
    )


def _released() -> str:
    return _json(
        {
            "released_work": [
                {
                    "candidate_id": COMPLETED_CANDIDATE_ID,
                    "status": "released",
                    "reason_ko": "스펙 105 완료",
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
        "kis-smoke": _kis_smoke(),
        "execution-quality": _execution_quality(_broker_smoke()),
        "pipeline-liveness": _pipeline(),
        "released-work": _released(),
        "capital-path-readiness": _capital(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.gate_id: gate.status for gate in report.quality_gates}


def test_ready_report_requires_kis_execution_quality_and_pipeline_liveness():
    report = build_broker_diagnostic_liveness_report(
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
    assert report.diagnostic_summary["diagnostic_state"] == BROKER_DIAGNOSTIC_LIVE
    assert report.diagnostic_summary["kis_smoke_success"] is True
    assert report.diagnostic_summary["execution_quality_smoke_success"] is True
    assert report.released_work_summary["completed_candidate_released"] is True
    assert report.capital_path_summary["money_path_mutation"] is False
    assert "no orders" in report.safety_invariants
    assert "브로커 진단 생존성 요약" in report.as_markdown()


def test_missing_execution_quality_broker_smoke_waits_without_blocking():
    report = build_broker_diagnostic_liveness_report(
        _evidence(**{"execution-quality": _execution_quality(None)}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert report.diagnostic_summary["diagnostic_state"] == BROKER_DIAGNOSTIC_OBSERVATION_WAIT
    assert _gates(report)["execution_quality_broker_smoke"] == GATE_WAIT
    assert _gates(report)["kis_smoke_health"] == GATE_PASS


def test_failed_kis_smoke_blocks_contract():
    report = build_broker_diagnostic_liveness_report(
        _evidence(**{"kis-smoke": _kis_smoke(state="failed", exit_code=1, tests_failed=1)}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["kis_smoke_health"] == GATE_FAIL


def test_invalid_kis_key_blocks_contract():
    report = build_broker_diagnostic_liveness_report(
        _evidence(**{"kis-smoke": _kis_smoke(key_valid=False)}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["kis_smoke_health"] == GATE_FAIL


def test_stale_pipeline_for_relevant_diagnostic_blocks_contract():
    report = build_broker_diagnostic_liveness_report(
        _evidence(**{"pipeline-liveness": _pipeline(kis_status="STALE")}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["pipeline_broker_diagnostic_liveness"] == GATE_FAIL


def test_missing_required_evidence_blocks_contract():
    report = build_broker_diagnostic_liveness_report(
        _evidence(**{"execution-quality": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["required_evidence_parse"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["execution-quality"].parse_status == "missing"


def test_missing_pipeline_relevant_check_waits_when_overall_is_ok():
    report = build_broker_diagnostic_liveness_report(
        _evidence(
            **{
                "pipeline-liveness": _markdown_json(
                    {
                        "overall": "OK",
                        "checks": [
                            {"key": "kis-smoke", "status": "OK", "critical": True}
                        ],
                    }
                )
            }
        ),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["pipeline_broker_diagnostic_liveness"] == GATE_WAIT
