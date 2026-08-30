from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_PROBE_PATH = Path("scripts/accounting_factor_factory_probe.py")
_SPEC = importlib.util.spec_from_file_location("accounting_factor_factory_probe", _PROBE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


def test_probe_exposes_two_vintages_retry_and_no_money_boundary() -> None:
    result = subprocess.run(
        [sys.executable, str(_PROBE_PATH), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--archive-file" in result.stdout
    assert "--current-file" in result.stdout
    assert "--prior-factory-json" in result.stdout
    assert "--calibration-json" in result.stdout
    assert "--result-schema" in result.stdout
    text = _PROBE_PATH.read_text(encoding="utf-8")
    assert "run_accounting_factor_factory" in text
    assert "parse_fama_french_five_factor_zip" in text
    assert "for attempt in range(3)" in text
    assert "KIS_" not in text
    assert "auto_invest.broker" not in text


def test_probe_writes_schema_checked_json_and_markdown(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "archive.zip"
    current = tmp_path / "current.zip"
    prior = tmp_path / "prior.json"
    calibration = tmp_path / "calibration.json"
    schema = tmp_path / "schema.json"
    json_out = tmp_path / "result.json"
    summary_out = tmp_path / "result.md"
    archive.write_bytes(b"archive")
    current.write_bytes(b"current")
    prior.write_text('{"audit_records": []}', encoding="utf-8")
    calibration.write_text("{}", encoding="utf-8")
    schema.write_text('{"type":"object"}', encoding="utf-8")
    expected = {
        "decision": {"verdict": "NO_FACTORY_EDGE"},
        "holdout": {"psr": "0.5"},
        "promotion_allowed": False,
        "safety": {
            "orders_submitted": 0,
            "capital_changed": False,
            "live_strategy_changed": False,
        },
    }
    monkeypatch.setattr(probe, "parse_fama_french_five_factor_zip", lambda raw: ())
    monkeypatch.setattr(probe, "build_accounting_factor_bundle", lambda *args, **kwargs: "bundle")
    monkeypatch.setattr(probe, "run_accounting_factor_factory", lambda **kwargs: expected)
    monkeypatch.setattr(probe, "render_accounting_factor_markdown", lambda payload: "# result")
    monkeypatch.setattr(probe, "_validate_schema", lambda payload, schema_payload: None)

    code = probe.main(
        [
            "--archive-file",
            str(archive),
            "--current-file",
            str(current),
            "--prior-factory-json",
            str(prior),
            "--calibration-json",
            str(calibration),
            "--result-schema",
            str(schema),
            "--timestamp-utc",
            "2026-08-31T00:00:00Z",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
        ]
    )

    assert code == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["safety"]["orders_submitted"] == 0
    assert summary_out.read_text(encoding="utf-8").startswith("# result")
