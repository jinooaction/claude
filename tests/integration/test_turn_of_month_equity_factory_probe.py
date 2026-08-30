from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_PROBE_PATH = Path("scripts/turn_of_month_equity_factory_probe.py")
_SPEC = importlib.util.spec_from_file_location("turn_of_month_equity_factory_probe", _PROBE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


def test_probe_exposes_offline_inputs_and_no_money_boundary() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/turn_of_month_equity_factory_probe.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--french-daily-file" in result.stdout
    assert "--prior-factory-json" in result.stdout
    assert "--released-regime-json" in result.stdout
    assert "--calibration-json" in result.stdout
    text = Path("scripts/turn_of_month_equity_factory_probe.py").read_text(encoding="utf-8")
    assert "run_turn_of_month_equity_factory" in text
    assert "parse_fama_french_daily" in text
    assert "KIS_" not in text
    assert "auto_invest.broker" not in text


def test_probe_writes_json_and_markdown_outputs(tmp_path: Path, monkeypatch) -> None:
    prior = tmp_path / "prior.json"
    regime = tmp_path / "regime.json"
    calibration = tmp_path / "calibration.json"
    french = tmp_path / "french.zip"
    json_out = tmp_path / "result.json"
    summary_out = tmp_path / "result.md"
    prior.write_text('{"audit_records": []}', encoding="utf-8")
    regime.write_text("{}", encoding="utf-8")
    calibration.write_text("{}", encoding="utf-8")
    french.write_bytes(b"fixture")
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
    monkeypatch.setattr(probe, "parse_fama_french_daily", lambda raw: ())
    monkeypatch.setattr(probe, "build_french_daily_bundle", lambda *args, **kwargs: "bundle")
    monkeypatch.setattr(probe, "run_turn_of_month_equity_factory", lambda **kwargs: expected)
    monkeypatch.setattr(probe, "render_turn_of_month_markdown", lambda payload: "# result")

    code = probe.main(
        [
            "--french-daily-file",
            str(french),
            "--prior-factory-json",
            str(prior),
            "--released-regime-json",
            str(regime),
            "--calibration-json",
            str(calibration),
            "--timestamp-utc",
            "2026-08-30T00:00:00Z",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
        ]
    )

    assert code == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["safety"]["orders_submitted"] == 0
    assert summary_out.read_text(encoding="utf-8").startswith("# result")
