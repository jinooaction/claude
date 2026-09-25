"""Hostile input and archive framing counterexamples."""

import gzip
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from auto_invest.analytics import archived_event_evidence as evidence


def framed(block=b"fetchTimeMs: 1470\r\n\r\n", extra=b""):
    return (
        b"WARC/1.0\r\nWARC-Type: metadata\r\n"
        b"WARC-Date: 2014-03-10T00:43:42Z\r\n"
        b"WARC-Record-ID: <urn:uuid:4944037f-d426-4425-bac4-49b0d44fa3f7>\r\n"
        b"Content-Type: application/warc-fields\r\n"
        + b"Content-Length: " + str(len(block)).encode() + b"\r\n" + extra
        + b"\r\n" + block + b"\r\n\r\n"
    )


def read(tmp_path, raw, digest=None):
    path = tmp_path / "record.gz"
    path.write_bytes(raw)
    return evidence.read_record(path, digest or hashlib.sha256(raw).hexdigest(), "metadata")


def test_single_complete_member(tmp_path):
    record = read(tmp_path, gzip.compress(framed()))
    assert record.block == b"fetchTimeMs: 1470\r\n\r\n"
    assert record.headers["warc-date"] == "2014-03-10T00:43:42Z"


@pytest.mark.parametrize("transform", [
    lambda raw: raw[:-1],
    lambda raw: raw + b"trailing",
    lambda raw: raw + gzip.compress(framed()),
    lambda raw: raw[:-8] + b"\x00" * 8,
])
def test_invalid_gzip_rejected(tmp_path, transform):
    with pytest.raises(ValueError):
        read(tmp_path, transform(gzip.compress(framed())))


@pytest.mark.parametrize("raw", [
    framed()[:-1],
    framed() + framed(),
    framed().replace(b"Content-Length: 21", b"Content-Length: 22"),
    framed().replace(b"WARC/1.0", b"WARC/1.1"),
    framed().replace(b"2014-03-10", b"2014-02-30"),
    framed().replace(b"00:43:42Z", b"00:43:42+00:00"),
    framed().replace(b"4944037f", b"not-uuid"),
    framed(extra=b"content-length: 21\r\n"),
    framed(extra=b"WARC-Block-Digest: sha1:INVALID\r\n"),
])
def test_invalid_warc_rejected(tmp_path, raw):
    with pytest.raises(ValueError):
        read(tmp_path, gzip.compress(raw))


def test_wrong_file_digest(tmp_path):
    with pytest.raises(ValueError, match="artifact digest mismatch"):
        read(tmp_path, gzip.compress(framed()), "0" * 64)


def test_bounded_expansion(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "MAX_BYTES", 1024)
    with pytest.raises(ValueError, match="expanded size"):
        read(tmp_path, gzip.compress(framed(b"x" * 2048)))


def test_bounded_source(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "MAX_BYTES", 10)
    with pytest.raises(ValueError, match="input size"):
        read(tmp_path, b"x" * 11)


def manifest():
    return {
        "schema_version": 1, "profile": evidence.PROFILE,
        "artifacts": {name: {"path": name + ".gz", "sha256": "0" * 64}
                      for name in ("response", "metadata", "warcinfo")},
        "index": {"url": "https://example.org", "timestamp": "20140310004342", "digest": "x"},
        "event": {"issuer_cik": "0000104169", "kind": "reported",
                  "event_date": "2014-02-20", "report_period_end": None,
                  "evidence_quotes": ["sample"]},
    }


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(schema_version=True),
    lambda value: value.update(profile="unknown"),
    lambda value: value.update(extra="unexpected"),
    lambda value: value["artifacts"]["response"].update(extra="unexpected"),
    lambda value: value["artifacts"]["response"].update(sha256=42),
])
def test_manifest_structure_rejected(tmp_path, mutation):
    value = manifest()
    mutation(value)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        evidence.load_manifest(path)


@pytest.mark.parametrize("raw", [
    '{"schema_version":1,"schema_version":1}',
    '{"nested":{"key":1,"key":2}}',
    '{"value":NaN}',
    '{"value":Infinity}',
])
def test_duplicate_or_nonstandard_json(tmp_path, raw):
    path = tmp_path / "manifest.json"
    path.write_text(raw)
    with pytest.raises(ValueError):
        evidence.load_manifest(path)


def linked_manifest(tmp_path, *, modifications=None, body=None):
    """Independent tiny archive, with fresh hashes even for semantically invalid links."""
    modifications = modifications or {}
    value = manifest()
    url = value["index"]["url"]
    body = body if body is not None else b"<html><p>sample earnings</p></html>"
    payload_digest = evidence._sha1(body)
    value["index"]["digest"] = payload_digest
    ids = {name: f"<urn:uuid:00000000-0000-0000-0000-00000000000{number}>"
           for number, name in enumerate(("response", "metadata", "warcinfo"), 1)}
    blocks = {
        "response": b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n" + body,
        "metadata": b"fetchTimeMs: 1470\r\n\r\n",
        "warcinfo": b"software: Nutch 1.6 (CC)/CC WarcExport 1.0\r\n\r\n",
    }
    for name, block in blocks.items():
        block = modifications.get(name + "_block", block)
        headers = {
            "WARC-Type": name, "WARC-Date": "2014-03-10T00:43:42Z",
            "WARC-Record-ID": ids[name], "Content-Length": str(len(block)),
            "Content-Type": "application/warc-fields",
        }
        if name != "warcinfo":
            headers.update({"WARC-Target-URI": url, "WARC-Warcinfo-ID": ids["warcinfo"]})
        if name == "response":
            headers.update({
                "Content-Type": "application/http; msgtype=response",
                "WARC-Payload-Digest": "sha1:" + payload_digest,
                "WARC-Block-Digest": "sha1:" + evidence._sha1(block),
                "WARC-Truncated": "length",
            })
        if name == "metadata":
            headers["WARC-Concurrent-To"] = ids["response"]
        headers.update(modifications.get(name, {}))
        raw = gzip.compress(
            ("WARC/1.0\r\n" + "\r\n".join(f"{k}: {v}" for k, v in headers.items())
             + "\r\n\r\n").encode() + block + b"\r\n\r\n", mtime=0,
        )
        (tmp_path / (name + ".gz")).write_bytes(raw)
        value["artifacts"][name]["sha256"] = hashlib.sha256(raw).hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value))
    return path


def test_linked_inspection_preserves_limits(tmp_path):
    path = linked_manifest(tmp_path)
    first, second = evidence.inspect_manifest(path), evidence.inspect_manifest(path)
    assert first["links_verified"] and first["quotes_present"]
    assert first["strategy_admitted"] is False and first["live_eligible"] is False
    interval = first["conditional_provider_interval"]
    assert interval["post_response_lower_inclusive"] == "2014-03-10T00:43:42+00:00"
    assert interval["conditional_use_not_before"] == "2014-03-10T00:43:43+00:00"
    assert interval["fetch_time_ms"] == 1470
    assert interval["duration_added_to_timestamp"] is False
    assert first["warc_truncated"] == "length"
    assert "complete_original_document" in first["unverified"]
    first.pop("local_inspection")
    second.pop("local_inspection")
    assert first == second


@pytest.mark.parametrize("modifications", [
    {"metadata": {"WARC-Concurrent-To": "<urn:uuid:00000000-0000-0000-0000-000000000009>"}},
    {"metadata": {"WARC-Target-URI": "https://different.example.org"}},
    {"response": {"WARC-Warcinfo-ID": "<urn:uuid:00000000-0000-0000-0000-000000000009>"}},
    {"metadata": {"WARC-Date": "2014-03-10T00:43:43Z"}},
    {"response": {"WARC-Payload-Digest": "sha1:" + "A" * 32}},
    {"warcinfo_block": b"software: another crawler\r\n\r\n"},
    {"metadata_block": b"fetchTimeMs: -1\r\n\r\n"},
    {"metadata_block": b"fetchTimeMs: 1.5\r\n\r\n"},
    {"response_block": b"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\nsample"},
])
def test_links_and_profile_rejected(tmp_path, modifications):
    path = linked_manifest(tmp_path, modifications=modifications)
    with pytest.raises(ValueError):
        evidence.inspect_manifest(path)


@pytest.mark.parametrize("body", [
    b"<script>sample</script><p>other text</p>",
    b"<style>sample</style><p>other text</p>",
    b"<iframe src='https://example.org/sample'></iframe>",
    b"<html>sample \xff</html>",
])
def test_unusable_text_rejected(tmp_path, body):
    with pytest.raises(ValueError):
        evidence.inspect_manifest(linked_manifest(tmp_path, body=body))


def test_backward_local_clock(tmp_path, monkeypatch):
    path = linked_manifest(tmp_path)
    now = datetime(2026, 9, 25, tzinfo=UTC)
    clock = iter([now, now - timedelta(seconds=1)])
    monkeypatch.setattr(evidence, "_now", lambda: next(clock))
    with pytest.raises(ValueError, match="local inspection interval"):
        evidence.inspect_manifest(path)


def test_real_exporter_fields_single_final_crlf(tmp_path):
    path = linked_manifest(tmp_path, modifications={
        "warcinfo_block": b"software: Nutch 1.6 (CC)/CC WarcExport 1.0\r\n",
        "warcinfo": {"WARC-Date": "2014-03-18T07:32:17Z"},
    })
    assert evidence.inspect_manifest(path)["links_verified"]


def test_http_cookie_repetition_does_not_relax_framing_fields():
    assert evidence._headers(b"Set-Cookie: a=1\r\nSet-Cookie: b=2", http=True) == {}
    with pytest.raises(ValueError):
        evidence._headers(b"Content-Length: 1\r\ncontent-length: 2", http=True)
    with pytest.raises(ValueError):
        evidence._headers(b"WARC-Record-ID: first\r\nwarc-record-id: second")


def test_output_and_original_are_not_overwritten(tmp_path):
    source = linked_manifest(tmp_path)
    original = source.read_bytes()
    with pytest.raises(FileExistsError):
        evidence.write_inspection(source, source)
    assert source.read_bytes() == original
    output = tmp_path / "report.json"
    result = evidence.write_inspection(source, output)
    assert json.loads(output.read_bytes()) == result
    saved = output.read_bytes()
    with pytest.raises(FileExistsError):
        evidence.write_inspection(source, output)
    assert output.read_bytes() == saved


@pytest.mark.parametrize("field,value", [
    ("issuer_cik", 104169), ("kind", []), ("event_date", "2014-02-30"),
    ("report_period_end", "2014-1-31"), ("evidence_quotes", []),
    ("evidence_quotes", [" "]), ("evidence_quotes", [42]),
])
def test_event_claim_shape(tmp_path, field, value):
    source = linked_manifest(tmp_path)
    data = json.loads(source.read_bytes())
    data["event"][field] = value
    source.write_text(json.dumps(data))
    output = tmp_path / "report.json"
    with pytest.raises(ValueError):
        evidence.write_inspection(source, output)
    assert not output.exists()


@pytest.mark.parametrize("field,value", [
    ("url", "https://user:password@example.org"), ("url", "file:///local/file"),
    ("timestamp", "20140310004343"), ("timestamp", "20140310004342Z"),
    ("timestamp", "20140230004342"), ("digest", "A" * 32), ("digest", "invalid"),
])
def test_index_mismatch_and_invalid_fields(tmp_path, field, value):
    source = linked_manifest(tmp_path)
    data = json.loads(source.read_bytes())
    data["index"][field] = value
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        evidence.inspect_manifest(source)


def test_next_second_reference_rollover_and_boundary(tmp_path):
    source = linked_manifest(tmp_path, modifications={
        name: {"WARC-Date": "2014-12-31T23:59:59Z"} for name in ("response", "metadata")
    })
    data = json.loads(source.read_bytes())
    data["index"]["timestamp"] = "20141231235959"
    source.write_text(json.dumps(data))
    result = evidence.inspect_manifest(source)
    reference = datetime.fromisoformat(
        result["conditional_provider_interval"]["conditional_use_not_before"]
    )
    assert reference == datetime(2015, 1, 1, tzinfo=UTC)
    before = datetime(2014, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    assert not before >= reference
    assert datetime(2015, 1, 1, tzinfo=UTC) >= reference
    assert not result["strategy_admitted"] and not result["live_eligible"]


def test_bom_and_visible_whitespace_normalization(tmp_path):
    source = linked_manifest(tmp_path, body=b"\xef\xbb\xbf<p>sample\n earnings</p>")
    data = json.loads(source.read_bytes())
    data["event"]["evidence_quotes"] = ["sample  earnings"]
    source.write_text(json.dumps(data))
    assert evidence.inspect_manifest(source)["quotes_present"]
