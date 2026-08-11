"""스펙 125 — 광역 자산군 방어 회전 no-live 실험 계약 코어 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.broad_no_edge_asset_universe_rotation import (
    BLOCKED,
    CONTRACT_READY,
    build_broad_no_edge_asset_universe_rotation,
)

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _fenced(obj: dict) -> str:
    return "```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```"


def _forward_sidecar() -> str:
    board = {
        "schema_version": "1.0",
        "as_of_utc": "2026-08-10T23:10:02Z",
        "champion_key": None,
        "incumbent_key": "global",
        "challenger_key": None,
        "comparable_count": 7,
        "track_count": 7,
        "known_count": 7,
        "unknown_count": 0,
        "max_n_obs": 40,
        "min_n_obs": 34,
        "observation_health": "OK",
        "headline": "비교 가능 트랙 모두 NO_EDGE",
        "rows": [
            {
                "key": "multiasset",
                "label": "멀티에셋 분산 추세",
                "is_incumbent": False,
                "verdict": "NO_EDGE",
                "n_obs": 40,
                "min_obs": 20,
                "comparability": "COMPARABLE",
                "rank": 1,
                "universe": ["SPY", "IEF"],
            },
            {
                "key": "global",
                "label": "글로벌 분산 추세",
                "is_incumbent": True,
                "verdict": "NO_EDGE",
                "n_obs": 40,
                "min_obs": 20,
                "comparability": "COMPARABLE",
                "rank": 4,
                "universe": ["SPY", "IEF", "GLD"],
            },
            {
                "key": "wide",
                "label": "글로벌 분산 추세 확대",
                "is_incumbent": False,
                "verdict": "NO_EDGE",
                "n_obs": 40,
                "min_obs": 20,
                "comparability": "COMPARABLE",
                "rank": 7,
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
        ],
    }
    return "# forward\n\n## 리더보드 결정 JSON\n\n" + _fenced(board)


def _money_path() -> str:
    return (
        "# 돈 경로 상태\n\n## 결정 JSON\n\n"
        + _fenced(
            {
                "stage": "NO_EDGE_YET",
                "live_money_state": {
                    "status": "PREVIEW_ONLY",
                    "can_submit_real_orders": False,
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


def _public_data(*, published: int = 10, overall_ok: bool = False) -> str:
    return (
        "# 공개 데이터 수집 채널\n\n## summary.json\n\n"
        + _fenced(
            {
                "overall_ok": overall_ok,
                "published": published,
                "items": [
                    {"kind": "treasury", "id": "UST2Y", "ok": True},
                    {"kind": "treasury", "id": "UST10Y", "ok": True},
                    {"kind": "treasury", "id": "UST10Y2Y", "ok": True},
                    {"kind": "cboe", "id": "VIX", "ok": True},
                    {"kind": "fred", "id": "DGS2", "ok": True},
                    {"kind": "fred", "id": "DGS10", "ok": True},
                ],
            }
        )
    )


def _released() -> str:
    return json.dumps(
        {
            "overall_status": "OK",
            "released_work": [
                {
                    "candidate_id": (
                        "candidate-broad-no-edge-asset-universe-rotation-experiment"
                    ),
                    "status": "released",
                    "spec_id": "125-broad-no-edge-asset-universe",
                }
            ],
        },
        ensure_ascii=False,
    )


def _ledger() -> str:
    return json.dumps({"entries": []}, ensure_ascii=False)


def _pipeline(overall: str = "OK") -> str:
    return "# 파이프라인 생존 감시\n\n## 결정 JSON\n\n" + _fenced(
        {"overall": overall, "checks": []}
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        "rebalance-paper-forward": _forward_sidecar(),
        "money-path": _money_path(),
        "edge-autoarm": _edge_autoarm(),
        "public-data": _public_data(),
        "released-work": _released(),
        "evolution-ledger": _ledger(),
        "pipeline-liveness": _pipeline(),
    }
    base.update(overrides)
    return base


def test_current_evidence_emits_asset_universe_contract():
    report = build_broad_no_edge_asset_universe_rotation(_evidence(), now=NOW)

    payload = report.to_dict()
    assert payload["experiment_id"] == "broad-no-edge-asset-universe-rotation"
    assert (
        payload["completed_candidate_id"]
        == "candidate-broad-no-edge-asset-universe-rotation-experiment"
    )
    assert (
        payload["next_candidate_id"]
        == "candidate-broad-no-edge-multi-horizon-signal-experiment"
    )
    assert payload["overall_status"] == CONTRACT_READY
    assert payload["asset_universe_metrics"]["tested_bucket_count"] >= 5
    assert payload["money_state"]["status"] == "PREVIEW_ONLY"
    assert payload["edge_autoarm_state"]["action"] == "WAIT_EDGE"
    proposed = {
        candidate["candidate_key"]: candidate
        for candidate in payload["proposed_rotation_candidates"]
    }
    assert "cash_treasury_defense_rotation" in proposed
    assert "inflation_shock_defense_rotation" in proposed
    assert proposed["cash_treasury_defense_rotation"]["status"] == "PROPOSED"
    exclusions = {
        item["candidate_key"]: item for item in payload["exclusion_criteria"]
    }
    assert exclusions["repeat_wide_universe_static"]["covered_by_track"] == "wide"
    assert "no orders" in payload["safety_boundary"]
    assert "자산군 방어 회전 no-live 실험 계약" in report.as_markdown()


def test_missing_forward_sidecar_blocks_contract():
    report = build_broad_no_edge_asset_universe_rotation(
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


def test_pipeline_critical_blocks_contract():
    report = build_broad_no_edge_asset_universe_rotation(
        _evidence(**{"pipeline-liveness": _pipeline("CRITICAL")}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == BLOCKED
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["pipeline-liveness"] == "FAIL"


def test_public_data_warning_does_not_block_when_core_inputs_exist():
    report = build_broad_no_edge_asset_universe_rotation(
        _evidence(**{"public-data": _public_data(published=6, overall_ok=False)}),
        now=NOW,
    )

    payload = report.to_dict()
    assert payload["overall_status"] == CONTRACT_READY
    assert payload["public_data_support"]["overall_ok"] is False
    assert payload["public_data_support"]["macro_core_available"] is True
    gates = {gate["gate_id"]: gate["status"] for gate in payload["validation_gates"]}
    assert gates["public-data-support"] == "PASS"
