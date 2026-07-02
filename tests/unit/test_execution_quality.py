"""스펙 083 — 실행 품질 패키지 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.execution_quality import (
    OVERALL_MISSING_EVIDENCE,
    OVERALL_OBSERVE,
    build_execution_quality,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "execution_quality"
NOW = datetime(2026, 7, 2, 7, 30, 0, tzinfo=UTC)


def _fixture_evidence() -> dict[str, str]:
    return {path.stem: path.read_text(encoding="utf-8") for path in FIXTURES.glob("*.md")}


def test_builds_execution_quality_package_from_existing_sidecars() -> None:
    report = build_execution_quality(
        _fixture_evidence(),
        now=NOW,
        run_id="run-083",
        commit="abc1234",
    )
    payload = report.to_dict()

    assert payload["schema_version"] == "1.0"
    assert payload["run_id"] == "run-083"
    assert payload["commit"] == "abc1234"
    assert payload["overall_status"] == OVERALL_OBSERVE
    assert payload["opportunity_monitor"] == {
        "verdict": "INSUFFICIENT_DATA",
        "latest_signal": "INTENT_LOSS",
        "cumulative_pnl_usd": "-1.14",
        "valued_records": 1,
        "rejected_orders": 2,
        "valued_orders": 2,
        "latest_run_id": "28253047287",
        "next_action_ko": (
            "최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 "
            "쌓이지 않습니다."
        ),
    }
    assert payload["broker_rejections"]["rejected_orders"] == 2
    assert payload["broker_rejections"]["parsed_broker_errors"] == 2
    assert payload["broker_rejections"]["broker_error_observation_rate"] == "1.0000"
    assert payload["broker_rejections"]["kis_msg_codes"] == {"APBK1672": 2}
    assert payload["broker_smoke"]["smoke_state"] == "success"
    assert payload["broker_smoke"]["tests_total"] == 4
    assert payload["broker_smoke"]["tests_failed"] == 0
    assert payload["broker_smoke"]["smoke_error_rate"] == "0.0000"
    assert payload["live_gate"]["reason"] == "latest_intent_loss"
    assert payload["live_gate"]["ok"] is False


def test_markdown_is_read_only_and_omits_raw_broker_payload() -> None:
    report = build_execution_quality(_fixture_evidence(), now=NOW)
    text = report.as_markdown()

    assert "실행 품질 패키지" in text
    assert "읽기 전용" in text
    assert "주문, 자본, whitelist, caps, live 전략은 변경하지 않았습니다" in text
    assert "APBK1672" in text
    assert "request_summary" not in text
    assert "CANO" not in text


def test_missing_evidence_fails_open_without_trading_side_effects() -> None:
    report = build_execution_quality({}, now=NOW)
    payload = report.to_dict()

    assert payload["overall_status"] == OVERALL_MISSING_EVIDENCE
    assert payload["opportunity_monitor"]["verdict"] == "UNKNOWN"
    assert payload["broker_rejections"]["rejected_orders"] == 0
    assert payload["broker_smoke"]["present"] is False
    assert all(surface["parse_status"] == "missing" for surface in payload["evidence_surfaces"])


def test_unparseable_broker_reason_is_counted_without_failure() -> None:
    evidence = _fixture_evidence()
    history = json.loads(evidence["opportunity-history"])
    rows = history["records"][0]["opportunity_report"]["rows"]
    rows[1]["reason"] = "plain text broker rejection"
    evidence["opportunity-history"] = json.dumps(history, ensure_ascii=False)

    report = build_execution_quality(evidence, now=NOW)
    summary = report.to_dict()["broker_rejections"]

    assert summary["rejected_orders"] == 2
    assert summary["parsed_broker_errors"] == 1
    assert summary["unparsed_reasons"] == 1
    assert summary["broker_error_observation_rate"] == "0.5000"
