import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from freezegun import freeze_time

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.execution import intraday_registration as registration
from auto_invest.execution.intraday_selection import ResearchSelection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import DataError

PREREG = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
STAMP = datetime(2026, 9, 9, 12, tzinfo=UTC)


@pytest.fixture
def selected(monkeypatch):
    provider = "kis-nasdaq-partial-unadjusted"
    candidate = build_candidate_registry(load_preregistration(PREREG))[-1]
    value = ResearchSelection(candidate, provider, "a" * 40, "dataset", "research",
                              execution_fingerprint(candidate, provider),
                              "PAPER_CHALLENGER", 756, 0)
    monkeypatch.setattr(registration, "_read_key", lambda: b"k" * 32)
    monkeypatch.setattr(registration.subprocess, "check_output", lambda *a, **k: "a" * 40)
    monkeypatch.setattr(registration, "select_research", lambda *a: value)
    return value


def issue(tmp_path):
    with freeze_time(STAMP):
        return registration.register(tmp_path, PREREG)


def test_issue_uses_server_time_and_checks_exact_identity(tmp_path, selected):
    record = issue(tmp_path)
    with freeze_time(STAMP + timedelta(seconds=1)):
        assert registration.verify_registration(record, selected, PREREG) == STAMP
        with pytest.raises(DataError, match="REGISTRATION_IDENTITY_CHANGED"):
            registration.verify_registration(record, replace(selected, research_digest="changed"),
                                             PREREG)
    with freeze_time(STAMP - timedelta(seconds=1)), pytest.raises(
        DataError, match="REGISTRATION_TIME_INVALID",
    ):
        registration.verify_registration(record, selected, PREREG)


def test_tampering_and_key_rotation_invalidate_record(tmp_path, selected, monkeypatch):
    original = issue(tmp_path)
    record = json.loads(original)
    record["payload"]["frozen_at"] = "2020-01-01T00:00:00Z"
    with pytest.raises(DataError, match="REGISTRATION_SIGNATURE_INVALID"):
        registration.verify_registration(json.dumps(record).encode(), selected, PREREG)
    monkeypatch.setattr(registration, "_read_key", lambda: b"z" * 32)
    with pytest.raises(DataError, match="REGISTRATION_SIGNATURE_INVALID"):
        registration.verify_registration(original, selected, PREREG)


def test_registration_rejects_research_failure(tmp_path, selected, monkeypatch):
    monkeypatch.setattr(registration, "select_research", lambda *a:
                        replace(selected, candidate=None, verdict="INSUFFICIENT_EVIDENCE"))
    with pytest.raises(DataError, match="REGISTRATION_RESEARCH_INVALID"):
        registration.register(tmp_path, PREREG)


@pytest.mark.parametrize("record", [b"{}", b"[]", b"x" * 16385,
                                    b'{"payload":{},"payload":{},"signature":"x"}'])
def test_malformed_record_is_closed_error(selected, record):
    with pytest.raises(DataError, match="REGISTRATION_FORMAT_INVALID"):
        registration.verify_registration(record, selected, PREREG)


def test_key_missing_user_owned_or_symlink_is_rejected(tmp_path, monkeypatch):
    key = tmp_path / "key"
    monkeypatch.setattr(registration, "KEY_PATH", key)
    with pytest.raises(DataError, match="REGISTRATION_KEY_UNAVAILABLE"):
        registration._read_key()
    key.write_bytes(b"k" * 32)
    key.chmod(0o666)
    with pytest.raises(DataError, match="REGISTRATION_KEY_INVALID"):
        registration._read_key()
    alias = tmp_path / "alias"
    alias.symlink_to(key)
    monkeypatch.setattr(registration, "KEY_PATH", alias)
    with pytest.raises(DataError, match="REGISTRATION_KEY_UNAVAILABLE"):
        registration._read_key()


def test_signed_freeze_is_passed_to_replay_without_granting_execution(
    tmp_path, selected, monkeypatch,
):
    record = issue(tmp_path)
    seen = []

    def replay(database, selection, preregistration, *, frozen_at, now, include_interval_bars):
        assert include_interval_bars is False
        assert preregistration != PREREG
        assert preregistration.read_bytes() == PREREG.read_bytes()
        seen.append(frozen_at)
        return dict(freeze_authentication_verified=False, execution_parity_verified=False,
                    live_eligible=False, orders_submitted=0)

    monkeypatch.setattr(registration, "assess_forward", replay)
    with freeze_time(STAMP + timedelta(seconds=1)):
        result = registration.assess_registered_forward(tmp_path, record, selected, PREREG)
    assert seen == [STAMP]
    assert result["freeze_authentication_verified"] is True
    assert result["execution_parity_verified"] is False
    assert result["live_eligible"] is False


def test_issuer_freezes_registration_before_research(tmp_path, selected, monkeypatch):
    prereg = tmp_path / "input.json"
    raw = PREREG.read_bytes()
    prereg.write_bytes(raw)

    def research(archives, frozen, commit):
        assert frozen != prereg and frozen.read_bytes() == raw
        assert commit == "a" * 40
        prereg.write_text("concurrent change")
        return selected

    monkeypatch.setattr(registration, "select_research", research)
    with freeze_time(STAMP):
        record = registration.register(tmp_path, prereg)
        assert registration.verify_registration(record, selected, PREREG) == STAMP


def test_secure_root_key_is_read_and_bad_size_is_rejected(tmp_path, monkeypatch):
    import os

    key = tmp_path / "key"
    key.write_bytes(b"k" * 32)
    key.chmod(0o640)
    monkeypatch.setattr(registration, "KEY_PATH", key)
    real_stat = os.fstat

    def root_owned(fd):
        values = list(real_stat(fd))
        values[4] = 0
        return os.stat_result(values)

    monkeypatch.setattr(registration.os, "fstat", root_owned)
    assert registration._read_key() == b"k" * 32
    key.write_bytes(b"k" * 31)
    with pytest.raises(DataError, match="REGISTRATION_KEY_INVALID"):
        registration._read_key()
