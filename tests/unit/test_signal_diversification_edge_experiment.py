"""스펙 096 — 신호 다변화 엣지 no-live 실험 계약 코어 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.signal_diversification_edge_experiment import (
    BLOCKED,
    CONTRACT_READY,
    OBSERVATION_WAIT,
    build_signal_diversification_edge_experiment,
)

NOW = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


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
            "key": "trend",
            "label": "추세 필터 ON (드로다운 방어)",
            "is_incumbent": False,
            "rank": 1,
            "max_drawdown_pct": "41.2",
            "universe": ["AAPL", "MSFT", "NVDA"],
        },
        {
            **base,
            "key": "notrend",
            "label": "추세 필터 OFF (대조군)",
            "is_incumbent": False,
            "rank": 2,
            "max_drawdown_pct": "43.2",
            "universe": ["AAPL", "MSFT", "NVDA"],
        },
        {
            **base,
            "key": "rmbeta",
            "label": "위험관리 베타 (스펙 042)",
            "is_incumbent": False,
            "rank": 3,
            "max_drawdown_pct": "30.1",
            "universe": ["SPY", "QQQ"],
        },
        {
            **base,
            "key": "multiasset",
            "label": "멀티에셋 분산 추세 (스펙 043)",
            "is_incumbent": False,
            "rank": 4,
            "max_drawdown_pct": "10.6",
            "universe": ["SPY", "IEF"],
        },
        {
            **base,
            "key": "global",
            "label": "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)",
            "is_incumbent": True,
            "rank": 5,
            "max_drawdown_pct": "4.2",
            "universe": ["SPY", "IEF", "GLD"],
        },
        {
            **base,
            "key": "wide",
            "label": "글로벌 분산 추세 확대 (11 슬리브)",
            "is_incumbent": False,
            "rank": 6,
            "max_drawdown_pct": "6.0",
            "universe": [
                "SPY",
                "QQQ",
                "EFA",
                "EEM",
                "IEF",
                "TLT",
                "LQD",
                "GLD",
                "DBC",
                "VNQ",
                "UUP",
            ],
        },
        {
            **base,
            "key": "globalfixed",
            "label": "글로벌 3자산 추세 고정등가중 (재지정 후보)",
            "is_incumbent": False,
            "rank": 7,
            "max_drawdown_pct": "3.3",
            "universe": ["SPY", "IEF", "GLD"],
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
        "observation_note": "모든 후보 판정이 읽혔고 비교 전 관측 누적 중.",
        "headline": "아직 비교 불가" if not comparable else "비교 가능",
        "rows": rows,
    }
    return "# forward\n\n## 리더보드 결정 JSON\n\n" + _fenced(board)


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
                    "candidate_id": "candidate-signal-diversification-edge-experiment",
                    "status": "released",
                    "spec_id": "096-signal-diversification-edge-experiment",
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
        "money-path": _money_path(),
        "released-work": _released(),
        "evolution-ledger": _ledger(),
        "pipeline-liveness": _pipeline(),
    }
    base.update(overrides)
    return base


def test_current_forward_tracks_emit_signal_contract_with_observation_wait():
    report = build_signal_diversification_edge_experiment(_evidence(), now=NOW)

    payload = report.to_dict()
    assert payload["experiment_id"] == "signal-diversification-edge-experiment"
    assert payload["completed_candidate_id"] == "candidate-signal-diversification-edge-experiment"
    assert payload["overall_status"] == OBSERVATION_WAIT
    assert payload["diversification_metrics"]["family_count"] >= 5
    assert payload["diversification_metrics"]["remaining_observations"] == 4
    families = {family["family_key"]: family for family in payload["signal_families"]}
    assert families["broad_equity_timing"]["track_count"] == 2
    assert families["global_diversification"]["incumbent_present"] is True
    candidate_keys = {
        candidate["candidate_key"]
        for candidate in payload["proposed_signal_candidates"]
    }
    assert "wide_universe_allocation" in candidate_keys
    assert "no orders" in payload["safety_boundary"]
    assert "신호 다변화 no-live 엣지 실험 계약" in report.as_markdown()


def test_comparable_tracks_make_contract_ready():
    report = build_signal_diversification_edge_experiment(
        _evidence(**{"rebalance-paper-forward": _forward_sidecar(n_obs=22, comparable=True)}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == CONTRACT_READY
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["forward-observation-readiness"] == "PASS"
    assert gates["signal-diversity"] == "PASS"


def test_pipeline_critical_blocks_experiment():
    report = build_signal_diversification_edge_experiment(
        _evidence(**{"pipeline-liveness": _pipeline("CRITICAL")}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    assert {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}[
        "pipeline-liveness"
    ] == "FAIL"


def test_missing_forward_sidecar_blocks_experiment():
    report = build_signal_diversification_edge_experiment(
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
