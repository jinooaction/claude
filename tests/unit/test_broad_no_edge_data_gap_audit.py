"""스펙 133 — 광역 no-edge 데이터 결측 감사 계약 코어 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.broad_no_edge_data_gap_audit import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_broad_no_edge_data_gap_audit,
)

NOW = datetime(2026, 8, 12, 13, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _fenced(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _public_data_summary(*, overall_ok: bool = False) -> str:
    return _json(
        {
            "schema_version": "2.0",
            "as_of": "2026-08-12",
            "overall_ok": overall_ok,
            "published": 10,
            "total_items": 11,
            "cross_checks": [
                {
                    "pair": "bls:CUUR0000SA0 vs dbnomics:BLS/cu/CUUR0000SA0",
                    "kind": "levels",
                    "status": "SKIPPED",
                    "detail": (
                        "교차 검증 입력 미발행 "
                        "(bls:CUUR0000SA0: 없음, dbnomics:BLS/cu/CUUR0000SA0: 있음)"
                    ),
                },
                {
                    "pair": "treasury:UST10Y vs fred:DGS10",
                    "kind": "levels",
                    "status": "PASS",
                    "overlap": 2401,
                    "agree_pct": "100.00",
                },
            ],
            "items": [
                {
                    "kind": "treasury",
                    "id": "UST10Y2Y",
                    "derived": True,
                    "ok": True,
                    "rows": 2402,
                    "first_date": "2017-01-03",
                    "last_date": "2026-08-11",
                    "missing": 0,
                    "issues": [],
                    "published": "treasury/UST10Y2Y.csv",
                },
                {
                    "kind": "cboe",
                    "id": "VIX",
                    "ok": True,
                    "rows": 9248,
                    "first_date": "1990-01-02",
                    "last_date": "2026-08-11",
                    "missing": 0,
                    "issues": [],
                    "published": "cboe/VIX.csv",
                },
                {
                    "kind": "bls",
                    "id": "CUUR0000SA0",
                    "ok": False,
                    "rows": 30,
                    "first_date": "2024-01-01",
                    "last_date": "2026-06-01",
                    "missing": 1,
                    "issues": ["신선도 위반: 마지막 관측 2026-06-01 이 72일 전"],
                },
            ],
        }
    )


def _regime() -> str:
    return _json(
        {
            "schema_version": "1.0",
            "as_of": "2026-08-12",
            "indicators": {
                "yield_curve": {
                    "status": "OK",
                    "state": "FLAT",
                    "source": "treasury/UST10Y2Y.csv",
                },
                "vix": {"status": "OK", "state": "NORMAL", "source": "cboe/VIX.csv"},
                "inflation": {
                    "status": "UNAVAILABLE",
                    "reason": "파일 없음: bls/CUUR0000SA0.csv (해당 항목 미발행)",
                    "source": "bls/CUUR0000SA0.csv",
                },
                "sahm": {"status": "OK", "state": "QUIET", "source": "bls/LNS14000000.csv"},
            },
            "overall": {
                "label": "RISK_ON",
                "available_indicators": 3,
                "total_indicators": 4,
            },
        }
    )


def _timeline(*, missing_canonical: bool = False) -> str:
    rows = ["date,label,flags,available,spread,vix,inflation_yoy,sahm_pp"]
    labels = ("RISK_ON", "CAUTION") if missing_canonical else ("RISK_ON", "CAUTION", "RISK_OFF")
    for index in range(30):
        label = labels[index % len(labels)]
        sahm = "" if index < 10 else "0.30"
        rows.append(
            f"2026-01-{index + 1:02d},{label},,2,1.20,12.00,,{sahm}"
        )
    return "\n".join(rows) + "\n"


def _regime_window(risk_off_days: int = 7) -> dict:
    return {
        "schema_version": "1.0",
        "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적)",
        "total_return_days": 750,
        "by_label": {
            "CAUTION": {"n_days": 430, "total_return_pct": "11.61", "sharpe": "0.85"},
            "RISK_OFF": {"n_days": risk_off_days, "total_return_pct": "0.10"},
            "RISK_ON": {"n_days": 313, "total_return_pct": "21.91", "sharpe": "1.85"},
        },
        "all": {"n_days": 750},
    }


def _stratify(risk_off_days: int = 7) -> str:
    return (
        "# 레짐 층화\n\n"
        "## GLOBAL-TREND\n\n"
        "```\n--- stratified json ---\n"
        + json.dumps(_regime_window(risk_off_days), ensure_ascii=False, indent=2)
        + "\n```\n"
    )


def _forward() -> str:
    return (
        "# forward\n\n## 리더보드 결정 JSON\n\n"
        + _fenced(
            {
                "rows": [
                    {
                        "key": "global",
                        "label": "글로벌 분산 추세",
                        "verdict": "NO_EDGE",
                        "n_obs": 41,
                        "rank": 4,
                        "is_incumbent": True,
                    }
                ]
            }
        )
    )


def _money_path(*, status: str = "PREVIEW_ONLY", can_submit: bool = False) -> str:
    return _fenced(
        {
            "stage": "NO_EDGE_YET",
            "live_money_state": {
                "status": status,
                "can_submit_real_orders": can_submit,
            },
        }
    )


def _edge_autoarm(action: str = "WAIT_EDGE") -> str:
    return _fenced({"action": action, "reason": "forward 판정='NO_EDGE'"})


def _released(*, include_candidate: bool = True) -> str:
    released = []
    if include_candidate:
        released.append(
            {
                "candidate_id": COMPLETED_CANDIDATE_ID,
                "status": "released",
                "spec_id": "133-broad-no-edge-data-gap-audit",
            }
        )
    return _json({"overall_status": "OK", "released_work": released})


def _pipeline(overall: str = "OK") -> str:
    return _fenced(
        {
            "overall": overall,
            "checks": [
                {"key": "collect-public-data", "status": "OK"},
                {"key": "regime-stratify", "status": "OK"},
            ],
        }
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence: dict[str, str | None] = {
        "public-data-last-run": _fenced({"overall_ok": False, "published": 10}),
        "public-data-summary": _public_data_summary(),
        "public-data-regime": _regime(),
        "public-data-regime-timeline": _timeline(),
        "regime-stratify": _stratify(),
        "rebalance-paper-forward": _forward(),
        "money-path": _money_path(),
        "edge-autoarm": _edge_autoarm(),
        "released-work": _released(),
        "pipeline-liveness": _pipeline(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.gate_id: gate.status for gate in report.validation_gates}


def test_current_style_evidence_classifies_data_gap_causes():
    report = build_broad_no_edge_data_gap_audit(
        _evidence(),
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == CONTRACT_READY
    assert report.run_id == "123"
    assert report.commit == "abc123"
    assert report.completed_candidate_id == COMPLETED_CANDIDATE_ID
    assert report.next_candidate_id == NEXT_CANDIDATE_ID
    assert "no broker API call" in report.safety_boundary
    assert set(_gates(report).values()) == {GATE_PASS}

    gaps = {gap.item_id: gap for gap in report.public_data_gaps}
    assert gaps["CUUR0000SA0"].gap_status == "GAP_DETECTED"
    assert "not_published" in gaps["CUUR0000SA0"].gap_causes
    assert gaps["CUUR0000SA0"].no_edge_impact == "MEDIUM"
    assert gaps["UST10Y2Y"].gap_status == "DATA_READY"

    checks = {gap.pair: gap for gap in report.cross_check_gaps}
    assert (
        checks["bls:CUUR0000SA0 vs dbnomics:BLS/cu/CUUR0000SA0"].gap_cause
        == "SKIPPED_MISSING_INPUT"
    )

    indicators = {gap.indicator: gap for gap in report.regime_indicator_gaps}
    assert indicators["inflation"].gap_cause == "INDICATOR_UNAVAILABLE"
    assert indicators["inflation"].no_edge_impact == "MEDIUM"

    assert report.timeline_gap_summary["canonical_labels_missing"] == []
    assert report.timeline_gap_summary["missing_column_pcts"]["inflation_yoy"] == 100.0
    assert "GLOBAL-TREND:RISK_OFF" in report.stratified_join_summary["sparse_labels"]
    assert report.forward_no_edge_summary["no_edge_count"] == 1

    payload = report.to_dict()
    assert payload["audit_id"] == "broad-no-edge-data-gap-audit"
    assert len(payload["evidence_surfaces"]) == 10
    assert "데이터 결측 원인 감사" in report.as_markdown()


def test_missing_public_data_summary_blocks_contract():
    report = build_broad_no_edge_data_gap_audit(
        _evidence(**{"public-data-summary": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["input-evidence"] == GATE_FAIL
    surfaces = {surface.key: surface for surface in report.evidence_surfaces}
    assert surfaces["public-data-summary"].parse_status == "missing"


def test_missing_canonical_timeline_label_waits():
    report = build_broad_no_edge_data_gap_audit(
        _evidence(**{"public-data-regime-timeline": _timeline(missing_canonical=True)}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["timeline-label-coverage"] == GATE_WAIT
    assert report.timeline_gap_summary["canonical_labels_missing"] == ["RISK_OFF"]
    causal = {finding.finding_id: finding for finding in report.causal_findings}
    assert causal["timeline_label_coverage"].impact == "HIGH"


def test_money_path_live_like_state_waits_without_opening_orders():
    report = build_broad_no_edge_data_gap_audit(
        _evidence(
            **{
                "money-path": _money_path(status="ARMED", can_submit=True),
                "edge-autoarm": _edge_autoarm(action="ARM"),
            }
        ),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["money-gate-alignment"] == GATE_WAIT
    assert "no orders" in report.safety_boundary


def test_malformed_timeline_blocks_contract():
    malformed_timeline = "date,label\n2026-01-02,RISK_ON\n2026-01-01,CAUTION\n"
    report = build_broad_no_edge_data_gap_audit(
        _evidence(**{"public-data-regime-timeline": malformed_timeline}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["timeline-label-coverage"] == GATE_FAIL
    assert report.timeline_gap_summary["out_of_order_dates"] == ["2026-01-01"]
