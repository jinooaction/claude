"""스펙 101 — 데이터 증거 생존성 계약 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.data_evidence_liveness import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_data_evidence_liveness_report,
)

NOW = datetime(2026, 7, 6, 13, 5, 0, tzinfo=UTC)
PUBLIC_DATA_TS = "2026-07-04T05:05:20Z"
REGIME_STRATIFY_TS = "2026-07-04T01:09:16Z"


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _last_run(timestamp: str) -> str:
    return (
        "# sidecar\n\n"
        "| 항목 | 값 |\n"
        "|------|-----|\n"
        f"| timestamp_utc | {timestamp} |\n"
    )


def _summary() -> str:
    return _json(
        {
            "schema_version": "2.0",
            "overall_ok": True,
            "published": 11,
            "total_items": 11,
            "items": {"SPY": {"ok": True}},
            "cross_checks": [{"name": "spy_vs_ief", "status": "PASS"}],
        }
    )


def _regime() -> str:
    return _json(
        {
            "schema_version": "1.0",
            "overall_label": "CAUTION",
            "available_indicators": 4,
            "total_indicators": 4,
            "indicators": {"yield_curve": {"status": "OK"}},
        }
    )


def _timeline() -> str:
    return "date,label\n2026-01-01,CAUTION\n"


def _liveness(
    *,
    collect: str = "OK",
    stratify: str = "OK",
    collect_ts: str | None = PUBLIC_DATA_TS,
    stratify_ts: str | None = REGIME_STRATIFY_TS,
    omit: set[str] | None = None,
    use_last_success: bool = False,
) -> str:
    omit = omit or set()
    checks = []
    for key, status, ts, age in (
        ("collect-public-data", collect, collect_ts, 55.9),
        ("regime-stratify", stratify, stratify_ts, 59.9),
    ):
        if key in omit:
            continue
        item = {
            "key": key,
            "status": status,
            "critical": False,
            "age_hours": age,
            "max_age_hours": 80.0,
        }
        if ts is not None:
            item["last_success_utc" if use_last_success else "timestamp_utc"] = ts
        checks.append(item)
    return _markdown_json({"schema_version": "1.0", "overall": "OK", "checks": checks})


def _released() -> str:
    return _json(
        {
            "released_work": [
                {
                    "candidate_id": COMPLETED_CANDIDATE_ID,
                    "status": "released",
                    "reason_ko": "스펙 101 완료",
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
        "public-data-last-run": _last_run(PUBLIC_DATA_TS),
        "public-data-summary": _summary(),
        "public-data-regime": _regime(),
        "public-data-regime-timeline": _timeline(),
        "regime-stratify": _last_run(REGIME_STRATIFY_TS),
        "pipeline-liveness": _liveness(),
        "released-work": _released(),
        "capital-path-readiness": _capital(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.key: gate.status for gate in report.quality_gates}


def test_ready_report_contains_contract_fields_and_safety_boundary():
    report = build_data_evidence_liveness_report(
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
    assert len(report.evidence_surfaces) == 8
    assert len(report.quality_gates) == 6
    assert {check.key for check in report.data_liveness_checks} == {
        "collect-public-data",
        "regime-stratify",
    }
    assert all(check.source_matches_pipeline for check in report.data_liveness_checks)
    assert report.released_work_summary["completed_candidate_released"] is True
    assert report.capital_path_summary["live_money_status"] == "PREVIEW_ONLY"
    assert report.capital_path_summary["money_path_mutation"] is False
    assert "no broker API call" in report.safety_invariants
    assert "데이터 증거 생존성 계약" in report.as_markdown()


def test_liveness_degradation_waits_without_blocking_auditable_sources():
    stale_liveness = _liveness(
        collect="STALE",
        collect_ts="2026-06-29T05:05:20Z",
    )
    report = build_data_evidence_liveness_report(
        _evidence(
            **{
                "public-data-last-run": _last_run("2026-06-29T05:05:20Z"),
                "pipeline-liveness": stale_liveness,
            }
        ),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["data_liveness_status"] == GATE_WAIT
    assert _gates(report)["source_timestamp_consistency"] == GATE_PASS
    assert _gates(report)["source_freshness"] == GATE_WAIT


def test_missing_pipeline_liveness_blocks_contract():
    report = build_data_evidence_liveness_report(
        _evidence(**{"pipeline-liveness": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["pipeline_report_parse"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["pipeline-liveness"].parse_status == "missing"


def test_missing_required_data_check_blocks_contract():
    report = build_data_evidence_liveness_report(
        _evidence(**{"pipeline-liveness": _liveness(omit={"regime-stratify"})}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["data_check_registration"] == GATE_FAIL
    checks = {check.key: check for check in report.data_liveness_checks}
    assert checks["regime-stratify"].status == "MISSING_CHECK"


def test_ok_check_without_source_timestamp_blocks_contract():
    report = build_data_evidence_liveness_report(
        _evidence(**{"public-data-last-run": "# no timestamp\n"}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["source_timestamp_consistency"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["public-data-last-run"].parse_status == "malformed"


def test_source_timestamp_mismatch_blocks_contract():
    report = build_data_evidence_liveness_report(
        _evidence(**{"regime-stratify": _last_run("2026-07-04T02:00:00Z")}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["source_timestamp_consistency"] == GATE_FAIL
    checks = {check.key: check for check in report.data_liveness_checks}
    assert checks["regime-stratify"].source_matches_pipeline is False


def test_last_success_timestamp_is_accepted_for_pipeline_check():
    report = build_data_evidence_liveness_report(
        _evidence(**{"pipeline-liveness": _liveness(use_last_success=True)}),
        now=NOW,
    )

    assert report.overall_status == CONTRACT_READY
    assert _gates(report)["source_timestamp_consistency"] == GATE_PASS


def test_malformed_pipeline_json_blocks_contract():
    report = build_data_evidence_liveness_report(
        _evidence(**{"pipeline-liveness": "## 결정 JSON\n\n```json\n{not-json}\n```\n"}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["pipeline_report_parse"] == GATE_FAIL
