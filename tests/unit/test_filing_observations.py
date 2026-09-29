"""First-observation evidence must retain bytes and honest receipt times."""

import hashlib
from dataclasses import replace

import pytest

from auto_invest.analytics.filing_observations import BlobStore, Observation


def observation(**changes):
    values = dict(
        observation_id="84dc0271-07f0-41ea-856b-510002131b80",
        issuer_cik="0000789019",
        accession="0000789019-26-000001",
        source_kind="primary",
        url="https://www.sec.gov/Archives/edgar/data/789019/000078901926000001/doc.htm",
        blob_sha256=hashlib.sha256(b"original").hexdigest(),
        requested_at="2026-09-28T12:00:00Z",
        received_at="2026-09-28T12:00:01Z",
        verified_at="2026-09-28T12:00:02Z",
        source_claims={"acceptance_datetime": "2026-09-27T10:00:00"},
    )
    values.update(changes)
    return Observation(**values)


def test_receipt_round_trip_and_untrusted_source_time():
    item = observation()
    assert Observation.from_dict(item.to_dict()) == item
    assert item.available_at == item.verified_at
    assert item.available_at != item.source_claims["acceptance_datetime"]


@pytest.mark.parametrize("changes", [
    {"received_at": "2026-09-28T11:59:59Z"},
    {"verified_at": "2026-09-28T12:00:00Z"},
    {"requested_at": "2026-09-28T12:00:00"},
    {"requested_at": "2026-09-28T21:00:00+09:00"},
    {"issuer_cik": "789019"},
    {"observation_id": "../../escape"},
    {"blob_sha256": "A" * 64},
    {"url": "https://www.sec.gov.evil.test/Archives/edgar/data/789019/doc.htm"},
    {"url": "https://www.sec.gov/Archives/edgar/data/1/000078901926000001/doc.htm"},
    {"url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000002/doc.htm"},
    {"url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000001/../doc.htm"},
    {"source_claims": {"user_agent": "private contact"}},
])
def test_invalid_receipt_rejected(changes):
    with pytest.raises(ValueError):
        observation(**changes)


def test_closed_fields_and_defensive_copy():
    source = observation().to_dict()
    item = Observation.from_dict(source)
    source["source_claims"]["acceptance_datetime"] = "changed"
    assert item.source_claims["acceptance_datetime"] != "changed"
    source["extra"] = True
    with pytest.raises(ValueError):
        Observation.from_dict(source)


def test_listing_requires_exact_cik_url_and_no_accession():
    item = observation(source_kind="listing", accession=None,
                       url="https://data.sec.gov/submissions/CIK0000789019.json",
                       source_claims={})
    assert item.source_kind == "listing"
    with pytest.raises(ValueError):
        replace(item, accession="0000789019-26-000001")


def test_same_bytes_never_rewritten_and_corruption_rejected(tmp_path):
    store = BlobStore(tmp_path)
    digest = store.put(b"original")
    path = tmp_path / "blobs" / digest
    before = path.stat().st_mtime_ns
    assert store.put(b"original") == digest
    assert path.stat().st_mtime_ns == before
    assert store.read(digest) == b"original"
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest"):
        store.put(b"original")


def test_blob_traversal_and_symlinks_rejected(tmp_path):
    store = BlobStore(tmp_path / "store")
    with pytest.raises(ValueError):
        store.read("../secret")
    digest = hashlib.sha256(b"secret").hexdigest()
    secret = tmp_path / "secret"
    secret.write_bytes(b"secret")
    (store.root / "blobs" / digest).symlink_to(secret)
    with pytest.raises(ValueError, match="symlink"):
        store.read(digest)
    alias = tmp_path / "alias"
    alias.symlink_to(store.root, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        BlobStore(alias)


def test_blob_size_bounded_before_write(tmp_path):
    store = BlobStore(tmp_path, max_bytes=4)
    with pytest.raises(ValueError, match="size"):
        store.put(b"12345")
    assert list((tmp_path / "blobs").iterdir()) == []


def run_manifest(**changes):
    result = dict(
        schema_version=1, run_id="run-1", source_commit="a" * 40,
        config_sha256="b" * 64, started_at="2026-09-28T12:00:00Z",
        ended_at="2026-09-28T12:00:03Z", previous_run_sha256=None,
        observations=[], failures=[],
        coverage={"succeeded": 1, "failed": 0, "skipped": 0},
        circuit={"consecutive_failures": 0, "cooldown_until": None},
    )
    result.update(changes)
    return result


def publish(store, item=None, **changes):
    item = item or observation()
    store.blobs.put(b"original")
    return store.publish(run_manifest(**changes), [item])


def test_run_visibility_waits_for_finalization_and_ignores_orphans(tmp_path):
    from auto_invest.analytics.filing_observations import RunStore

    store = RunStore(tmp_path, clock=lambda: "2026-09-28T12:00:05Z")
    store.blobs.put(b"orphan")
    assert store.query("2026-09-28T12:00:10Z")["observations"] == []
    publish(store)
    assert store.query("2026-09-28T12:00:04Z")["observations"] == []
    result = store.query("2026-09-28T12:00:05Z")
    assert len(result["observations"]) == 1
    assert result["observations"][0]["available_at"] == "2026-09-28T12:00:05Z"
    assert result["scope"] == "collector_local_observation_only"


def test_run_chain_rejects_reversal_duplicate_and_wrong_parent(tmp_path):
    from auto_invest.analytics.filing_observations import RunStore

    store = RunStore(tmp_path, clock=lambda: "2026-09-28T12:00:05Z")
    first = publish(store)
    with pytest.raises(ValueError, match="duplicate"):
        publish(store)
    with pytest.raises(ValueError, match="previous"):
        publish(store, run_id="run-2")
    with pytest.raises(ValueError, match="clock"):
        publish(store, run_id="run-2", previous_run_sha256=first)


def test_tampered_receipt_and_manifest_fail_closed(tmp_path):
    import json

    from auto_invest.analytics.filing_observations import RunStore

    store = RunStore(tmp_path, clock=lambda: "2026-09-28T12:00:05Z")
    publish(store)
    receipt = tmp_path / "observations" / f"{observation().observation_id}.json"
    original = receipt.read_bytes()
    receipt.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="digest"):
        store.verify()
    receipt.write_bytes(original)
    path = tmp_path / "runs/run-1.json"
    value = json.loads(path.read_bytes())
    value["manifest"]["ended_at"] = "2026-09-28T12:00:04Z"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="digest"):
        store.verify()


def test_failed_run_preserves_past_query_and_is_visible(tmp_path):
    from auto_invest.analytics.filing_observations import RunStore

    ticks = iter(["2026-09-28T12:00:05Z", "2026-09-28T12:00:15Z"])
    store = RunStore(tmp_path, clock=lambda: next(ticks))
    first = publish(store)
    before = store.query("2026-09-28T12:00:05Z")
    store.publish(run_manifest(
        run_id="run-2", previous_run_sha256=first,
        started_at="2026-09-28T12:00:10Z", ended_at="2026-09-28T12:00:12Z",
        coverage={"succeeded": 0, "failed": 1, "skipped": 2},
        failures=[{"issuer_cik": "0000789019", "code": "http_403"}],
        circuit={"consecutive_failures": 1, "cooldown_until": "2026-09-28T12:15:12Z"},
    ), [])
    assert store.query("2026-09-28T12:00:05Z") == before
    assert len(store.query("2026-09-28T12:00:15Z")["runs"]) == 2


def test_finalization_clock_reversal_does_not_publish(tmp_path):
    from auto_invest.analytics.filing_observations import RunStore

    store = RunStore(tmp_path, clock=lambda: "2026-09-28T12:00:01Z")
    with pytest.raises(ValueError, match="clock"):
        publish(store)
    assert list((tmp_path / "runs").iterdir()) == []


def test_incomplete_manifest_and_duplicate_json_rejected(tmp_path):
    from auto_invest.analytics.filing_observations import RunStore

    store = RunStore(tmp_path)
    path = tmp_path / "runs/incomplete.json"
    path.write_text('{"manifest": {}, "manifest": {}}')
    with pytest.raises(ValueError, match="duplicate"):
        store.verify()
    path.write_text('{"manifest": {}}')
    with pytest.raises(ValueError, match="fields"):
        store.verify()


def test_changed_source_is_new_version_without_rewriting_past(tmp_path):
    from auto_invest.analytics.filing_observations import RunStore

    ticks = iter(["2026-09-28T12:00:05Z", "2026-09-28T12:00:15Z"])
    store = RunStore(tmp_path, clock=lambda: next(ticks))
    first = publish(store)
    before = store.query("2026-09-28T12:00:05Z")
    changed = observation(
        observation_id="27d8b9c0-6b58-4818-bce7-349a323a2f89",
        blob_sha256=store.blobs.put(b"corrected"),
        requested_at="2026-09-28T12:00:10Z",
        received_at="2026-09-28T12:00:11Z",
        verified_at="2026-09-28T12:00:12Z",
    )
    store.publish(run_manifest(
        run_id="run-2", previous_run_sha256=first,
        started_at="2026-09-28T12:00:10Z", ended_at="2026-09-28T12:00:13Z",
    ), [changed])
    assert store.query("2026-09-28T12:00:05Z") == before
    versions = store.query("2026-09-28T12:00:15Z")["observations"]
    assert [store.blobs.read(item["blob_sha256"]) for item in versions] == [
        b"original", b"corrected",
    ]


@pytest.mark.parametrize("parent", [None, "c" * 64])
def test_fork_or_missing_parent_never_silently_selected(tmp_path, parent):
    import json

    from auto_invest.analytics.filing_observations import RunStore

    store = RunStore(tmp_path, clock=lambda: "2026-09-28T12:00:05Z")
    publish(store)
    original = tmp_path / "runs/run-1.json"
    envelope = json.loads(original.read_bytes())
    envelope["manifest"]["run_id"] = "fork"
    envelope["manifest"]["previous_run_sha256"] = parent
    encoded = (json.dumps(envelope["manifest"], sort_keys=True,
                          separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    envelope["manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
    (tmp_path / "runs/fork.json").write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="chain"):
        store.verify()


def test_symlink_run_directory_is_rechecked_on_read(tmp_path):
    from auto_invest.analytics.filing_observations import RunStore

    store = RunStore(tmp_path / "store")
    (store.root / "runs").rmdir()
    external = tmp_path / "external"
    external.mkdir()
    (store.root / "runs").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        store.verify()


@pytest.mark.parametrize("changes", [
    {"run_id": "../../escape"},
    {"source_commit": "main"},
    {"config_sha256": "bad"},
    {"schema_version": True},
    {"coverage": {"succeeded": 0, "failed": 0, "skipped": 0}},
    {"coverage": {"succeeded": True, "failed": 0, "skipped": 0}},
    {"circuit": {"consecutive_failures": -1, "cooldown_until": None}},
    {"failures": [{"issuer_cik": "0000789019", "code": "private raw HTTP headers"}]},
])
def test_invalid_run_writes_no_receipts(tmp_path, changes):
    from auto_invest.analytics.filing_observations import RunStore

    store = RunStore(tmp_path, clock=lambda: "2026-09-28T12:00:05Z")
    with pytest.raises(ValueError):
        publish(store, **changes)
    assert list((tmp_path / "observations").iterdir()) == []


def test_interrupted_completion_cannot_expose_receipt(tmp_path, monkeypatch):
    from auto_invest.analytics import filing_observations as module

    store = module.RunStore(tmp_path, clock=lambda: "2026-09-28T12:00:05Z")
    original = module._publish_file

    def fail_marker(path, raw):
        if path.parent.name == "runs":
            raise OSError("simulated full disk")
        original(path, raw)

    monkeypatch.setattr(module, "_publish_file", fail_marker)
    with pytest.raises(OSError):
        publish(store)
    assert len(list((tmp_path / "observations").iterdir())) == 1
    assert store.query("2026-09-28T12:00:10Z")["observations"] == []
