from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_existing_output_refused_before_any_input_read(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    output.mkdir()
    preserved = output / "result.json"
    preserved.write_text("original evidence")
    result = subprocess.run(
        [sys.executable, "scripts/cost_aware_intraday_probe.py", "develop",
         "--bars-dir", str(tmp_path / "missing"), "--manifest", str(tmp_path / "missing.json"),
         "--output-dir", str(output)],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert "already exists" in result.stderr
    assert preserved.read_text() == "original evidence"


def test_development_command_has_no_holdout_input() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/cost_aware_intraday_probe.py", "--help"],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    assert "--holdout" not in result.stdout


def test_forged_bundle_is_rejected_before_missing_source_is_read(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "result.json").write_text(json.dumps({"verdict": "SELECTION_SEALED"}))
    (evidence / "ledger.jsonl").write_bytes(b"")
    result = subprocess.run(
        [sys.executable, "scripts/cost_aware_intraday_evidence_gate.py", "develop",
         "--evidence", str(evidence), "--bars-dir", str(tmp_path / "never-read"),
         "--manifest", str(tmp_path / "never-read.json")],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assessment = json.loads(result.stdout)
    assert assessment["valid"] is False
    assert "content fingerprint" in assessment["reasons"][0]


def test_confirmation_input_helper_refuses_rejection_before_source_read(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "research_cli", "scripts/cost_aware_intraday_probe.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "read_bundle", lambda *a: (
        {"verdict": "DEVELOPMENT_REJECTED", "selected_candidate_id": None}, b""))
    def never_read(*args, **kwargs):
        pytest.fail("rejected development must not access any source files")
    monkeypatch.setattr(module, "load_intraday_dataset", never_read)
    args = SimpleNamespace(development=Path("evidence"), development_bars_dir=Path("bars"),
                           development_manifest=Path("manifest"))
    with pytest.raises(ValueError, match="holdout must remain unopened"):
        module.verified_development_inputs(args, {}, {}, require_selected=True)
