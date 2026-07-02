from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.operator_status import (
    ALERT_ACTION_REQUIRED,
    ALERT_SILENT_OK,
    SEND_SENT,
    STATUS_ACTION_REQUIRED,
    STATUS_OK,
    build_operator_status,
)

NOW = datetime(2026, 7, 2, 9, 25, 0, tzinfo=UTC)


def _fenced(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```\n"


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        "pipeline-liveness": _fenced({"overall": "OK", "checks": []}),
        "money-path": _fenced(
            {
                "stage": "ACCUMULATING_EDGE",
                "blocking_gate": "전진 관측 부족: 14/20",
                "live_money_state": {"status": "PREVIEW_ONLY"},
            }
        ),
        "capital-path-readiness": json.dumps(
            {
                "readiness_state": "ACCUMULATING_EDGE",
                "live_money_status": "PREVIEW_ONLY",
                "blocking_gate": "전진 관측 부족: 14/20",
            },
            ensure_ascii=False,
        ),
        "money-gate-alignment": json.dumps(
            {
                "overall_status": "ALIGNED_WAITING",
                "next_action_ko": "전진 관측을 계속 누적한다.",
            },
            ensure_ascii=False,
        ),
        "autonomous-work-execution": json.dumps(
            {
                "overall_status": "EXECUTION_READY",
                "selected_work": {
                    "candidate_id": "candidate-e481b0309206",
                    "title_ko": "레짐·성과 분석을 후보 점수화 입력으로 승격",
                    "next_action_ko": "후보 점수화 입력을 구현한다.",
                },
            },
            ensure_ascii=False,
        ),
        "released-work": json.dumps(
            {
                "overall_status": "OK",
                "released_work": [{"candidate_id": "candidate-fd04772a23c5"}],
            },
            ensure_ascii=False,
        ),
    }
    base.update(overrides)
    return base


def test_ok_inputs_do_not_send_mobile_alert() -> None:
    report = build_operator_status(
        _evidence(),
        now=NOW,
        run_id="123",
        commit="abc123",
        dashboard_url="https://jinooaction.github.io/claude/status.html",
    )

    assert report.overall_status == STATUS_OK
    assert report.alert_decision.alert_level == ALERT_SILENT_OK
    assert report.alert_decision.should_send is False
    assert report.run_id == "123"
    assert report.commit == "abc123"
    assert any(section.key == "money" for section in report.dashboard_sections)


def test_pipeline_critical_requires_mobile_alert() -> None:
    report = build_operator_status(
        _evidence(**{"pipeline-liveness": _fenced({"overall": "CRITICAL", "checks": []})}),
        now=NOW,
        dashboard_url="https://example.test/status.html",
    )

    assert report.overall_status == "CRITICAL"
    assert report.alert_decision.should_send is True
    assert "pipeline-liveness" in report.alert_decision.message_ko
    assert "https://example.test/status.html" in report.alert_decision.message_ko


def test_money_gate_blocked_is_action_required() -> None:
    report = build_operator_status(
        _evidence(
            **{
                "money-gate-alignment": json.dumps(
                    {
                        "overall_status": "BLOCKED",
                        "next_action_ko": "pipeline-liveness workflow를 복구한다.",
                    },
                    ensure_ascii=False,
                )
            }
        ),
        now=NOW,
    )

    assert report.overall_status == STATUS_ACTION_REQUIRED
    assert report.alert_decision.alert_level == ALERT_ACTION_REQUIRED
    assert report.alert_decision.should_send is True
    assert "pipeline-liveness workflow를 복구한다" in report.next_action_ko


def test_missing_core_sidecar_is_action_required() -> None:
    report = build_operator_status(_evidence(**{"money-path": None}), now=NOW)

    assert report.overall_status == STATUS_ACTION_REQUIRED
    by_key = {surface.key: surface for surface in report.surfaces}
    assert by_key["money-path"].parse_status == "missing"
    assert by_key["money-path"].severity == "action"


def test_alert_message_masks_sensitive_values() -> None:
    report = build_operator_status(
        _evidence(
            **{
                "money-gate-alignment": json.dumps(
                    {
                        "overall_status": "BLOCKED",
                        "next_action_ko": "token secret-1234 chat_id 8783665778 확인",
                    },
                    ensure_ascii=False,
                )
            }
        ),
        now=NOW,
    )

    assert "secret-1234" not in report.alert_decision.message_ko
    assert "8783665778" not in report.alert_decision.message_ko


def test_report_with_send_status_updates_decision_only() -> None:
    report = build_operator_status(_evidence(), now=NOW)
    updated = report.with_send_status(SEND_SENT)

    assert updated.alert_decision.send_status == SEND_SENT
    assert report.alert_decision.send_status == "NOT_ATTEMPTED"


def test_deterministic_for_same_inputs() -> None:
    evidence = _evidence()

    first = build_operator_status(evidence, now=NOW).to_dict()
    second = build_operator_status(evidence, now=NOW).to_dict()

    assert first == second
