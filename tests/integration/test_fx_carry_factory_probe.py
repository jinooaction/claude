from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    shiller, gold = tmp_path / "shiller.csv", tmp_path / "gold.csv"
    shiller_lines = ["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate"]
    gold_lines = ["Date,Price"]
    year, month = 1990, 1
    for index in range(37 * 12):
        current = f"{year:04d}-{month:02d}-01"
        shiller_lines.append(
            f"{current},{100 * 1.006**index},2,5,100,{3 + index % 24 / 20}"
        )
        gold_lines.append(f"{year:04d}-{month:02d},{400 * 1.004**index}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    shiller.write_text("\n".join(shiller_lines) + "\n", encoding="utf-8")
    gold.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")

    data = tmp_path / "public-data" / "fred"
    data.mkdir(parents=True)
    spot_series = ("DEXUSAL", "DEXCAUS", "DEXJPUS", "DEXUSUK")
    current = date(1980, 1, 1)
    spot_lines = {series_id: [f"observation_date,{series_id}"] for series_id in spot_series}
    index = 0
    while current <= date(2026, 8, 24):
        values = (0.7 + index % 100 / 10000, 1.2 + index % 100 / 10000,
                  100 + index % 100 / 100, 1.3 + index % 100 / 10000)
        for series_id, value in zip(spot_series, values, strict=True):
            spot_lines[series_id].append(f"{current.isoformat()},{value}")
        current, index = current + timedelta(days=1), index + 1
    for series_id, lines in spot_lines.items():
        (data / f"{series_id}.csv").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    rate_series = (
        "IRSTCI01AUM156N",
        "IRSTCI01CAM156N",
        "IRSTCI01JPM156N",
        "IRSTCI01GBM156N",
        "IRSTCI01USM156N",
    )
    for offset, series_id in enumerate(rate_series):
        lines = [f"observation_date,{series_id}"]
        year, month = 1990, 1
        index = 0
        while (year, month) <= (2026, 7):
            lines.append(f"{year:04d}-{month:02d}-01,{2 + offset + index % 12 / 20}")
            month += 1
            index += 1
            if month == 13:
                year, month = year + 1, 1
        (data / f"{series_id}.csv").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    prior = tmp_path / "prior.json"
    prior.write_text(
        json.dumps(
            {
                "audit_records": [
                    {
                        "candidate_id": f"prior-{index:03d}",
                        "strategy_fingerprint": f"sha256:prior-{index:03d}",
                        "status": "complete",
                        "segment_sharpes": [0.1] * 10,
                    }
                    for index in range(640)
                ]
            }
        ),
        encoding="utf-8",
    )
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "gate_version": "2.0",
                "verdict": "CALIBRATED",
                "code_commit": "abc123",
                "scenario": {"repetitions": 500},
                "thresholds": {"holdout_psr_min": 0.95, "paper_psr_min": 0.80},
                "family_calibrations": {
                    "16": {
                        "live_calibrated": True,
                        "null_false_acceptance_rate": 0.04,
                        "target_live_detection_rate": 0.84,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return shiller, gold, data.parent, prior, calibration


def test_fx_probe_writes_656_trial_no_order_evidence(tmp_path: Path) -> None:
    shiller, gold, data, prior, calibration = _write_inputs(tmp_path)
    output, summary = tmp_path / "factory.json", tmp_path / "LAST_RUN.md"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/fx_carry_factory_probe.py",
            "--shiller-file",
            str(shiller),
            "--gold-file",
            str(gold),
            "--macro-data-dir",
            str(data),
            "--prior-factory-json",
            str(prior),
            "--calibration-json",
            str(calibration),
            "--code-commit",
            "abc123",
            "--timestamp-utc",
            "2026-08-24T00:00:00Z",
            "--json-out",
            str(output),
            "--summary-out",
            str(summary),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 16
    assert payload["prior_trial_count"] == 640
    assert payload["global_audit_trial_count"] == 656
    assert payload["multiplicity_trial_count"] == 16
    assert payload["decision"]["selected_deploy_config"] is None
    assert "독립 외환 금리차 전략 공장" in summary.read_text(encoding="utf-8")
