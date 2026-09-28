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
