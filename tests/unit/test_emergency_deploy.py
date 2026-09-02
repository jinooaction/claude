"""Spec 179: one-shot owner emergency deploy request validation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from auto_invest.deploy.emergency import (
    EmergencyRequestError,
    find_pending_preauthorization,
    is_request_consumed,
    validate_emergency_request,
)
from auto_invest.persistence import audit
from auto_invest.persistence import db as dbmod

NOW = 1_788_368_400
TARGET = "a" * 40


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "request_id": "github-run-123456",
        "target_sha": TARGET,
        "actor": "jinooaction",
        "workflow_run_id": "123456",
        "source": "github-actions-workflow-dispatch",
        "reason_sha256": "b" * 64,
        "issued_at_epoch": NOW - 5,
        "expires_at_epoch": NOW + 595,
    }
    payload.update(overrides)
    return payload


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


@pytest.mark.parametrize("actor", ["jinooaction", "masonoh-kidsnote"])
def test_valid_exact_short_lived_root_equivalent_request(
    tmp_path: Path, actor: str
) -> None:
    path = tmp_path / "request.json"
    _write(path, _payload(actor=actor))

    request = validate_emergency_request(
        path,
        target_sha=TARGET,
        now_epoch=NOW,
        expected_uid=os.getuid(),
    )

    assert request.request_id == "github-run-123456"
    assert request.target_sha == TARGET
    assert request.actor == actor
    assert request.expires_at_epoch - request.issued_at_epoch == 600


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"schema_version": "0.9"}, "schema"),
        ({"target_sha": "c" * 40}, "target"),
        ({"actor": "someone-else"}, "actor"),
        ({"source": "shell"}, "source"),
        ({"reason_sha256": "bad"}, "reason"),
        ({"issued_at_epoch": NOW + 1}, "future"),
        ({"expires_at_epoch": NOW - 1}, "expired"),
        ({"expires_at_epoch": NOW + 901}, "15 minutes"),
        ({"workflow_run_id": "0"}, "workflow"),
        ({"request_id": "github-run-999"}, "request id"),
        ({"unexpected": True}, "extra"),
    ],
)
def test_invalid_request_fails_closed(
    tmp_path: Path, overrides: dict[str, object], reason: str
) -> None:
    path = tmp_path / "request.json"
    _write(path, _payload(**overrides))

    with pytest.raises(EmergencyRequestError, match=reason):
        validate_emergency_request(
            path,
            target_sha=TARGET,
            now_epoch=NOW,
            expected_uid=os.getuid(),
            allowed_actors=frozenset({"jinooaction"}),
        )


def test_missing_symlink_writable_and_wrong_owner_requests_fail(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(EmergencyRequestError, match="missing"):
        validate_emergency_request(
            missing, target_sha=TARGET, now_epoch=NOW, expected_uid=os.getuid()
        )

    real = tmp_path / "real.json"
    _write(real, _payload())
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(EmergencyRequestError, match="regular"):
        validate_emergency_request(
            link, target_sha=TARGET, now_epoch=NOW, expected_uid=os.getuid()
        )

    real.chmod(0o620)
    with pytest.raises(EmergencyRequestError, match="writable"):
        validate_emergency_request(
            real, target_sha=TARGET, now_epoch=NOW, expected_uid=os.getuid()
        )

    real.chmod(0o600)
    with pytest.raises(EmergencyRequestError, match="owner"):
        validate_emergency_request(
            real, target_sha=TARGET, now_epoch=NOW, expected_uid=os.getuid() + 1
        )


def test_request_id_is_persistently_single_use(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    conn = dbmod.get_connection(db_path)
    try:
        dbmod.migrate(conn)
        assert not is_request_consumed(conn, "github-run-123456")
        audit.append(
            conn,
            audit.DeployEmergencyAuthorizedPayload(
                request_id="github-run-123456",
                target_sha=TARGET,
                actor="jinooaction",
                workflow_run_id="123456",
                source="github-actions-workflow-dispatch",
                reason_sha256="b" * 64,
                issued_at_epoch=NOW - 5,
                expires_at_epoch=NOW + 595,
            ),
        )
        conn.commit()
        assert is_request_consumed(conn, "github-run-123456")
    finally:
        conn.close()


def test_matching_root_helper_preauthorization_is_pending_until_started(
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    _write(request_path, _payload())
    request = validate_emergency_request(
        request_path,
        target_sha=TARGET,
        now_epoch=NOW,
        expected_uid=os.getuid(),
    )
    db_path = tmp_path / "audit.db"
    conn = dbmod.get_connection(db_path)
    try:
        dbmod.migrate(conn)
        correlation_id = "c" * 32
        audit.append(
            conn,
            audit.DeployEmergencyAuthorizedPayload(
                request_id=request.request_id,
                target_sha=request.target_sha,
                actor=request.actor,
                workflow_run_id=request.workflow_run_id,
                source="github-actions-workflow-dispatch",
                reason_sha256=request.reason_sha256,
                issued_at_epoch=request.issued_at_epoch,
                expires_at_epoch=request.expires_at_epoch,
            ),
            correlation_id=correlation_id,
        )
        conn.commit()
        assert find_pending_preauthorization(conn, request) == correlation_id

        audit.append(
            conn,
            audit.DeployStartedPayload(
                sha_before="d" * 40,
                sha_after=TARGET,
                branch="main",
                triggered_by="operator-emergency",
            ),
            correlation_id=correlation_id,
        )
        conn.commit()
        with pytest.raises(EmergencyRequestError, match="already consumed"):
            find_pending_preauthorization(conn, request)
    finally:
        conn.close()


def test_mismatched_or_ambiguous_preauthorization_fails_closed(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    _write(request_path, _payload())
    request = validate_emergency_request(
        request_path,
        target_sha=TARGET,
        now_epoch=NOW,
        expected_uid=os.getuid(),
    )
    db_path = tmp_path / "audit.db"
    conn = dbmod.get_connection(db_path)
    try:
        dbmod.migrate(conn)
        payload = audit.DeployEmergencyAuthorizedPayload(
            request_id=request.request_id,
            target_sha="e" * 40,
            actor=request.actor,
            workflow_run_id=request.workflow_run_id,
            source="github-actions-workflow-dispatch",
            reason_sha256=request.reason_sha256,
            issued_at_epoch=request.issued_at_epoch,
            expires_at_epoch=request.expires_at_epoch,
        )
        audit.append(conn, payload, correlation_id="f" * 32)
        conn.commit()
        with pytest.raises(EmergencyRequestError, match="does not match"):
            find_pending_preauthorization(conn, request)

        audit.append(conn, payload, correlation_id="1" * 32)
        conn.commit()
        with pytest.raises(EmergencyRequestError, match="ambiguous"):
            find_pending_preauthorization(conn, request)
    finally:
        conn.close()
