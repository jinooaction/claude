"""Recover retained evidence without moving its availability into the past."""

import hashlib

import pytest

from auto_invest.analytics.filing_observations import Observation, RunStore
from auto_invest.analytics.filing_recovery import recover


def source_store(root, raw=b"source"):
    store = RunStore(root, clock=lambda: "2026-09-28T12:00:05Z")
    item = Observation(
        "84dc0271-07f0-41ea-856b-510002131b80", "0000789019",
        "0000789019-26-000001", "primary",
        "https://www.sec.gov/Archives/edgar/data/789019/000078901926000001/doc.htm",
        store.blobs.put(raw), "2026-09-28T12:00:00Z", "2026-09-28T12:00:01Z",
        "2026-09-28T12:00:02Z", {},
    )
    store.publish({
        "schema_version": 1, "run_id": "old", "source_commit": "a" * 40,
        "config_sha256": "b" * 64, "started_at": "2026-09-28T12:00:00Z",
        "ended_at": "2026-09-28T12:00:03Z", "previous_run_sha256": None,
        "observations": [], "failures": [{"issuer_cik": "0000789019", "code": "http_5xx"}],
        "coverage": {"succeeded": 1, "failed": 1, "skipped": 2},
        "circuit": {"consecutive_failures": 0, "cooldown_until": None},
    }, [item])
    return store


def test_recovery_preserves_artifact_and_delays_visibility(tmp_path):
    source = source_store(tmp_path / "artifact")
    before = {str(p.relative_to(source.root)): p.read_bytes()
              for p in source.root.rglob("*") if p.is_file()}
    destination = RunStore(tmp_path / "store", clock=lambda: "2026-09-28T13:00:00Z")
    recover(destination, source.root, run_id="recovery", source_commit="c" * 40)
    assert destination.query("2026-09-28T12:59:59Z")["observations"] == []
    result = destination.query("2026-09-28T13:00:00Z")
    assert len(result["observations"]) == 1
    assert result["observations"][0]["available_at"] == "2026-09-28T13:00:00Z"
    assert result["observations"][0]["verified_at"] == "2026-09-28T12:00:02Z"
    assert result["recovered_runs"][0]["manifest"]["coverage"]["skipped"] == 2
    assert result["recovered_runs"][0]["manifest"]["failures"][0]["code"] == "http_5xx"
    assert before == {str(p.relative_to(source.root)): p.read_bytes()
                      for p in source.root.rglob("*") if p.is_file()}


def test_corrupt_source_rejected_without_publishing(tmp_path):
    source = source_store(tmp_path / "artifact")
    (source.root / "blobs" / hashlib.sha256(b"source").hexdigest()).write_bytes(b"bad")
    destination = RunStore(tmp_path / "store")
    with pytest.raises(ValueError):
        recover(destination, source.root, run_id="recovery", source_commit="c" * 40)
    assert destination.verify() == []


def test_recovery_keeps_current_chain_and_avoids_duplicate_receipts(tmp_path):
    source = source_store(tmp_path / "artifact")
    destination = source_store(tmp_path / "store")
    destination.clock = lambda: "2026-09-28T13:00:00Z"
    before = destination.query("2026-09-28T12:00:05Z")
    recover(destination, source.root, run_id="recovery", source_commit="c" * 40)
    assert destination.query("2026-09-28T12:00:05Z") == before
    assert len(destination.query("2026-09-28T13:00:00Z")["observations"]) == 1


def test_recovery_refuses_overlap_and_future_source(tmp_path):
    source = source_store(tmp_path / "artifact")
    with pytest.raises(ValueError, match="overlap"):
        recover(source, source.root, run_id="recovery", source_commit="c" * 40)
    destination = RunStore(tmp_path / "store", clock=lambda: "2026-09-28T11:00:00Z")
    with pytest.raises(ValueError, match="clock"):
        recover(destination, source.root, run_id="recovery", source_commit="c" * 40)


def test_conflicting_id_is_rejected_before_new_run(tmp_path):
    source = source_store(tmp_path / "artifact", b"different")
    destination = source_store(tmp_path / "store")
    destination.clock = lambda: "2026-09-28T13:00:00Z"
    with pytest.raises(ValueError, match="conflicting"):
        recover(destination, source.root, run_id="recovery", source_commit="c" * 40)
    assert len(destination.verify()) == 1


def test_archived_bytes_remain_verifiable_after_source_disappears(tmp_path):
    import shutil

    source = source_store(tmp_path / "artifact")
    destination = RunStore(tmp_path / "store", clock=lambda: "2026-09-28T13:00:00Z")
    recover(destination, source.root, run_id="recovery", source_commit="c" * 40)
    shutil.rmtree(source.root)
    assert len(destination.query("2026-09-28T13:00:00Z")["observations"]) == 1
    digest = hashlib.sha256(b"source").hexdigest()
    (destination.root / "blobs" / digest).write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest"):
        destination.verify()


def test_recover_artifact_that_already_contains_recovery(tmp_path):
    source = source_store(tmp_path / "artifact")
    first = RunStore(tmp_path / "first", clock=lambda: "2026-09-28T13:00:00Z")
    recover(first, source.root, run_id="first", source_commit="c" * 40)
    second = RunStore(tmp_path / "second", clock=lambda: "2026-09-28T14:00:00Z")
    recover(second, first.root, run_id="second", source_commit="c" * 40)
    assert second.query("2026-09-28T13:59:59Z")["observations"] == []
    result = second.query("2026-09-28T14:00:00Z")
    assert len(result["observations"]) == 1
    assert result["observations"][0]["verified_at"] == "2026-09-28T12:00:02Z"
