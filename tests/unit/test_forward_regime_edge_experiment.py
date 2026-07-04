"""스펙 095 — forward 레짐 엣지 no-live 실험 계약 코어 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.forward_regime_edge_experiment import (
    BLOCKED,
    CONTRACT_READY,
    OBSERVATION_WAIT,
    build_forward_regime_edge_experiment,
)

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _fenced(obj: dict) -> str:
    return "```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```"


def _forward_sidecar(*, n_obs: int = 16, comparable: bool = False) -> str:
    verdict = "NO_EDGE" if comparable else "INSUFFICIENT_DATA"
    comparability = "COMPARABLE" if comparable else "PREMATURE"
    rows = [
        {
            "key": "global",
            "label": "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)",
            "is_incumbent": True,
            "verdict": verdict,
            "n_obs": n_obs,
            "min_obs": 20,
            "comparability": comparability,
            "rank": 1,
            "calmar": None,
            "sharpe": None,
            "total_return_pct": "-0.5",
            "max_drawdown_pct": "4.2",
            "excess_return_pct": None,
            "dsr": None,
            "psr_vs_benchmark": None,
            "dsr_threshold": "0.95",
            "universe_size": 3,
            "universe": ["SPY", "IEF", "GLD"],
        },
        {
            "key": "wide",
            "label": "글로벌 분산 추세 확대 (11 슬리브)",
            "is_incumbent": False,
            "verdict": verdict,
            "n_obs": n_obs,
            "min_obs": 20,
            "comparability": comparability,
            "rank": 2,
            "calmar": None,
            "sharpe": None,
            "total_return_pct": "-5.2",
            "max_drawdown_pct": "6.0",
            "excess_return_pct": None,
            "dsr": None,
            "psr_vs_benchmark": None,
            "dsr_threshold": "0.95",
            "universe_size": 11,
            "universe": ["SPY", "QQQ", "EFA"],
        },
    ]
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
        "observation_note": "모든 후보 판정이 읽혔고 비교 전 관측 누적 중.",
        "headline": "아직 비교 불가" if not comparable else "엣지 확정 트랙 없음",
        "rows": rows,
    }
    monitor = {
        "as_of": "2026-06",
        "regime": {
            "corr_current": 0.06,
            "corr_recent_5y_avg": 0.10,
            "verdict": "DIVERSIFICATION_WEAKENED",
        },
        "today_signal": {"in_market": True, "gap_pct": 7.6},
    }
    return (
        "# forward 페이퍼 A/B 토너먼트\n\n"
        "## 리더보드 결정 JSON\n\n"
        f"{_fenced(board)}\n\n"
        "=== 낙폭 예산 20% (레버리지 권고 비교) ===\n"
        f"{json.dumps(monitor, ensure_ascii=False)}\n"
    )


def _money_path(*, can_submit: bool = False, status: str = "PREVIEW_ONLY") -> str:
    return (
        "# 돈 경로 상태\n\n"
        "## 결정 JSON\n\n"
        + _fenced(
            {
                "stage": "BLOCKED",
                "headline": "자본 사다리 게이트가 차단/정지 상태",
                "blocking_gate": "전진 판정=INSUFFICIENT_DATA",
                "live_money_state": {
                    "status": status,
                    "can_submit_real_orders": can_submit,
                    "detail": "armed:false",
                },
            }
        )
    )


def _pipeline(overall: str = "OK") -> str:
    return (
        "# 파이프라인 생존 감시\n\n"
        "## 결정 JSON\n\n"
        + _fenced({"overall": overall, "checks": []})
    )


def _released() -> str:
    return json.dumps(
        {
            "overall_status": "OK",
            "released_work": [
                {
                    "candidate_id": "candidate-forward-regime-edge-experiment",
                    "status": "released",
                    "spec_id": "095-forward-regime-edge-experiment",
                }
            ],
        },
        ensure_ascii=False,
    )


def _ledger() -> str:
    return json.dumps(
        {
            "entries": [
                {
                    "candidate_id": "candidate-forward-regime-edge-experiment",
                    "decision": "evidence_dependent",
                    "reason_ko": "후보별 전진 관측과 레짐을 묶는 실험을 설계한다.",
                }
            ]
        },
        ensure_ascii=False,
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        "rebalance-paper-forward": _forward_sidecar(),
        "money-path": _money_path(),
        "released-work": _released(),
        "evolution-ledger": _ledger(),
        "pipeline-liveness": _pipeline(),
    }
    base.update(overrides)
    return base


def test_current_forward_insufficient_data_is_observation_wait():
    report = build_forward_regime_edge_experiment(_evidence(), now=NOW)

    payload = report.to_dict()
    assert payload["experiment_id"] == "forward-regime-edge-experiment"
    assert payload["completed_candidate_id"] == "candidate-forward-regime-edge-experiment"
    assert payload["overall_status"] == OBSERVATION_WAIT
    assert payload["money_state"]["status"] == "PREVIEW_ONLY"
    assert payload["next_observation_gate"]["remaining_observations"] == 4
    assert {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}[
        "forward-comparability"
    ] == "WAIT"
    assert "no orders" in payload["safety_boundary"]
    assert "forward 레짐 엣지 no-live 실험 계약" in report.as_markdown()


def test_pipeline_critical_blocks_experiment():
    report = build_forward_regime_edge_experiment(
        _evidence(**{"pipeline-liveness": _pipeline("CRITICAL")}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    assert {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}[
        "pipeline-liveness"
    ] == "FAIL"


def test_missing_forward_sidecar_blocks_experiment():
    report = build_forward_regime_edge_experiment(
        _evidence(**{"rebalance-paper-forward": None}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    forward_surface = next(
        surface
        for surface in payload["evidence_surfaces"]
        if surface["key"] == "rebalance-paper-forward"
    )
    assert forward_surface["parse_status"] == "missing"


def test_comparable_forward_tracks_make_contract_ready():
    report = build_forward_regime_edge_experiment(
        _evidence(**{"rebalance-paper-forward": _forward_sidecar(n_obs=22, comparable=True)}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == CONTRACT_READY
    assert {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}[
        "forward-comparability"
    ] == "PASS"
