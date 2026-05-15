"""Tests for the new spec 006 audit payloads (T005)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from auto_invest.persistence.audit import (
    DeployCompletedPayload,
    DeployFailedPayload,
    DeployKernelTouchedPayload,
    DeployRolledBackPayload,
    DeployStartedPayload,
)


def test_started_payload_roundtrip():
    p = DeployStartedPayload(
        sha_before="a" * 40,
        sha_after="b" * 40,
        branch="main",
        triggered_by="manual",
        dry_run=False,
        allow_dirty=False,
        health_window_s=90,
    )
    body = p.model_dump_json()
    parsed = json.loads(body)
    assert parsed["event_type"] == "DEPLOY_STARTED"
    assert parsed["sha_before"] == "a" * 40
    assert parsed["health_window_s"] == 90


def test_started_payload_frozen():
    p = DeployStartedPayload(
        sha_before="a" * 40, sha_after="b" * 40, branch="main",
    )
    with pytest.raises(ValidationError):
        p.sha_before = "c" * 40  # type: ignore[misc]


def test_started_payload_rejects_extra():
    with pytest.raises(ValidationError):
        DeployStartedPayload(
            sha_before="a" * 40, sha_after="b" * 40, branch="main",
            bogus_field=1,
        )


def test_started_payload_rejects_bad_triggered_by():
    with pytest.raises(ValidationError):
        DeployStartedPayload(
            sha_before="a", sha_after="b", branch="main",
            triggered_by="hacker",  # type: ignore[arg-type]
        )


def test_completed_payload_phase_literal():
    p = DeployCompletedPayload(
        sha_before="a", sha_after="b", phase="dry_run", duration_s=1.5,
    )
    assert p.event_type == "DEPLOY_COMPLETED"
    assert p.phase == "dry_run"
    with pytest.raises(ValidationError):
        DeployCompletedPayload(
            sha_before="a", sha_after="b",
            phase="canary",  # type: ignore[arg-type]
            duration_s=0.1,
        )


def test_failed_payload_phase_enum():
    p = DeployFailedPayload(
        sha_before="a", sha_after=None, phase="market_hours_guard",
        reason="market is open", exit_code=2,
    )
    assert p.event_type == "DEPLOY_FAILED"
    assert p.sha_after is None
    with pytest.raises(ValidationError):
        DeployFailedPayload(
            sha_before="a", sha_after=None, phase="not_a_phase",  # type: ignore[arg-type]
            reason="x", exit_code=2,
        )


def test_rolled_back_payload():
    p = DeployRolledBackPayload(
        sha_before="a", sha_after_failed="b", rolled_back_phase="migrate",
    )
    parsed = json.loads(p.model_dump_json())
    assert parsed["event_type"] == "DEPLOY_ROLLED_BACK"
    assert parsed["rolled_back_phase"] == "migrate"


def test_kernel_touched_payload():
    p = DeployKernelTouchedPayload(
        sha_before="a", sha_after="b",
        touched_paths=["src/auto_invest/risk/gates.py"],
        touched_groups=["K1_position_sizing"],
        triggered_by="manual",
    )
    parsed = json.loads(p.model_dump_json())
    assert parsed["event_type"] == "DEPLOY_KERNEL_TOUCHED"
    assert parsed["touched_groups"] == ["K1_position_sizing"]
