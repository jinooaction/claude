"""스펙 069 — 자율 승격 실행 루프 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.promotion_actions import (
    ACTION_CANARY_SUBMISSION,
    ACTION_EXISTING_GATE_REPORT,
    ACTION_FORWARD_REGISTRATION,
    OVERALL_DEGRADED,
    OVERALL_OK,
    STATUS_ALREADY_REGISTERED,
    STATUS_ALREADY_SUBMITTED,
    STATUS_REGISTERED,
    STATUS_REPORTED,
    STATUS_SUBMITTED,
    build_promotion_actions,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "promotion_actions" / "fresh"
NOW = datetime(2026, 6, 29, 0, 0, 0, tzinfo=UTC)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_build_actions_registers_forward_and_canary_candidates() -> None:
    run = build_promotion_actions(
        promotion_summary=_load("promotion_summary.json"),
        forward_registry=_load("promotion-forward-registry.json"),
        canary_submissions=_load("promotion-canary-submissions.json"),
        now=NOW,
        commit="abc123",
        run_id="unit",
    )

    assert run.overall_status == OVERALL_DEGRADED
    by_kind = {action.kind: action for action in run.actions}
    assert by_kind[ACTION_FORWARD_REGISTRATION].status == STATUS_REGISTERED
    assert by_kind[ACTION_CANARY_SUBMISSION].status == STATUS_SUBMITTED
    assert by_kind[ACTION_EXISTING_GATE_REPORT].status == STATUS_REPORTED
    assert run.counts["blocked"] == 1

    tracks = run.forward_registry_next["tracks"]
    assert tracks[0]["candidate_id"] == "candidate-forward-ready"
    assert tracks[0]["portfolio_path"] == "deploy/promotion_forward_a.toml"
    assert tracks[0]["db_path"] == "data/promotion_forward_a.db"
    assert tracks[0]["halt_path"] == "data/promotion_forward_a.halt.flag"

    submissions = run.canary_submissions_next["submissions"]
    assert submissions[0]["candidate_id"] == "candidate-canary-ready"
    assert submissions[0]["status"] == "pending"
    assert submissions[0]["bands_toml"] == "config/canary_bands_reassign.toml"


def test_actions_are_idempotent_against_existing_state() -> None:
    first = build_promotion_actions(
        promotion_summary=_load("promotion_summary.json"),
        forward_registry=_load("promotion-forward-registry.json"),
        canary_submissions=_load("promotion-canary-submissions.json"),
        now=NOW,
    )
    second = build_promotion_actions(
        promotion_summary=_load("promotion_summary.json"),
        forward_registry=first.forward_registry_next,
        canary_submissions=first.canary_submissions_next,
        now=NOW,
    )

    statuses = {action.kind: action.status for action in second.actions}
    assert statuses[ACTION_FORWARD_REGISTRATION] == STATUS_ALREADY_REGISTERED
    assert statuses[ACTION_CANARY_SUBMISSION] == STATUS_ALREADY_SUBMITTED
    assert len(second.forward_registry_next["tracks"]) == 1
    assert len(second.canary_submissions_next["submissions"]) == 1


def test_unsafe_candidate_path_is_blocked_without_state_change() -> None:
    run = build_promotion_actions(
        promotion_summary=_load("promotion_summary.json"),
        forward_registry=_load("promotion-forward-registry.json"),
        canary_submissions=_load("promotion-canary-submissions.json"),
        now=NOW,
    )

    block = next(block for block in run.blocked if block.candidate_id == "candidate-bad-path")
    assert block.field == "portfolio_path"
    assert "deploy/*.toml" in block.reason_ko
    assert all(
        track["candidate_id"] != "candidate-bad-path"
        for track in run.forward_registry_next["tracks"]
    )


def test_missing_promotion_summary_degrades_without_actions() -> None:
    run = build_promotion_actions(
        promotion_summary=None,
        forward_registry=None,
        canary_submissions=None,
        now=NOW,
    )
    assert run.overall_status == OVERALL_DEGRADED
    assert run.missing_inputs == ("promotion_summary",)
    assert run.actions == ()
    assert run.forward_registry_next == {"schema_version": "1.0", "tracks": []}


def test_valid_subset_without_blocks_is_ok() -> None:
    summary = _load("promotion_summary.json")
    summary["assessments"] = [summary["assessments"][0], summary["assessments"][1]]
    run = build_promotion_actions(
        promotion_summary=summary,
        forward_registry=_load("promotion-forward-registry.json"),
        canary_submissions=_load("promotion-canary-submissions.json"),
        now=NOW,
    )
    assert run.overall_status == OVERALL_OK
    assert run.counts[STATUS_REGISTERED] == 1
    assert run.counts[STATUS_SUBMITTED] == 1
