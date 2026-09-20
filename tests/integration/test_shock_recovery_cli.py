from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def cli():
    path = Path("scripts/shock_recovery_probe.py")
    spec = importlib.util.spec_from_file_location("shock_recovery_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_evidence_is_preserved_before_input_read(tmp_path):
    module = cli()
    original = tmp_path / "result.json"
    original.write_text("preserved")
    assert module.main(["develop", "--bars-dir", "/missing", "--manifest", "/missing",
                        "--output-dir", str(tmp_path)]) == 2
    assert original.read_text() == "preserved"


def test_no_confirmation_command_or_live_arguments():
    with pytest.raises(SystemExit) as exc:
        cli().main(["confirm", "--bars-dir", "/missing", "--manifest", "/missing"])
    assert exc.value.code == 2


def test_uncommitted_code_fails_before_dataset_access(tmp_path, monkeypatch):
    module = cli()
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **k: " M src/dirty.py")
    monkeypatch.setattr(module.research, "load_development", lambda *a: pytest.fail("dataset read"))
    assert module.main(["develop", "--bars-dir", "/missing", "--manifest", "/missing",
                        "--output-dir", str(tmp_path / "new")]) == 2
    assert not (tmp_path / "new").exists()


def test_wrong_manifest_does_not_create_evidence(tmp_path, monkeypatch):
    module = cli()
    monkeypatch.setattr(module, "clean_commit", lambda: "a" * 40)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    output = tmp_path / "output"
    assert module.main(["develop", "--bars-dir", str(tmp_path), "--manifest", str(manifest),
                        "--output-dir", str(output)]) == 2
    assert not output.exists()


def test_develop_writes_new_bundle_and_verify_replays(tmp_path, monkeypatch, capsys):
    module = cli()
    result = {"verdict": "DEVELOPMENT_REJECTED", "selected_candidate_id": None,
              "ledger_row_count": 0, "content_sha256": "sha256:fixture"}
    monkeypatch.setattr(module, "clean_commit", lambda: "a" * 40)
    monkeypatch.setattr(module.research, "load_development", lambda *a: "dataset")
    monkeypatch.setattr(module.research, "run_development", lambda *a, **k: (result, b""))
    output = tmp_path / "output"
    assert module.main(["develop", "--bars-dir", "/input", "--manifest", "/manifest",
                        "--output-dir", str(output)]) == 0
    assert json.loads((output / "result.json").read_text()) == result
    assert (output / "ledger.jsonl").read_bytes() == b""
    calls = []
    monkeypatch.setattr(module, "read_bundle", lambda *a: (result, b""))
    monkeypatch.setattr(module.research, "verify_development",
                        lambda *a: calls.append(a) or result)
    assert module.main(["verify", "--bars-dir", "/input", "--manifest", "/manifest",
                        "--evidence", str(output)]) == 0
    assert calls[0][:3] == (result, b"", "dataset")
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["capital_eligible"] is False
