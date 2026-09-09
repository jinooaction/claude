import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.execution import intraday_qualification as q
from auto_invest.execution.intraday_selection import ResearchSelection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import DataError


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    candidate = build_candidate_registry(load_preregistration(q.PREREGISTRATION))[0]
    provider = "kis-nasdaq-partial-unadjusted"
    selection = ResearchSelection(candidate, provider, "a" * 40, "dataset", "research",
                                  execution_fingerprint(candidate, provider),
                                  "PAPER_CHALLENGER", 756, 0)
    forward = dict(freeze_authentication_verified=True, minimum_observation_count_met=True,
                   complete_sessions=60, required_sessions=60, invalid_sessions=0,
                   execution_parity_verified=True)
    record = tmp_path / "freeze.json"
    record.write_bytes(b"frozen-record")
    calls = []

    def select(archives, prereg, commit):
        assert prereg != q.PREREGISTRATION
        assert prereg.read_bytes() == q.PREREGISTRATION.read_bytes()
        assert commit == "a" * 40
        calls.append(("research", prereg))
        return selection

    def assess(database, raw, selected, prereg):
        assert selected is selection and raw == b"frozen-record"
        assert prereg == calls[0][1]
        calls.append(("forward", prereg))
        return forward

    monkeypatch.setattr(q, "subprocess", SimpleNamespace(check_output=lambda *a, **k: "a" * 40))
    monkeypatch.setattr(q, "select_research", select)
    monkeypatch.setattr(q, "assess_registered_forward", assess)
    args = dict(archives=tmp_path, forward_database=tmp_path / "forward.db",
                registration=record, account="1234567801", capital_limit=Decimal("600.00"),
                runtime_digest="sha256:" + "d" * 64)
    return args, selection, forward, calls


def grant(qualification):
    selected = qualification.selection
    now = datetime.now(UTC)
    return dict(
        schema=1, scope="intraday-repeated-orders", authorization_id="operator-reviewed-1",
        account_digest=qualification.account_digest, execution_identity=selected.execution_identity,
        research_digest=selected.research_digest, dataset_fingerprint=selected.dataset_fingerprint,
        registration_digest=qualification.registration_digest, capital_limit_usd="600",
        runtime_digest=qualification.runtime_digest,
        valid_from=(now - timedelta(minutes=1)).isoformat(),
        valid_until=(now + timedelta(minutes=1)).isoformat(),
        broker_execution_parity_digest="sha256:" + "a" * 64,
        hardened_canary_digest="sha256:" + "b" * 64,
        deployment_audit_digest="sha256:" + "c" * 64,
    )


def test_recomputation_is_required_and_server_authorization_is_separate(prepared, monkeypatch):
    args, _, _, calls = prepared
    result = q.prepare_qualification(**args)
    assert [name for name, _ in calls] == ["research", "forward"]
    assert not calls[0][1].exists()
    monkeypatch.setattr(q, "_read_authorization", lambda: {})
    assert result() == "QUALIFICATION_AUTHORIZATION_MISMATCH"
    approved = grant(result)
    monkeypatch.setattr(q, "_read_authorization", lambda: approved)
    assert result() is None
    approved["authorization_id"] = ""
    assert result() == "QUALIFICATION_AUTHORIZATION_MISMATCH"


@pytest.mark.parametrize("field,value", [
    ("complete_sessions", 59), ("complete_sessions", True), ("required_sessions", 1),
    ("invalid_sessions", 1), ("invalid_sessions", False),
    ("freeze_authentication_verified", False), ("minimum_observation_count_met", "true"),
])
def test_bad_forward_evidence_never_produces_a_guard(prepared, field, value):
    args, _, forward, _ = prepared
    forward[field] = value
    with pytest.raises(DataError, match="QUALIFICATION_FORWARD_NOT_ACCEPTED"):
        q.prepare_qualification(**args)


def test_failed_research_never_reaches_forward_assessment(prepared, monkeypatch):
    args, selection, _, calls = prepared
    monkeypatch.setattr(q, "select_research", lambda *a: replace(selection, candidate=None))
    with pytest.raises(DataError, match="QUALIFICATION_RESEARCH_NOT_ACCEPTED"):
        q.prepare_qualification(**args)
    assert calls == []


def test_current_forward_without_execution_parity_cannot_be_overridden_by_approval(prepared):
    args, _, forward, _ = prepared
    forward["execution_parity_verified"] = False
    with pytest.raises(DataError, match="QUALIFICATION_PARITY_NOT_VERIFIED"):
        q.prepare_qualification(**args)


@pytest.mark.parametrize("field", [
    "account_digest", "execution_identity", "research_digest", "dataset_fingerprint",
    "registration_digest", "runtime_digest", "capital_limit_usd", "scope",
    "broker_execution_parity_digest",
    "hardened_canary_digest", "deployment_audit_digest",
])
def test_changed_authorization_identity_is_refused(prepared, monkeypatch, field):
    result = q.prepare_qualification(**prepared[0])
    approved = grant(result)
    approved[field] = "changed"
    monkeypatch.setattr(q, "_read_authorization", lambda: approved)
    assert result() == "QUALIFICATION_AUTHORIZATION_MISMATCH"


def test_expiry_and_strategy_change_are_checked_at_each_call(prepared, monkeypatch):
    result = q.prepare_qualification(**prepared[0])
    approved = grant(result)
    monkeypatch.setattr(q, "_read_authorization", lambda: approved)
    assert result() is None
    approved["valid_until"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    assert result() == "QUALIFICATION_AUTHORIZATION_EXPIRED"
    monkeypatch.setattr(q, "execution_fingerprint", lambda *a: "changed")
    assert result() == "QUALIFICATION_STRATEGY_CHANGED"


def test_unavailable_error_is_closed(prepared, monkeypatch):
    result = q.prepare_qualification(**prepared[0])

    def fail():
        raise OSError("private path and contents")

    monkeypatch.setattr(q, "_read_authorization", fail)
    assert result() == "QUALIFICATION_AUTHORIZATION_UNAVAILABLE"


def test_protected_file_missing_world_writable_or_symlink_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "authorization.json"
    monkeypatch.setattr(q, "AUTHORIZATION_PATH", path)
    with pytest.raises(DataError, match="INTRADAY_AUTHORIZATION_UNAVAILABLE"):
        q._read_authorization()
    path.write_text("{}")
    path.chmod(0o666)
    with pytest.raises(DataError, match="INTRADAY_AUTHORIZATION_UNAVAILABLE"):
        q._read_authorization()
    alias = tmp_path / "alias"
    alias.symlink_to(path)
    monkeypatch.setattr(q, "AUTHORIZATION_PATH", alias)
    with pytest.raises(DataError, match="INTRADAY_AUTHORIZATION_UNAVAILABLE"):
        q._read_authorization()


def test_root_file_parser_rejects_duplicate_keys_and_oversize(tmp_path, monkeypatch):
    path = tmp_path / "authorization.json"
    monkeypatch.setattr(q, "AUTHORIZATION_PATH", path)
    real = os.fstat

    def owned(fd):
        info = real(fd)
        return SimpleNamespace(**{name: 0 if name == "st_uid" else getattr(info, name)
                                  for name in dir(info) if name.startswith("st_")})

    proxy = SimpleNamespace(**{name: getattr(os, name) for name in dir(os)})
    proxy.fstat = owned
    monkeypatch.setattr(q, "os", proxy)
    path.write_text(json.dumps({"schema": 1}))
    path.chmod(0o600)
    assert q._read_authorization() == {"schema": 1}
    path.write_text('{"schema":1,"schema":2}')
    with pytest.raises(DataError):
        q._read_authorization()
    path.write_text("x" * 16385)
    with pytest.raises(DataError):
        q._read_authorization()
