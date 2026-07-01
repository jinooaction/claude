"""스펙 078 — 돈 경로 게이트 정렬 루프 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.money_gate_alignment import (
    SEVERITY_BLOCKED,
    SEVERITY_MISALIGNED,
    SEVERITY_WAITING,
    STATUS_ALIGNED_WAITING,
    STATUS_BLOCKED,
    STATUS_MISALIGNED,
    build_money_gate_alignment,
)

NOW = datetime(2026, 7, 1, 9, 20, 0, tzinfo=UTC)
BLOCKER = "전진 관측 부족: 14/20 (통계적 유의까지 더 쌓여야 함)."


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _fenced(header: str, payload: dict) -> str:
    return f"## {header}\n\n```json\n{_json(payload)}\n```\n"


def _money_path(stage: str = "ACCUMULATING_EDGE", blocker: str = BLOCKER) -> str:
    return _fenced(
        "결정 JSON",
        {
            "schema_version": "1.1",
            "as_of_utc": "2026-07-01T11:21:50Z",
            "stage": stage,
            "blocking_gate": blocker,
            "live_money_state": {
                "status": "PREVIEW_ONLY",
                "can_submit_real_orders": False,
            },
            "gates": [
                {
                    "name": "전진 관측 수",
                    "status": "PENDING",
                    "current": "14",
                    "required": ">= 20",
                }
            ],
            "forward_n_obs": 14,
            "next_action": "전진 관측을 계속 누적한다.",
        },
    )


def _capital(stage: str = "ACCUMULATING_EDGE", blocker: str = BLOCKER) -> str:
    return _json(
        {
            "schema_version": "1.0",
            "timestamp_utc": "2026-07-01T14:11:27Z",
            "readiness_state": "ACCUMULATING_EDGE",
            "live_money_status": "PREVIEW_ONLY",
            "capital_ladder_stage": stage,
            "blocking_gate": blocker,
        }
    )


def _edge(action: str = "WAIT_EDGE", verdict: str = "INSUFFICIENT_DATA") -> str:
    return (
        _fenced(
            "결정 JSON",
            {
                "schema_version": "1.0",
                "action": action,
                "current_rung": 0,
                "target_rung": 0,
                "reason": "단 0 + forward 판정='INSUFFICIENT_DATA'",
            },
        )
        + "\n"
        + _fenced(
            "forward 판정 JSON",
            {
                "schema_version": "1.1",
                "verdict": verdict,
                "n_obs": 14,
                "min_obs_required": 20,
                "snapshot_count": 15,
            },
        )
    )


def _reassign(action: str = "HOLD", challenger: str | None = None) -> str:
    return _fenced(
        "5중 게이트 결정 JSON",
        {
            "schema_version": "1.2",
            "action": action,
            "incumbent_key": "global",
            "challenger_key": challenger,
            "observation_health": "OK",
            "gates": {
                "observation_quality_ok": True,
                "challenger_confirmed": False,
                "multiplicity_robust": False,
                "canary_pass": False,
            },
        },
    )


def _forward() -> str:
    return _fenced(
        "리더보드 결정 JSON",
        {
            "schema_version": "1.0",
            "comparable_count": 0,
            "known_count": 7,
            "max_n_obs": 14,
            "observation_health": "OK",
        },
    )


def _liveness(overall: str = "OK") -> str:
    return _fenced(
        "결정 JSON",
        {
            "schema_version": "1.0",
            "overall": overall,
            "checks": [
                {
                    "key": "rebalance-paper-forward",
                    "status": "OK" if overall == "OK" else "STALE",
                    "critical": True,
                }
            ],
        },
    )


def _work(candidate_id: str = "candidate-fd04772a23c5") -> str:
    return _json(
        {
            "schema_version": "1.0",
            "overall_status": "EXECUTION_READY",
            "selected_work": {"candidate_id": candidate_id},
        }
    )


def _kis_smoke() -> str:
    return (
        "| timestamp_utc | 2026-07-01T14:13:22Z |\n"
        "| smoke_state | success |\n"
        "| key_valid | true |\n"
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        "money-path": _money_path(),
        "capital-path-readiness": _capital(),
        "edge-autoarm": _edge(),
        "reassign": _reassign(),
        "rebalance-paper-forward": _forward(),
        "pipeline-liveness": _liveness(),
        "autonomous-work-execution": _work(),
        "kis-smoke": _kis_smoke(),
    }
    base.update(overrides)
    return base


def test_aligned_waiting_when_existing_gates_agree():
    report = build_money_gate_alignment(
        _evidence(),
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == STATUS_ALIGNED_WAITING
    assert report.live_money_status == "PREVIEW_ONLY"
    assert report.readiness_state == "ACCUMULATING_EDGE"
    assert report.capital_ladder_stage == "ACCUMULATING_EDGE"
    assert report.blocking_gate == BLOCKER
    assert report.selected_work_candidate == "candidate-fd04772a23c5"
    assert {issue.severity for issue in report.alignment_issues} == {SEVERITY_WAITING}
    assert len(report.gate_surfaces) == 8
    assert report.run_id == "123"
    assert report.commit == "abc123"


def test_stage_mismatch_becomes_misaligned():
    report = build_money_gate_alignment(
        _evidence(**{"capital-path-readiness": _capital(stage="EDGE_READY")}),
        now=NOW,
    )

    assert report.overall_status == STATUS_MISALIGNED
    assert any(
        issue.severity == SEVERITY_MISALIGNED
        and issue.gate_key == "capital_ladder_stage"
        for issue in report.alignment_issues
    )


def test_pipeline_critical_blocks_alignment():
    report = build_money_gate_alignment(
        _evidence(**{"pipeline-liveness": _liveness("CRITICAL")}),
        now=NOW,
    )

    assert report.overall_status == STATUS_BLOCKED
    assert any(
        issue.severity == SEVERITY_BLOCKED and issue.gate_key == "pipeline-liveness"
        for issue in report.alignment_issues
    )
    assert "workflow" in report.next_action_ko


def test_missing_money_path_fails_closed():
    report = build_money_gate_alignment(_evidence(**{"money-path": None}), now=NOW)

    assert report.overall_status == STATUS_BLOCKED
    assert report.live_money_status == "UNKNOWN"
    assert any(issue.gate_key == "money-path" for issue in report.alignment_issues)


def test_kis_table_sidecar_counts_as_parseable_status():
    report = build_money_gate_alignment(_evidence(), now=NOW)
    kis = [surface for surface in report.gate_surfaces if surface.key == "kis-smoke"][0]

    assert kis.parse_status == "ok"
    assert kis.status == "success"


def test_deterministic_for_same_inputs():
    evidence = _evidence()

    first = build_money_gate_alignment(evidence, now=NOW).to_dict()
    second = build_money_gate_alignment(evidence, now=NOW).to_dict()

    assert first == second
