"""Fail-closed validation for one-shot owner emergency deploy requests.

The root-owned server helper writes the request at a fixed path.  This module
does not create requests and exposes no CLI override; it only verifies the
small immutable contract immediately before the deploy runner decides whether
the normal XNYS market-hours refusal may use constitution VIII.A's exception.
"""

from __future__ import annotations

import json
import re
import sqlite3
import stat
import time
from dataclasses import dataclass
from pathlib import Path

MAX_TTL_SEC = 900
DEFAULT_REQUEST_PATH = Path("/run/auto-invest-deploy/emergency-request.json")
DEFAULT_ALLOWED_ACTORS = frozenset({"jinooaction", "masonoh-kidsnote"})

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^[1-9][0-9]*$")
_ACTOR_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_FIELDS = {
    "schema_version",
    "request_id",
    "target_sha",
    "actor",
    "workflow_run_id",
    "source",
    "reason_sha256",
    "issued_at_epoch",
    "expires_at_epoch",
}
_CORRELATION_RE = re.compile(r"^[0-9a-f]{32}$")


class EmergencyRequestError(ValueError):
    """A request cannot safely authorize a market-hours deploy."""


@dataclass(frozen=True)
class EmergencyDeployRequest:
    schema_version: str
    request_id: str
    target_sha: str
    actor: str
    workflow_run_id: str
    source: str
    reason_sha256: str
    issued_at_epoch: int
    expires_at_epoch: int


def _required_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise EmergencyRequestError(f"invalid {key}")
    return value


def _required_epoch(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EmergencyRequestError(f"invalid {key}")
    return value


def validate_emergency_request(
    path: Path,
    *,
    target_sha: str,
    now_epoch: int | None = None,
    expected_uid: int = 0,
    allowed_actors: frozenset[str] = DEFAULT_ALLOWED_ACTORS,
) -> EmergencyDeployRequest:
    """Validate file identity, exact target, owner, lifetime, and closed schema."""

    try:
        file_stat = path.lstat()
    except FileNotFoundError as exc:
        raise EmergencyRequestError("emergency request is missing") from exc
    if not stat.S_ISREG(file_stat.st_mode):
        raise EmergencyRequestError("emergency request must be a regular file")
    if file_stat.st_uid != expected_uid:
        raise EmergencyRequestError("emergency request has an invalid owner")
    if stat.S_IMODE(file_stat.st_mode) & 0o022:
        raise EmergencyRequestError("emergency request is writable by an untrusted user")
    if file_stat.st_size <= 0 or file_stat.st_size > 4096:
        raise EmergencyRequestError("emergency request has an invalid size")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmergencyRequestError("emergency request is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise EmergencyRequestError("emergency request must be a JSON object")
    data: dict[str, object] = raw
    extra = set(data) - _FIELDS
    missing = _FIELDS - set(data)
    if extra:
        raise EmergencyRequestError(f"emergency request has extra fields: {sorted(extra)}")
    if missing:
        raise EmergencyRequestError(f"emergency request is missing fields: {sorted(missing)}")

    schema_version = _required_string(data, "schema_version")
    if schema_version != "1.0":
        raise EmergencyRequestError("invalid emergency request schema")
    request_id = _required_string(data, "request_id")
    request_target = _required_string(data, "target_sha")
    actor = _required_string(data, "actor")
    workflow_run_id = _required_string(data, "workflow_run_id")
    source = _required_string(data, "source")
    reason_sha256 = _required_string(data, "reason_sha256")
    issued_at = _required_epoch(data, "issued_at_epoch")
    expires_at = _required_epoch(data, "expires_at_epoch")

    if not _SHA_RE.fullmatch(target_sha) or request_target != target_sha:
        raise EmergencyRequestError("emergency request target does not match current main")
    if not _ACTOR_RE.fullmatch(actor) or actor not in allowed_actors:
        raise EmergencyRequestError("emergency request actor is not a registered owner")
    if source != "github-actions-workflow-dispatch":
        raise EmergencyRequestError("invalid emergency request source")
    if not _RUN_ID_RE.fullmatch(workflow_run_id):
        raise EmergencyRequestError("invalid workflow run id")
    if request_id != f"github-run-{workflow_run_id}":
        raise EmergencyRequestError("emergency request id does not match workflow run id")
    if not _DIGEST_RE.fullmatch(reason_sha256):
        raise EmergencyRequestError("invalid emergency reason digest")

    now = int(time.time()) if now_epoch is None else now_epoch
    if issued_at > now:
        raise EmergencyRequestError("emergency request was issued in the future")
    if expires_at < now:
        raise EmergencyRequestError("emergency request expired")
    if expires_at <= issued_at or expires_at - issued_at > MAX_TTL_SEC:
        raise EmergencyRequestError("emergency request exceeds 15 minutes")

    return EmergencyDeployRequest(
        schema_version=schema_version,
        request_id=request_id,
        target_sha=request_target,
        actor=actor,
        workflow_run_id=workflow_run_id,
        source=source,
        reason_sha256=reason_sha256,
        issued_at_epoch=issued_at,
        expires_at_epoch=expires_at,
    )


def is_request_consumed(conn: sqlite3.Connection, request_id: str) -> bool:
    """Return true when append-only audit already contains this request id."""

    rows = conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type = 'DEPLOY_EMERGENCY_AUTHORIZED' ORDER BY seq"
    )
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if payload.get("request_id") == request_id:
            return True
    return False


def find_pending_preauthorization(
    conn: sqlite3.Connection,
    request: EmergencyDeployRequest,
) -> str | None:
    """Return a matching root-helper authorization not yet followed by STARTED.

    The production helper must stop the old worker before the new deploy code can
    run.  It therefore appends the authorization first, then quiesces services.
    A matching row is a pending hand-off, not a reusable request: once a
    ``DEPLOY_STARTED`` row exists on its correlation id it is consumed forever.
    """

    matches: list[tuple[dict[str, object], str]] = []
    rows = conn.execute(
        "SELECT payload_json, correlation_id FROM audit_log "
        "WHERE event_type = 'DEPLOY_EMERGENCY_AUTHORIZED' ORDER BY seq"
    )
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if payload.get("request_id") == request.request_id:
            matches.append((payload, row["correlation_id"]))

    if not matches:
        return None
    if len(matches) != 1:
        raise EmergencyRequestError("emergency request authorization is ambiguous")

    payload, correlation_id = matches[0]
    expected = {
        "event_type": "DEPLOY_EMERGENCY_AUTHORIZED",
        "request_id": request.request_id,
        "target_sha": request.target_sha,
        "actor": request.actor,
        "workflow_run_id": request.workflow_run_id,
        "source": request.source,
        "reason_sha256": request.reason_sha256,
        "issued_at_epoch": request.issued_at_epoch,
        "expires_at_epoch": request.expires_at_epoch,
    }
    if payload != expected:
        raise EmergencyRequestError("emergency preauthorization does not match request")
    if not isinstance(correlation_id, str) or not _CORRELATION_RE.fullmatch(
        correlation_id
    ):
        raise EmergencyRequestError("emergency preauthorization correlation is invalid")
    started = conn.execute(
        "SELECT 1 FROM audit_log WHERE correlation_id = ? "
        "AND event_type = 'DEPLOY_STARTED' LIMIT 1",
        (correlation_id,),
    ).fetchone()
    if started is not None:
        raise EmergencyRequestError("emergency request was already consumed")
    return correlation_id
