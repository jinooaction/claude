from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


def _record(prefix: str, index: int) -> dict:
    return {
        "candidate_id": f"{prefix}{index:03d}",
        "strategy_fingerprint": f"sha256:{prefix}{index:03d}",
        "status": "complete",
        "segment_sharpes": [0.1] * 10,
    }


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    shiller, gold = tmp_path / "shiller.csv", tmp_path / "gold.csv"
    shiller_lines = ["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate"]
    gold_lines = ["Date,Price"]
    year, month = 1990, 1
    for index in range(37 * 12):
        current = f"{year:04d}-{month:02d}-01"
        shiller_lines.append(f"{current},{100 * 1.006**index},2,5,100,{3 + index % 24 / 20}")
        gold_lines.append(f"{year:04d}-{month:02d},{400 * 1.004**index}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    shiller.write_text("\n".join(shiller_lines) + "\n", encoding="utf-8")
    gold.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")

    data = tmp_path / "public-data" / "fred"
    data.mkdir(parents=True)
    for offset, series_id in enumerate(("HQMCB10YR", "HQMCB20YR")):
        lines = [f"observation_date,{series_id}"]
        year, month = 1984, 1
        for index in range(43 * 12):
            lines.append(f"{year:04d}-{month:02d}-01,{5 + offset + index % 24 / 20}")
            month += 1
            if month == 13:
                year, month = year + 1, 1
        (data / f"{series_id}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for offset, series_id in enumerate(("DGS10", "DGS30")):
        lines = [f"observation_date,{series_id}"]
        current, index = date(1984, 1, 1), 0
        while current <= date(2026, 8, 23):
            lines.append(f"{current.isoformat()},{3 + offset * 0.5 + index % 30 / 100}")
            current, index = current + timedelta(days=5), index + 1
        (data / f"{series_id}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    ledger = tmp_path / "prior.jsonl"
    ledger.write_text(
        "".join(json.dumps(_record("factory-", index)) + "\n" for index in range(256)),
        encoding="utf-8",
    )
    prior = tmp_path / "treasury.json"
    prior.write_text(
        json.dumps({"trial_records": [_record("treasury-", index) for index in range(64)]}),
        encoding="utf-8",
    )
    macro = tmp_path / "macro.json"
    exploratory = [_record("exploratory-", index) for index in range(192)]
    for record in exploratory:
        record["status"] = "EXPLORATORY_REJECTED"
    macro.write_text(
        json.dumps(
            {
                "exploratory_replay": exploratory,
                "trial_records": [_record("macro-", index) for index in range(64)],
            }
        ),
        encoding="utf-8",
    )
    return shiller, gold, data.parent, ledger, prior, macro


def test_credit_probe_writes_640_trial_no_order_evidence(tmp_path: Path) -> None:
    shiller, gold, data, ledger, prior, macro = _inputs(tmp_path)
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "gate_version": "2.0",
                "verdict": "CALIBRATED",
                "code_commit": "abc123",
                "scenario": {"repetitions": 500},
                "revised": {"false_acceptance_rate": 0.036, "detection_rate": 0.834},
                "thresholds": {
                    "development_dsr_diagnostic_min": 0.95,
                    "development_pbo_diagnostic_max": 0.10,
                    "holdout_psr_min": 0.95,
                },
            }
        ),
        encoding="utf-8",
    )
    result_json, summary = tmp_path / "factory.json", tmp_path / "LAST_RUN.md"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/credit_spread_factory_probe.py",
            "--shiller-file",
            str(shiller),
            "--gold-file",
            str(gold),
            "--macro-data-dir",
            str(data),
            "--prior-factory-json",
            str(prior),
            "--macro-factory-json",
            str(macro),
            "--prior-ledger",
            str(ledger),
            "--calibration-json",
            str(calibration),
            "--code-commit",
            "abc123",
            "--timestamp-utc",
            "2026-08-23T00:00:00Z",
            "--json-out",
            str(result_json),
            "--summary-out",
            str(summary),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result_json.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 64
    assert payload["prior_trial_count"] == 576
    assert payload["global_audit_trial_count"] == 640
    assert payload["multiplicity_trial_count"] == 64
    assert payload["decision"]["live_canary_eligible"] is False
    assert payload["decision"]["selected_deploy_config"] is None
    assert "독립 회사채 스프레드 전략 공장" in summary.read_text(encoding="utf-8")
