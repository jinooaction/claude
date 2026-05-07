"""Tests for the DEPLOY_BLOCKED_KERNEL_TOUCH audit-log extension (spec 006 FR-D13)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import DeployBlockedKernelTouchPayload


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "test.db"
    c = db.get_connection(path)
    db.migrate(c)
    yield c
    c.close()


def test_payload_validates():
    p = DeployBlockedKernelTouchPayload(
        sha_before="abc",
        sha_after="def",
        touched_paths=["src/auto_invest/risk/gates.py"],
        touched_groups=["K1_position_sizing"],
        triggered_by="auto-tuner",
    )
    assert p.event_type == "DEPLOY_BLOCKED_KERNEL_TOUCH"
    assert p.triggered_by == "auto-tuner"


def test_payload_default_triggered_by_manual():
    p = DeployBlockedKernelTouchPayload(
        sha_before="a",
        sha_after="b",
        touched_paths=[],
        touched_groups=[],
    )
    assert p.triggered_by == "manual"


def test_payload_appended_to_audit_log(conn: sqlite3.Connection):
    audit.append(
        conn,
        DeployBlockedKernelTouchPayload(
            sha_before="abc123",
            sha_after="def456",
            touched_paths=["src/auto_invest/persistence/audit.py"],
            touched_groups=["K4_append_only_audit"],
            triggered_by="auto-tuner",
        ),
    )
    row = conn.execute(
        "SELECT event_type, payload_json FROM audit_log "
        "WHERE event_type='DEPLOY_BLOCKED_KERNEL_TOUCH'"
    ).fetchone()
    assert row is not None
    payload = json.loads(row["payload_json"])
    assert payload["touched_groups"] == ["K4_append_only_audit"]
    assert payload["triggered_by"] == "auto-tuner"


def test_payload_extra_fields_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DeployBlockedKernelTouchPayload(
            sha_before="a",
            sha_after="b",
            touched_paths=[],
            touched_groups=[],
            extra_field="nope",  # type: ignore[call-arg]
        )
