"""스펙 100 — 레짐 타임라인 커버리지 계약 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from auto_invest.analytics.regime_timeline_coverage import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_DATA_EVIDENCE_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_regime_timeline_coverage_report,
)

NOW = datetime(2026, 7, 6, 13, 30, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _markdown_json(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _timeline(labels: tuple[str, ...] | None = None) -> str:
    labels = labels or ("RISK_ON", "CAUTION", "RISK_OFF")
    rows = ["date,label,flags,available"]
    current = date(2026, 1, 1)
    for label in labels:
        for _ in range(25):
            rows.append(f"{current.isoformat()},{label},,4")
            current += timedelta(days=1)
    return "\n".join(rows) + "\n"


def _stratified_payload(
    *,
    risk_off_days: int = 25,
    join_rule: str = "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
    total_return_days: int | None = None,
    label_counts: dict[str, int] | None = None,
) -> dict:
    counts = label_counts or {"CAUTION": 25, "RISK_OFF": risk_off_days, "RISK_ON": 25}
    total = total_return_days if total_return_days is not None else sum(counts.values())
    return {
        "schema_version": "1.0",
        "join_rule": join_rule,
        "total_return_days": total,
        "by_label": {
            label: {"n_days": n_days, "total_return_pct": "1.0"}
            for label, n_days in counts.items()
        },
        "all": {"n_days": total},
        "note": "연구 전용 — 라이브 매매 신호 아님",
    }


def _stratify(*payloads: dict) -> str:
    if not payloads:
        payloads = (_stratified_payload(),)
    sections = []
    for index, payload in enumerate(payloads, start=1):
        name = "GLOBAL-TREND" if index == 1 else "GLOBAL-TREND-WIDE"
        sections.append(
            f"## {name}\n\n"
            "```\n"
            "regime stratify: 수익률 75일 — d일 라벨 ↔ d+1 거래일 수익률\n"
            "--- stratified json ---\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n```\n"
        )
    return "\n".join(sections)


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
                    "reason_ko": "스펙 100 완료",
                }
            ]
        }
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence = {
        "public-data-regime-timeline": _timeline(),
        "regime-stratify": _stratify(
            _stratified_payload(),
            _stratified_payload(label_counts={"CAUTION": 25, "RISK_OFF": 25, "RISK_ON": 25}),
        ),
        "pipeline-liveness": _liveness(),
        "released-work": _released(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.key: gate.status for gate in report.quality_gates}


def test_ready_report_contains_contract_fields_and_safety_boundary():
    report = build_regime_timeline_coverage_report(
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
    assert report.timeline_summary["row_count"] == 75
    assert report.timeline_summary["canonical_labels_missing"] == []
    assert report.stratified_summary["section_count"] == 2
    assert report.stratified_summary["sparse_labels"] == []
    assert report.released_work_summary["completed_candidate_released"] is True
    assert "no broker API call" in report.safety_invariants

    payload = report.to_dict()
    assert payload["overall_status"] == CONTRACT_READY
    assert len(payload["evidence_surfaces"]) == 4
    assert len(payload["quality_gates"]) == 5
    assert "레짐 타임라인 커버리지 계약" in report.as_markdown()


def test_sparse_label_waits_without_blocking_forward_join():
    report = build_regime_timeline_coverage_report(
        _evidence(**{"regime-stratify": _stratify(_stratified_payload(risk_off_days=7))}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["stratified_observation_floor"] == GATE_WAIT
    assert _gates(report)["forward_join_quality"] == GATE_PASS
    assert report.stratified_summary["sparse_labels"] == ["GLOBAL-TREND:RISK_OFF"]


def test_missing_timeline_blocks_contract():
    report = build_regime_timeline_coverage_report(
        _evidence(**{"public-data-regime-timeline": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["timeline_shape"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["public-data-regime-timeline"].parse_status == "missing"


def test_malformed_timeline_shape_blocks_contract():
    bad_timeline = "date,label\n2026-01-03,RISK_ON\n2026-01-02,CAUTION\n2026-01-02,RISK_OFF\n"
    report = build_regime_timeline_coverage_report(
        _evidence(**{"public-data-regime-timeline": bad_timeline}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["timeline_shape"] == GATE_FAIL
    assert report.timeline_summary["duplicate_dates"] == ["2026-01-02"]
    assert report.timeline_summary["out_of_order_dates"] == ["2026-01-02"]


def test_missing_canonical_timeline_label_waits():
    report = build_regime_timeline_coverage_report(
        _evidence(**{"public-data-regime-timeline": _timeline(("RISK_ON", "CAUTION"))}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["timeline_label_coverage"] == GATE_WAIT
    assert report.timeline_summary["canonical_labels_missing"] == ["RISK_OFF"]


def test_missing_forward_join_rule_blocks_contract():
    report = build_regime_timeline_coverage_report(
        _evidence(
            **{
                "regime-stratify": _stratify(
                    _stratified_payload(join_rule="d일 라벨과 같은 날 수익률")
                )
            }
        ),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["forward_join_quality"] == GATE_FAIL
    assert report.stratified_summary["non_forward_sections"] == ["GLOBAL-TREND"]


def test_label_count_mismatch_blocks_contract():
    report = build_regime_timeline_coverage_report(
        _evidence(
            **{
                "regime-stratify": _stratify(
                    _stratified_payload(total_return_days=99)
                )
            }
        ),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["forward_join_quality"] == GATE_FAIL
    assert report.stratified_summary["count_mismatches"] == ["GLOBAL-TREND"]


def test_missing_stratified_json_blocks_contract():
    report = build_regime_timeline_coverage_report(
        _evidence(**{"regime-stratify": "# 레짐 층화\n\nno json here\n"}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["stratified_observation_floor"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["regime-stratify"].parse_status == "malformed"


def test_liveness_degradation_waits_without_hiding_data_quality():
    report = build_regime_timeline_coverage_report(
        _evidence(**{"pipeline-liveness": _liveness(stratify="STALE")}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["sidecar_liveness"] == GATE_WAIT
    assert report.liveness_summary["non_ok_checks"] == ["regime-stratify"]
