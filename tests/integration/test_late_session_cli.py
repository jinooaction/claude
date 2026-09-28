from __future__ import annotations

import importlib.util
import json
import subprocess

import pytest


def cli():
    spec = importlib.util.spec_from_file_location(
        "late_session_probe", "scripts/late_session_probe.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_evidence_preserved_before_inputs(tmp_path):
    original = tmp_path / "result.json"
    original.write_text("preserved")
    assert cli().main(["develop", "--bars-dir", "/missing", "--manifest", "/missing",
                       "--output-dir", str(tmp_path)]) == 2
    assert original.read_text() == "preserved"


def test_no_confirmation_or_live_command():
    with pytest.raises(SystemExit) as exc:
        cli().main(["confirm", "--bars-dir", "/missing", "--manifest", "/missing"])
    assert exc.value.code == 2


def test_dirty_code_precedes_dataset_access(tmp_path, monkeypatch):
    module = cli()
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **k: " M src/dirty.py")
    monkeypatch.setattr(module.research, "load_development", lambda *a: pytest.fail("price read"))
    assert module.main(["develop", "--bars-dir", "/missing", "--manifest", "/missing",
                        "--output-dir", str(tmp_path / "new")]) == 2
    assert not (tmp_path / "new").exists()


def test_wrong_manifest_does_not_create_output(tmp_path, monkeypatch):
    module = cli()
    monkeypatch.setattr(module, "clean_commit", lambda: "a"*40)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    assert module.main(["develop", "--bars-dir", str(tmp_path), "--manifest", str(manifest),
                        "--output-dir", str(tmp_path / "output")]) == 2
    assert not (tmp_path / "output").exists()


def test_cli_writes_and_passes_bundle_to_replay(tmp_path, monkeypatch, capsys):
    module = cli()
    result = {"verdict": "DEVELOPMENT_REJECTED", "selected_candidate_id": None,
              "ledger_row_count": 0, "content_sha256": "sha256:fixture"}
    monkeypatch.setattr(module, "clean_commit", lambda: "a"*40)
    monkeypatch.setattr(module.research, "load_development", lambda *a: "dataset")
    monkeypatch.setattr(module.research, "run_development", lambda *a, **k: (result, b""))
    output = tmp_path / "new"
    assert module.main(["develop", "--bars-dir", "/input", "--manifest", "/manifest",
                        "--output-dir", str(output)]) == 0
    assert json.loads((output / "result.json").read_text()) == result
    assert (output / "ledger.jsonl").read_bytes() == b""
    monkeypatch.setattr(module, "read_bundle", lambda *a: (result, b""))
    calls = []
    monkeypatch.setattr(module.research, "verify_development", lambda *a: calls.append(a) or result)
    assert module.main(["verify", "--bars-dir", "/input", "--manifest", "/manifest",
                        "--evidence", str(output)]) == 0
    assert calls[0][:3] == (result, b"", "dataset")
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["capital_eligible"] is False


def test_historical_code_mismatch_rejected_before_prices(tmp_path, monkeypatch):
    module = cli()
    (tmp_path / "result.json").write_text(json.dumps({"code_commit": "a"*40}))
    (tmp_path / "ledger.jsonl").write_bytes(b"")
    monkeypatch.setattr(module.research, "validate_seal", lambda *a: None)
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[1] == "diff":
            raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        module.read_bundle(tmp_path)
    diff, = [args for args in calls if args[1] == "diff"]
    assert "src" in diff and "scripts/late_session_probe.py" in diff
