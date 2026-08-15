"""스펙 135 — 자산 간 상대가치 no-live 계약 코어 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.broad_no_edge_cross_asset_relative_value import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    NEXT_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_broad_no_edge_cross_asset_relative_value,
)

NOW = datetime(2026, 8, 15, 6, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _fenced(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _forward(*, include_duration: bool = True, include_commodity: bool = True) -> str:
    rows = [
        {
            "key": "multiasset",
            "label": "멀티에셋 분산 추세",
            "verdict": "NO_EDGE",
            "n_obs": 44,
            "rank": 1,
            "psr_vs_benchmark": "0.763517",
            "sharpe": "3.019443",
            "calmar": "49.787433",
            "universe": ["SPY", "IEF"],
        },
        {
            "key": "rmbeta",
            "label": "위험관리 베타",
            "verdict": "NO_EDGE",
            "n_obs": 44,
            "rank": 2,
            "psr_vs_benchmark": "0.739027",
            "sharpe": "2.586885",
            "calmar": "37.425697",
            "universe": ["SPY", "QQQ"],
        },
        {
            "key": "global",
            "label": "글로벌 분산 추세",
            "verdict": "NO_EDGE",
            "n_obs": 44,
            "rank": 4,
            "psr_vs_benchmark": "0.579446",
            "sharpe": "1.899467",
            "calmar": "10.898148",
            "universe": ["SPY", "IEF", "GLD"],
        },
    ]
    if not include_duration:
        for row in rows:
            row["universe"] = [symbol for symbol in row["universe"] if symbol != "IEF"]
    if not include_commodity:
        for row in rows:
            row["universe"] = [symbol for symbol in row["universe"] if symbol != "GLD"]
    return "# forward\n\n## 리더보드 결정 JSON\n\n" + _fenced({"rows": rows})


def _public_data(*, cash_ready: bool = True) -> str:
    items = [
        {"kind": "treasury", "id": "UST2Y", "ok": cash_ready, "rows": 2405},
        {"kind": "treasury", "id": "UST10Y", "ok": cash_ready, "rows": 2405},
        {"kind": "cboe", "id": "VIX", "ok": True, "rows": 9251},
        {"kind": "bls", "id": "CUUR0000SA0", "ok": True, "rows": 31},
        {"kind": "fred", "id": "DGS2", "ok": cash_ready, "rows": 13098},
        {"kind": "fred", "id": "DGS10", "ok": cash_ready, "rows": 16858},
        {"kind": "dbnomics", "id": "FED/H15/RIFLGFCY02_N.B", "ok": True, "rows": 13098},
        {"kind": "dbnomics", "id": "FED/H15/RIFLGFCY10_N.B", "ok": True, "rows": 16858},
    ]
    return _json(
        {
            "schema_version": "2.0",
            "overall_ok": True,
            "published": len(items),
            "total_items": len(items),
            "items": items,
        }
    )


def _regime() -> str:
    payload = {
        "schema_version": "1.0",
        "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적)",
        "total_return_days": 753,
        "by_label": {
            "CAUTION": {"n_days": 433, "total_return_pct": "11.76"},
            "RISK_OFF": {"n_days": 7, "total_return_pct": "0.10"},
            "RISK_ON": {"n_days": 313, "total_return_pct": "21.91"},
        },
    }
    return "# 레짐 층화\n\n```text\n--- stratified json ---\n" + json.dumps(
        payload,
        ensure_ascii=False,
    ) + "\n```\n"


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
                "spec_id": "135-broad-no-edge-cross-asset-relative-value",
            }
        )
    return _json({"overall_status": "OK", "released_work": released})


def _pipeline(overall: str = "OK") -> str:
    return _fenced(
        {
            "overall": overall,
            "checks": [
                {"key": "rebalance-paper-forward", "status": overall},
                {"key": "collect-public-data", "status": "OK"},
                {"key": "regime-stratify", "status": "OK"},
            ],
        }
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence: dict[str, str | None] = {
        "rebalance-paper-forward": _forward(),
        "public-data-summary": _public_data(),
        "regime-stratify": _regime(),
        "money-path": _money_path(),
        "edge-autoarm": _edge_autoarm(),
        "released-work": _released(),
        "pipeline-liveness": _pipeline(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.gate_id: gate.status for gate in report.validation_gates}


def test_current_evidence_emits_cross_asset_relative_value_contract():
    report = build_broad_no_edge_cross_asset_relative_value(
        _evidence(),
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    payload = report.to_dict()
    assert payload["contract_id"] == "broad-no-edge-cross-asset-relative-value"
    assert payload["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert payload["next_candidate_id"] == NEXT_CANDIDATE_ID
    assert payload["overall_status"] == CONTRACT_READY
    assert payload["run_id"] == "123"
    assert payload["commit"] == "abc123"
    assert len(payload["forward_tracks"]) == 3
    assert payload["cash_proxy_snapshot"]["available"] is True
    assert "no orders" in payload["safety_boundary"]
    assert "자산 간 상대가치 no-live 실험 계약" in report.as_markdown()
    assert _gates(report)["relative-value-lane-coverage"] == "PASS"


def test_missing_forward_sidecar_blocks_contract():
    report = build_broad_no_edge_cross_asset_relative_value(
        _evidence(**{"rebalance-paper-forward": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["input-evidence"] == "FAIL"


def test_missing_cash_proxy_keeps_contract_waiting():
    report = build_broad_no_edge_cross_asset_relative_value(
        _evidence(**{"public-data-summary": _public_data(cash_ready=False)}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["cash-proxy-availability"] == "WAIT"
    cash_lane = {
        lane.lane_id: lane.status for lane in report.relative_value_lanes
    }["cash_proxy_hurdle"]
    assert cash_lane == "WAIT"


def test_released_work_without_candidate_leaves_observation_wait():
    report = build_broad_no_edge_cross_asset_relative_value(
        _evidence(**{"released-work": _released(include_candidate=False)}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["released-work-closure"] == "WAIT"


def test_live_capable_money_path_keeps_contract_waiting():
    report = build_broad_no_edge_cross_asset_relative_value(
        _evidence(
            **{
                "money-path": _money_path(status="ARMED", can_submit=True),
                "edge-autoarm": _edge_autoarm("ARM"),
            }
        ),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["money-gate-alignment"] == "WAIT"
