from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from datetime import date


def _write_data(path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["signalname", "port", "date", "ret", "signallag", "Nlong", "Nshort"])
        year, month = 1971, 9
        index = 0
        while (year, month) <= (2024, 12):
            observed = date(year, month, 28).isoformat()
            cycle = math.sin(index / 7) * 0.3
            writer.writerow(["AnnouncementReturn", "LS", observed, 1.2 + cycle, "NA", 300, 299])
            writer.writerow(["EarningsSurprise", "LS", observed, 0.9 - cycle / 2, "NA", 280, 279])
            index += 1
            month += 1
            if month == 13:
                year += 1
                month = 1


def _prior() -> dict[str, object]:
    rows = []
    for family in range(20):
        count = 16 if family < 10 else 64
        for index in range(count):
            rows.append(
                {
                    "candidate_id": f"prior-{family:02d}-{index:03d}",
                    "strategy_fingerprint": f"sha256:prior-{family:02d}-{index:03d}",
                    "status": "complete",
                    "batch_id": f"prior-family-{family:02d}",
                }
            )
    return {"audit_records": rows}


def _calibration() -> dict[str, object]:
    return {
        "code_commit": "abc123",
        "scenario": {"seed": 60000, "repetitions": 500},
        "family_calibrations": {
            "16": {
                "null_research_entry_acceptance_rate": 0.01,
                "target_research_entry_detection_rate": 0.84,
            },
            "64": {
                "null_research_entry_acceptance_rate": 0.004,
                "target_research_entry_detection_rate": 0.804,
            },
        },
        "program_extension": {
            "gate_version": "3.2",
            "method": "family-size-bonferroni-v2",
            "family_caps": {"16": 0.01, "64": 0.009},
            "family_mix": {"16": 11, "64": 10},
            "conservative_upper_bound": 0.2,
            "false_acceptance_budget": 0.2,
            "planted_sharpe_annual": 0.6,
            "detection_min": 0.8,
            "minimum_repetitions": 500,
            "calibrated": True,
            "capital_entry_eligible": False,
        },
    }


def test_probe_writes_schema_valid_research_only_evidence(tmp_path) -> None:
    data = tmp_path / "op.csv"
    prior = tmp_path / "prior.json"
    calibration = tmp_path / "calibration.json"
    output = tmp_path / "pead.json"
    summary = tmp_path / "PEAD_LAST_RUN.md"
    _write_data(data)
    prior.write_text(json.dumps(_prior()), encoding="utf-8")
    calibration.write_text(json.dumps(_calibration()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/pead_factory_probe.py",
            "--data-file",
            str(data),
            "--prior-factory-json",
            str(prior),
            "--calibration-json",
            str(calibration),
            "--preregistration",
            "specs/175-pead-program-gate/contracts/pead-preregistration.json",
            "--result-schema",
            "specs/175-pead-program-gate/contracts/pead-result.schema.json",
            "--code-commit",
            "abc123",
            "--timestamp-utc",
            "2026-08-31T00:00:00Z",
            "--json-out",
            str(output),
            "--summary-out",
            str(summary),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["verdict"] == "PUBLISHED_EDGE"
    assert payload["global_audit"]["trial_count"] == 816
    assert payload["safety"]["orders_submitted"] == 0
    assert "현재 계좌 실행 적격이 아닙니다" in summary.read_text(encoding="utf-8")


def test_probe_rejects_bad_program_calibration(tmp_path) -> None:
    data = tmp_path / "op.csv"
    prior = tmp_path / "prior.json"
    calibration = tmp_path / "calibration.json"
    _write_data(data)
    prior.write_text(json.dumps(_prior()), encoding="utf-8")
    bad = _calibration()
    bad["program_extension"]["conservative_upper_bound"] = 0.21
    calibration.write_text(json.dumps(bad), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/pead_factory_probe.py",
            "--data-file",
            str(data),
            "--prior-factory-json",
            str(prior),
            "--calibration-json",
            str(calibration),
            "--preregistration",
            "specs/175-pead-program-gate/contracts/pead-preregistration.json",
            "--code-commit",
            "abc123",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "program calibration" in result.stderr

