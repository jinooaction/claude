"""스펙 137 — 변동성 목표·낙폭 제어 no-live 계약 코어 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.broad_no_edge_vol_target_drawdown import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    NEXT_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_broad_no_edge_vol_target_drawdown,
)

NOW = datetime(2026, 8, 15, 7, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _fenced(payload: dict) -> str:
    return "## 결정 JSON\n\n```json\n" + _json(payload) + "\n```\n"


def _forward(*, include_material_drawdown: bool = True) -> str:
    drawdown = "19.890290" if include_material_drawdown else "4.000000"
    rows = [
        {
            "key": "multiasset",
            "label": "멀티에셋 분산 추세",
            "verdict": "NO_EDGE",
            "n_obs": 44,
            "rank": 1,
            "psr_vs_benchmark": "0.763517",
            "calmar": "49.787433",
            "max_drawdown_pct": drawdown,
            "universe_size": 2,
            "universe": ["SPY", "IEF"],
        },
        {
            "key": "global",
            "label": "글로벌 분산 추세",
            "verdict": "NO_EDGE",
            "n_obs": 44,
            "rank": 2,
            "psr_vs_benchmark": "0.579446",
            "calmar": "10.898148",
            "max_drawdown_pct": "11.595110" if include_material_drawdown else "3.000000",
            "universe_size": 3,
            "universe": ["SPY", "IEF", "GLD"],
        },
        {
            "key": "wide",
            "label": "글로벌 분산 추세 확대",
            "verdict": "NO_EDGE",
            "n_obs": 44,
            "rank": 3,
            "psr_vs_benchmark": "0.491499",
            "calmar": "1.389891",
            "max_drawdown_pct": "13.600883" if include_material_drawdown else "2.000000",
            "universe_size": 11,
            "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD"],
        },
    ]
    return "# forward\n\n## 리더보드 결정 JSON\n\n" + _fenced({"rows": rows})


def _regime(*, include_drawdown: bool = True) -> str:
    worst = "-4.09" if include_drawdown else "-0.50"
    caution_dd = "6.47" if include_drawdown else "1.00"
    payload = {
        "schema_version": "1.0",
        "total_return_days": 753,
        "by_label": {
            "CAUTION": {
                "n_days": 433,
                "total_return_pct": "11.76",
                "worst_day_pct": "-2.18" if include_drawdown else "-0.30",
                "max_drawdown_pct": caution_dd,
                "sharpe": "0.86",
            },
            "RISK_OFF": {
                "n_days": 7 if include_drawdown else 0,
                "total_return_pct": "0.10",
                "worst_day_pct": "-0.59",
                "max_drawdown_pct": "0.59",
            },
            "RISK_ON": {
                "n_days": 313,
                "total_return_pct": "21.91",
                "worst_day_pct": worst,
                "max_drawdown_pct": "6.97" if include_drawdown else "1.00",
                "sharpe": "1.85",
            },
        },
    }
    return "# 레짐 층화\n\n```text\n--- stratified json ---\n" + _json(payload) + "\n```\n"


def _execution() -> str:
    return _fenced(
        {
            "overall_status": "OBSERVE",
            "latest_signal": "INTENT_LOSS",
            "cumulative_pnl_usd": "-1.14",
            "broker_rejections": {"rejected_orders": 2},
            "broker_smoke": {"smoke_state": "success"},
        }
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
                "spec_id": "137-broad-no-edge-vol-target-drawdown",
            }
        )
    return _json({"overall_status": "OK", "released_work": released})


def _pipeline(overall: str = "OK") -> str:
    return _fenced(
        {
            "overall": overall,
            "checks": [
                {"key": "rebalance-paper-forward", "status": overall},
                {"key": "regime-stratify", "status": "OK"},
                {"key": "execution-quality", "status": "OK"},
            ],
        }
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence: dict[str, str | None] = {
        "rebalance-paper-forward": _forward(),
        "regime-stratify": _regime(),
        "execution-quality": _execution(),
        "money-path": _money_path(),
        "edge-autoarm": _edge_autoarm(),
        "released-work": _released(),
        "pipeline-liveness": _pipeline(),
    }
    evidence.update(overrides)
    return evidence


def _gates(report) -> dict[str, str]:
    return {gate.gate_id: gate.status for gate in report.validation_gates}


def test_current_evidence_emits_vol_target_drawdown_contract():
    report = build_broad_no_edge_vol_target_drawdown(
        _evidence(),
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    payload = report.to_dict()
    assert payload["contract_id"] == "broad-no-edge-vol-target-drawdown"
    assert payload["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert payload["next_candidate_id"] == NEXT_CANDIDATE_ID
    assert payload["overall_status"] == CONTRACT_READY
    assert payload["drawdown_evidence_profile"]["drawdown_labels"]
    assert len(payload["drawdown_lanes"]) == 5
    assert "no orders" in payload["safety_boundary"]
    assert "변동성 목표·낙폭 제어 no-live 실험 계약" in report.as_markdown()
    assert _gates(report)["drawdown-lane-coverage"] == "PASS"


def test_missing_forward_sidecar_blocks_contract():
    report = build_broad_no_edge_vol_target_drawdown(
        _evidence(**{"rebalance-paper-forward": None}),
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    assert _gates(report)["input-evidence"] == "FAIL"


def test_missing_drawdown_context_keeps_contract_waiting():
    report = build_broad_no_edge_vol_target_drawdown(
        _evidence(
            **{
                "rebalance-paper-forward": _forward(include_material_drawdown=False),
                "regime-stratify": _regime(include_drawdown=False),
            }
        ),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["drawdown-risk-context"] == "WAIT"


def test_released_work_without_candidate_leaves_observation_wait():
    report = build_broad_no_edge_vol_target_drawdown(
        _evidence(**{"released-work": _released(include_candidate=False)}),
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    assert _gates(report)["released-work-closure"] == "WAIT"


def test_live_capable_money_path_keeps_contract_waiting():
    report = build_broad_no_edge_vol_target_drawdown(
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
