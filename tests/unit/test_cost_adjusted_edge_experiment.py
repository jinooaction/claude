"""스펙 097 — 비용 차감 엣지 no-live 실험 계약 코어 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.cost_adjusted_edge_experiment import (
    BLOCKED,
    CONTRACT_READY,
    OBSERVATION_WAIT,
    build_cost_adjusted_edge_experiment,
)

NOW = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


def _fenced(obj: dict) -> str:
    return "```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```"


def _rows(*, n_obs: int = 16, comparable: bool = False) -> list[dict]:
    verdict = "NO_EDGE" if comparable else "INSUFFICIENT_DATA"
    comparability = "COMPARABLE" if comparable else "PREMATURE"
    base = {
        "verdict": verdict,
        "n_obs": n_obs,
        "min_obs": 20,
        "comparability": comparability,
        "calmar": None,
        "sharpe": None,
        "excess_return_pct": None,
        "dsr": None,
        "psr_vs_benchmark": None,
        "dsr_threshold": "0.95",
    }
    return [
        {
            **base,
            "key": "global",
            "label": "글로벌 분산 추세",
            "is_incumbent": True,
            "rank": 1,
            "total_return_pct": "-0.58",
            "max_drawdown_pct": "4.28",
            "universe": ["SPY", "IEF", "GLD"],
        },
        {
            **base,
            "key": "multiasset",
            "label": "멀티에셋 분산 추세",
            "is_incumbent": False,
            "rank": 2,
            "total_return_pct": "1.84",
            "max_drawdown_pct": "10.64",
            "universe": ["SPY", "IEF"],
        },
        {
            **base,
            "key": "wide",
            "label": "글로벌 분산 추세 확대",
            "is_incumbent": False,
            "rank": 3,
            "total_return_pct": "-5.27",
            "max_drawdown_pct": "6.07",
            "universe": ["SPY", "QQQ", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD"],
        },
    ]


def _forward_sidecar(*, n_obs: int = 16, comparable: bool = False) -> str:
    rows = _rows(n_obs=n_obs, comparable=comparable)
    board = {
        "schema_version": "1.0",
        "as_of_utc": "2026-07-03T23:40:22Z",
        "champion_key": None,
        "incumbent_key": "global",
        "challenger_key": None,
        "comparable_count": len(rows) if comparable else 0,
        "track_count": len(rows),
        "known_count": len(rows),
        "unknown_count": 0,
        "max_n_obs": n_obs,
        "min_n_obs": n_obs,
        "lagging_keys": [],
        "observation_health": "OK",
        "observation_note": "관측 누적 중",
        "headline": "아직 비교 불가" if not comparable else "비교 가능",
        "rows": rows,
    }
    return "# forward\n\n## 리더보드 결정 JSON\n\n" + _fenced(board)


def _execution_quality(
    *,
    basis_complete: bool = False,
    monitor_verdict: str = "INSUFFICIENT_DATA",
) -> str:
    return (
        "# 실행 품질 패키지\n\n"
        "## 결정 JSON\n\n"
        + _fenced(
            {
                "overall_status": "OBSERVE",
                "opportunity_monitor": {
                    "verdict": monitor_verdict,
                    "latest_signal": "INTENT_LOSS",
                    "cumulative_pnl_usd": "-1.14",
                    "valued_records": 2,
                    "rejected_orders": 2,
                    "valued_orders": 0,
                },
                "broker_rejections": {
                    "rejected_orders": 2,
                    "parsed_broker_errors": 2,
                    "broker_error_observation_rate": 1.0,
                    "kis_msg_codes": {"APBK1672": 2},
                },
                "broker_smoke": {
                    "present": True,
                    "smoke_state": "success",
                    "tests_total": 4,
                    "tests_failed": 0,
                    "smoke_error_rate": 0.0,
                },
                "execution_cost_basis": {
                    "basis_complete": basis_complete,
                    "accepted_or_filled_orders": 4 if basis_complete else 0,
                    "turnover_observed": basis_complete,
                },
            }
        )
    )


def _money_path(*, can_submit: bool = False, status: str = "PREVIEW_ONLY") -> str:
    return (
        "# 돈 경로 상태\n\n"
        "## 결정 JSON\n\n"
        + _fenced(
            {
                "stage": "BLOCKED",
                "live_money_state": {
                    "status": status,
                    "can_submit_real_orders": can_submit,
                    "detail": "armed:false",
                },
            }
        )
    )


def _pipeline(overall: str = "OK") -> str:
    return "# 파이프라인 생존 감시\n\n## 결정 JSON\n\n" + _fenced(
        {"overall": overall, "checks": []}
    )


def _released() -> str:
    return json.dumps(
        {
            "overall_status": "OK",
            "released_work": [
                {
                    "candidate_id": "candidate-cost-adjusted-edge-experiment",
                    "status": "released",
                    "spec_id": "097-cost-adjusted-edge-experiment",
                }
            ],
        },
        ensure_ascii=False,
    )


def _ledger() -> str:
    return json.dumps({"entries": []}, ensure_ascii=False)


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        "rebalance-paper-forward": _forward_sidecar(),
        "execution-quality": _execution_quality(),
        "money-path": _money_path(),
        "released-work": _released(),
        "evolution-ledger": _ledger(),
        "pipeline-liveness": _pipeline(),
    }
    base.update(overrides)
    return base


def test_current_evidence_emits_cost_contract_with_observation_wait():
    report = build_cost_adjusted_edge_experiment(_evidence(), now=NOW)

    payload = report.to_dict()
    assert payload["experiment_id"] == "cost-adjusted-edge-experiment"
    assert payload["completed_candidate_id"] == "candidate-cost-adjusted-edge-experiment"
    assert payload["overall_status"] == OBSERVATION_WAIT
    assert len(payload["required_inputs"]) == 6
    assert payload["cost_metrics"]["stress_bps"] == [10, 25, 50]
    assert payload["execution_cost"]["latest_signal"] == "INTENT_LOSS"
    assert payload["execution_cost"]["cost_basis_complete"] is False
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["forward-observation-readiness"] == "WAIT"
    assert gates["cost-basis-completeness"] == "WAIT"
    assert gates["execution-quality-evidence"] == "PASS"
    candidate = next(
        item
        for item in payload["cost_adjusted_candidates"]
        if item["track_key"] == "multiasset" and item["stress_bps"] == 50
    )
    assert candidate["cost_adjusted_return_pct"] == 1.34
    assert "no orders" in payload["safety_boundary"]
    assert "비용 차감 no-live 엣지 실험 계약" in report.as_markdown()


def test_comparable_tracks_and_complete_cost_basis_make_contract_ready():
    report = build_cost_adjusted_edge_experiment(
        _evidence(
            **{
                "rebalance-paper-forward": _forward_sidecar(n_obs=22, comparable=True),
                "execution-quality": _execution_quality(
                    basis_complete=True,
                    monitor_verdict="OBSERVE",
                ),
            }
        ),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == CONTRACT_READY
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["forward-observation-readiness"] == "PASS"
    assert gates["cost-basis-completeness"] == "PASS"


def test_pipeline_critical_blocks_experiment():
    report = build_cost_adjusted_edge_experiment(
        _evidence(**{"pipeline-liveness": _pipeline("CRITICAL")}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    assert {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}[
        "pipeline-liveness"
    ] == "FAIL"


def test_missing_execution_quality_sidecar_blocks_experiment():
    report = build_cost_adjusted_edge_experiment(
        _evidence(**{"execution-quality": None}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    execution_surface = next(
        surface
        for surface in payload["evidence_surfaces"]
        if surface["key"] == "execution-quality"
    )
    assert execution_surface["parse_status"] == "missing"
