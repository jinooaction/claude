"""스펙 099 — 공개 데이터 입력 품질 계약 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.public_data_input_quality import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_DATA_EVIDENCE_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_public_data_input_quality_report,
)

NOW = datetime(2026, 7, 6, 12, 20, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _summary(**overrides) -> str:
    payload = {
        "schema_version": "2.0",
        "as_of": "2026-07-04",
        "overall_ok": True,
        "published": 3,
        "total_items": 3,
        "items": {
            "SPY": {"ok": True, "rows": 751},
            "IEF": {"ok": True, "rows": 751},
            "VIX": {"ok": True, "rows": 751},
        },
        "cross_checks": [
            {"name": "spy_vs_ief", "status": "PASS", "overlap_days": 751},
            {"name": "spy_vs_vix", "status": "PASS", "overlap_days": 751},
        ],
    }
    payload.update(overrides)
    return _json(payload)


def _regime(**overrides) -> str:
    payload = {
        "schema_version": "1.0",
        "as_of": "2026-07-04",
        "overall_label": "CAUTION",
        "available_indicators": 4,
        "total_indicators": 4,
        "indicators": {
            "yield_curve": {"status": "OK"},
            "vix": {"status": "OK"},
            "inflation": {"status": "OK"},
            "sahm": {"status": "OK"},
        },
    }
    payload.update(overrides)
    return _json(payload)


def _timeline(rows: int = 25) -> str:
    body = ["date,label", *[f"2026-01-{day:02d},CAUTION" for day in range(1, rows + 1)]]
    return "\n".join(body) + "\n"


def _stratify(days: int = 751) -> str:
    payload = {
        "schema_version": "1.0",
        "total_return_days": days,
        "labels": {"CAUTION": 431, "RISK_OFF": 7, "RISK_ON": 313},
    }
    return (
        "# 레짐 층화\n\n"
        "```\n"
        "regime stratify: 수익률 751일\n"
        "--- stratified json ---\n"
        + _json(payload)
        + "\n```\n"
    )


def _liveness(*, collect: str = "OK", stratify: str = "OK") -> str:
    return _markdown_json(
        {
            "overall": "OK",
            "checks": [
                {"key": "collect-public-data", "status": collect, "age_hours": 55.0},
                {"key": "regime-stratify", "status": stratify, "age_hours": 59.0},
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
                    "reason_ko": "스펙 099 완료",
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
        "public-data-last-run": _markdown_json(
            {"overall_ok": True, "published": 3, "total_items": 3}
        ),
        "public-data-summary": _summary(),
        "public-data-regime": _regime(),
        "public-data-regime-timeline": _timeline(),
        "regime-stratify": _stratify(),
        "pipeline-liveness": _liveness(),
        "released-work": _released(),
        "capital-path-readiness": _capital(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.key: gate.status for gate in report.quality_gates}


def test_ready_report_contains_contract_fields_and_safety_boundary():
    report = build_public_data_input_quality_report(
        _evidence(),
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == CONTRACT_READY
    assert report.run_id == "123"
    assert report.commit == "abc123"
    assert report.completed_candidate_id == COMPLETED_CANDIDATE_ID
    assert report.next_candidate_id == NEXT_DATA_EVIDENCE_CANDIDATE_ID
    assert set(_gates(report).values()) == {GATE_PASS}
    assert report.public_data_summary["published"] == 3
    assert report.regime_coverage_summary["total_return_days"] == 751
    assert report.released_work_summary["completed_candidate_released"] is True
    assert report.capital_path_summary["live_money_status"] == "PREVIEW_ONLY"
    assert report.capital_path_summary["money_path_mutation"] is False
    assert "no broker API call" in report.safety_invariants

    payload = report.to_dict()
    assert payload["overall_status"] == CONTRACT_READY
    assert len(payload["evidence_surfaces"]) == 8
    assert len(payload["quality_gates"]) >= 4
    assert "공개 데이터 입력 품질 계약" in report.as_markdown()


def test_missing_public_data_summary_blocks_contract():
    report = build_public_data_input_quality_report(
        _evidence(**{"public-data-summary": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["public_data_publication_completeness"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["public-data-summary"].parse_status == "missing"


def test_failed_cross_check_blocks_contract_even_when_publication_is_complete():
    summary = _summary(
        cross_checks=[
            {"name": "spy_vs_ief", "status": "PASS", "overlap_days": 751},
            {"name": "spy_vs_vix", "status": "FAIL", "overlap_days": 751},
        ]
    )

    report = build_public_data_input_quality_report(
        _evidence(**{"public-data-summary": summary}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["public_data_publication_completeness"] == GATE_PASS
    assert _gates(report)["public_data_cross_check_quality"] == GATE_FAIL
    assert report.public_data_summary["failed_cross_checks"] == ["spy_vs_vix"]


def test_liveness_degradation_waits_without_blocking_data_quality():
    report = build_public_data_input_quality_report(
        _evidence(**{"pipeline-liveness": _liveness(collect="STALE")}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["sidecar_liveness"] == GATE_WAIT
    assert report.liveness_summary["non_ok_checks"] == ["collect-public-data"]


def test_low_regime_stratify_coverage_waits_for_more_observations():
    report = build_public_data_input_quality_report(
        _evidence(**{"regime-stratify": _stratify(days=12)}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["regime_timeline_coverage"] == GATE_WAIT
    assert report.regime_coverage_summary["total_return_days"] == 12


def test_malformed_regime_summary_blocks_contract():
    report = build_public_data_input_quality_report(
        _evidence(**{"public-data-regime": "{not-json"}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["regime_timeline_coverage"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["public-data-regime"].parse_status == "malformed"
