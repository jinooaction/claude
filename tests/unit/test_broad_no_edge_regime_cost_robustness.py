"""스펙 132 — 광역 no-edge 레짐·비용 견고성 계약 코어 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.broad_no_edge_regime_cost_robustness import (
    BLOCKED,
    CONTRACT_READY,
    OBSERVATION_WAIT,
    build_broad_no_edge_regime_cost_robustness,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def _fenced(obj: dict) -> str:
    return "```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```"


def _regime_window(
    *,
    caution_sharpe: str = "0.85",
    risk_off_days: int = 7,
    risk_on_sharpe: str = "1.85",
) -> dict:
    return {
        "schema_version": "1.0",
        "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적)",
        "total_return_days": 750,
        "by_label": {
            "CAUTION": {
                "n_days": 430,
                "total_return_pct": "11.61",
                "max_drawdown_pct": "6.47",
                "sharpe": caution_sharpe,
            },
            "RISK_OFF": {
                "n_days": risk_off_days,
                "total_return_pct": "0.10",
                "max_drawdown_pct": "0.59",
                "note": f"관측 {risk_off_days}개 < 20개",
            },
            "RISK_ON": {
                "n_days": 313,
                "total_return_pct": "21.91",
                "max_drawdown_pct": "6.97",
                "sharpe": risk_on_sharpe,
            },
        },
        "all": {
            "n_days": 750,
            "total_return_pct": "36.21",
            "max_drawdown_pct": "9.60",
            "sharpe": "1.29",
        },
    }


def _regime_stratify(*, risk_off_days: int = 7) -> str:
    global_window = _regime_window(risk_off_days=risk_off_days)
    wide_window = _regime_window(
        caution_sharpe="0.70",
        risk_off_days=risk_off_days,
        risk_on_sharpe="1.98",
    )
    return (
        "# 레짐 층화\n\n"
        "## GLOBAL-TREND (3자산 SPY·IEF·GLD)\n\n"
        "```text\n--- stratified json ---\n"
        + json.dumps(global_window, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "## GLOBAL-TREND-WIDE (11 슬리브)\n\n"
        "```text\n--- stratified json ---\n"
        + json.dumps(wide_window, ensure_ascii=False, indent=2)
        + "\n```\n"
    )


def _execution_quality() -> str:
    return (
        "# 실행 품질 패키지\n\n## 결정 JSON\n\n"
        + _fenced(
            {
                "overall_status": "OBSERVE",
                "opportunity_monitor": {
                    "verdict": "INSUFFICIENT_DATA",
                    "latest_signal": "INTENT_LOSS",
                    "cumulative_pnl_usd": "-1.14",
                    "rejected_orders": 2,
                },
                "broker_rejections": {
                    "rejected_orders": 2,
                    "parsed_broker_errors": 2,
                    "broker_error_observation_rate": "1.0000",
                    "kis_msg_codes": {"APBK1672": 2},
                },
                "broker_smoke": {
                    "smoke_state": "success",
                    "tests_total": 5,
                    "tests_failed": 0,
                    "smoke_error_rate": "0.0000",
                },
                "live_gate": {"ok": False},
            }
        )
    )


def _money_path(*, can_submit: bool = False, status: str = "PREVIEW_ONLY") -> str:
    return (
        "# 돈 경로 상태\n\n## 결정 JSON\n\n"
        + _fenced(
            {
                "stage": "NO_EDGE_YET",
                "live_money_state": {
                    "status": status,
                    "can_submit_real_orders": can_submit,
                    "detail": "armed:false",
                },
            }
        )
    )


def _edge_autoarm(action: str = "WAIT_EDGE") -> str:
    return (
        "# 자본 사다리 게이트\n\n## 결정 JSON\n\n"
        + _fenced({"action": action, "reason": "forward 판정='NO_EDGE'"})
    )


def _forward_sidecar() -> str:
    return (
        "# forward\n\n## 리더보드 결정 JSON\n\n"
        + _fenced(
            {
                "schema_version": "1.0",
                "observation_health": "OK",
                "track_count": 2,
                "rows": [
                    {
                        "key": "global",
                        "label": "글로벌 분산 추세",
                        "verdict": "NO_EDGE",
                        "n_obs": 41,
                        "rank": 4,
                        "is_incumbent": True,
                    },
                    {
                        "key": "wide",
                        "label": "글로벌 분산 추세 확대",
                        "verdict": "NO_EDGE",
                        "n_obs": 41,
                        "rank": 7,
                        "is_incumbent": False,
                    },
                ],
            }
        )
    )


def _released(*, include_candidate: bool = True) -> str:
    released_work = []
    if include_candidate:
        released_work.append(
            {
                "candidate_id": (
                    "candidate-broad-no-edge-regime-cost-robustness-experiment"
                ),
                "status": "released",
                "spec_id": "132-broad-no-edge-regime-cost-robustness",
            }
        )
    return json.dumps(
        {"overall_status": "OK", "released_work": released_work},
        ensure_ascii=False,
    )


def _ledger(decision: str | None = None) -> str:
    entries = []
    if decision:
        entries.append(
            {
                "candidate_id": (
                    "candidate-broad-no-edge-regime-cost-robustness-experiment"
                ),
                "decision": decision,
            }
        )
    return json.dumps({"entries": entries}, ensure_ascii=False)


def _pipeline(overall: str = "OK") -> str:
    return "# 파이프라인 생존 감시\n\n## 결정 JSON\n\n" + _fenced(
        {"overall": overall, "checks": []}
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        "regime-stratify": _regime_stratify(),
        "execution-quality": _execution_quality(),
        "money-path": _money_path(),
        "edge-autoarm": _edge_autoarm(),
        "rebalance-paper-forward": _forward_sidecar(),
        "released-work": _released(),
        "evolution-ledger": _ledger(),
        "pipeline-liveness": _pipeline(),
    }
    base.update(overrides)
    return base


def test_current_evidence_emits_regime_cost_contract():
    report = build_broad_no_edge_regime_cost_robustness(_evidence(), now=NOW)

    payload = report.to_dict()
    assert payload["experiment_id"] == "broad-no-edge-regime-cost-robustness"
    assert (
        payload["completed_candidate_id"]
        == "candidate-broad-no-edge-regime-cost-robustness-experiment"
    )
    assert payload["next_candidate_id"] == "candidate-broad-no-edge-data-gap-audit"
    assert payload["overall_status"] == CONTRACT_READY
    assert payload["regime_metrics"]["window_count"] == 2
    assert payload["regime_metrics"]["wait_label_count"] >= 1
    assert payload["regime_metrics"]["stress_label_count"] >= 1
    assert [row["stress_bps"] for row in payload["cost_stress_rows"]] == [10, 25, 50]
    assert payload["execution_cost_snapshot"]["rejected_orders"] == 2
    assert payload["money_state"]["status"] == "PREVIEW_ONLY"
    assert "no orders" in payload["safety_boundary"]
    assert "레짐·비용 견고성 no-live 실험 계약" in report.as_markdown()


def test_missing_regime_stratify_blocks_contract():
    report = build_broad_no_edge_regime_cost_robustness(
        _evidence(**{"regime-stratify": None}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    surface = next(
        item for item in payload["evidence_surfaces"] if item["key"] == "regime-stratify"
    )
    assert surface["parse_status"] == "missing"


def test_pipeline_critical_blocks_contract():
    report = build_broad_no_edge_regime_cost_robustness(
        _evidence(**{"pipeline-liveness": _pipeline("CRITICAL")}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["pipeline-liveness"] == "FAIL"


def test_low_observation_regime_waits_without_failing_input():
    report = build_broad_no_edge_regime_cost_robustness(
        _evidence(**{"regime-stratify": _regime_stratify(risk_off_days=3)}),
        now=NOW,
    )

    payload = report.to_dict()
    risk_off = [
        label
        for window in payload["regime_windows"]
        for label in window["labels"]
        if label["label"] == "RISK_OFF"
    ]
    assert risk_off
    assert {label["assessment"] for label in risk_off} == {"WAIT"}
    assert payload["overall_status"] == CONTRACT_READY


def test_released_work_without_candidate_leaves_observation_wait():
    report = build_broad_no_edge_regime_cost_robustness(
        _evidence(**{"released-work": _released(include_candidate=False)}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == OBSERVATION_WAIT
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["released-work-closure"] == "WAIT"


def test_learning_suppression_blocks_contract():
    report = build_broad_no_edge_regime_cost_robustness(
        _evidence(**{"evolution-ledger": _ledger("rejected")}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["learning-ledger-duplication"] == "FAIL"


def test_live_capable_money_path_keeps_contract_waiting():
    report = build_broad_no_edge_regime_cost_robustness(
        _evidence(
            **{
                "money-path": _money_path(can_submit=True, status="ARMED"),
                "edge-autoarm": _edge_autoarm("ARM"),
            }
        ),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == OBSERVATION_WAIT
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["money-gate-alignment"] == "WAIT"
