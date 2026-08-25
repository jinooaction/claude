from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path


def _months(count: int = 240) -> list[tuple[int, int]]:
    year, month = 2006, 8
    output = []
    for _ in range(count):
        output.append((year, month))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return output


def _blackrock(path: Path) -> None:
    dates = [int(f"{year:04d}{month:02d}28") for year, month in _months()]
    fund = [str(10_000 * 1.001**index) for index in range(240)]
    benchmark = [str(10_000 * 1.0015**index) for index in range(240)]
    payload = {
        "productId": 239757,
        "pageScopeData": {"ticker": "GSG", "portfolioId": "239757"},
        "componentsByNameMap": {
            "performance": {
                "containersByNameMap": {
                    "chart": {
                        "dataPointsByNameMap": {
                            "performanceData": {"asOfDate": dates, "value": fund},
                            "benchmarkData": {"asOfDate": dates, "value": benchmark},
                        }
                    }
                }
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _world_bank(path: Path) -> None:
    labels = ["Updated on August 04, 2026"] + [
        f"{year:04d}M{month:02d}" for year, month in _months()
    ]
    shared = "".join(f"<si><t>{label}</t></si>" for label in labels)
    rows = ['<row r="1"><c r="A1" t="s"><v>0</v></c></row>']
    for index in range(240):
        row = index + 10
        rows.append(
            f'<row r="{row}"><c r="A{row}" t="s"><v>{index + 1}</v></c>'
            f'<c r="B{row}"><v>{100 * 1.0012**index}</v></c></row>'
        )
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{namespace}">{shared}</sst>')
        archive.writestr(
            "xl/worksheets/sheet3.xml",
            f'<worksheet xmlns="{namespace}"><sheetData>{"".join(rows)}</sheetData></worksheet>',
        )
    path.write_bytes(buffer.getvalue())


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    blackrock = tmp_path / "blackrock.json"
    world_bank = tmp_path / "world-bank.xlsx"
    _blackrock(blackrock)
    _world_bank(world_bank)

    shiller = tmp_path / "shiller.csv"
    gold = tmp_path / "gold.csv"
    shiller_lines = ["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate"]
    gold_lines = ["Date,Price"]
    for index, (year, month) in enumerate(_months()):
        shiller_lines.append(
            f"{year:04d}-{month:02d}-01,{100 * 1.006**index},2,5,100,{3 + index % 12 / 10}"
        )
        gold_lines.append(f"{year:04d}-{month:02d},{400 * 1.004**index}")
    shiller.write_text("\n".join(shiller_lines) + "\n", encoding="utf-8")
    gold.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")

    macro = tmp_path / "public-data" / "fred"
    macro.mkdir(parents=True)
    rate_lines = ["observation_date,DGS3MO", "2006-07-31,2.0"]
    for index, (year, month) in enumerate(_months()):
        rate_lines.append(f"{year:04d}-{month:02d}-20,{2 + index % 12 / 20}")
    rate_lines.append("2026-08-20,3.0")
    (macro / "DGS3MO.csv").write_text("\n".join(rate_lines) + "\n", encoding="utf-8")

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
                    for index in range(656)
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
    return blackrock, world_bank, shiller, gold, macro.parent, prior, calibration


def test_probe_writes_672_trial_no_order_evidence(tmp_path: Path) -> None:
    blackrock, world_bank, shiller, gold, macro, prior, calibration = _inputs(tmp_path)
    output, summary = tmp_path / "factory.json", tmp_path / "LAST_RUN.md"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/commodity_term_structure_factory_probe.py",
            "--blackrock-file",
            str(blackrock),
            "--world-bank-file",
            str(world_bank),
            "--shiller-file",
            str(shiller),
            "--gold-file",
            str(gold),
            "--macro-data-dir",
            str(macro),
            "--prior-factory-json",
            str(prior),
            "--calibration-json",
            str(calibration),
            "--code-commit",
            "abc123",
            "--timestamp-utc",
            "2026-08-25T00:00:00Z",
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
    assert payload["global_audit_trial_count"] == 672
    assert payload["multiplicity_trial_count"] == 16
    assert payload["decision"]["selected_deploy_config"] is None
    assert "독립 원자재 기간구조 전략 공장" in summary.read_text(encoding="utf-8")


def test_workflow_runs_commodity_after_fx_and_publishes_separate_evidence() -> None:
    workflow = Path(".github/workflows/autonomous-strategy-factory.yml").read_text()
    assert "scripts/commodity_term_structure_factory_probe.py" in workflow
    assert "--prior-factory-json /tmp/fx_carry_factory.json" in workflow
    assert 'global_audit_trial_count' in workflow and '= "672"' in workflow
    assert "commodity_term_structure_factory.json" in workflow
    assert "data_fingerprint: $root.supply_demand_data_fingerprint" in workflow
    preserved_sidecar = (
        'cp /tmp/commodity_term_structure_factory.json '
        '"${tmpdir}/commodity_term_structure_factory.json"'
    )
    assert preserved_sidecar in workflow
