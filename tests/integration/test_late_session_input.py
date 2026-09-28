from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    spec = importlib.util.spec_from_file_location(
        "unpack_late_session_input", "scripts/unpack_late_session_input.py",
    )
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def synthetic_bundle(tmp_path, monkeypatch):
    loaded = module()
    source = tmp_path / "source"
    source.mkdir()
    files = {}
    for symbol in loaded.SYMBOLS:
        payload = (symbol + " synthetic test only\n").encode()
        (source / f"{symbol}.csv.gz").write_bytes(gzip.compress(payload))
        files[symbol] = {"sha256": "sha256:" + hashlib.sha256(payload).hexdigest()}
    raw = json.dumps({"files": files}).encode()
    (source / "manifest.json").write_bytes(raw)
    monkeypatch.setattr(loaded, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    return loaded, source


def test_unpack_verifies_all_payloads_before_writing(tmp_path, monkeypatch):
    loaded, source = synthetic_bundle(tmp_path, monkeypatch)
    output = tmp_path / "output"
    result = loaded.unpack(source, output)
    assert result["valid"] and result["holdout_included"] is False
    assert (output / "manifest.json").read_bytes() == (source / "manifest.json").read_bytes()
    for symbol in loaded.SYMBOLS:
        assert (output / f"{symbol}.csv").read_bytes() == (symbol+" synthetic test only\n").encode()
    with pytest.raises(ValueError, match="already exists"):
        loaded.unpack(source, output)


def test_tampered_payload_cannot_leave_partial_bundle(tmp_path, monkeypatch):
    loaded, source = synthetic_bundle(tmp_path, monkeypatch)
    (source / "GLD.csv.gz").write_bytes(gzip.compress(b"tampered"))
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="fingerprint"):
        loaded.unpack(source, output)
    assert not output.exists()


def test_expansion_is_bounded_and_manifest_precedes_payloads(tmp_path, monkeypatch):
    loaded, source = synthetic_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(loaded, "MAX_CSV_BYTES", 5)
    with pytest.raises(ValueError, match="size bound"):
        loaded.unpack(source, tmp_path / "output")
    (source / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest fingerprint"):
        loaded.unpack(source, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_bundled_manifest_is_the_preregistered_development_only():
    loaded = module()
    raw = (Path("research-fixtures/198") / "manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == loaded.MANIFEST_SHA256
    assert json.loads(raw)["dataset_id"] == "hf-pitrading-coverage-frozen-20130823-20200306"
