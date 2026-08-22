import json
import subprocess
import sys
from pathlib import Path


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    shiller = tmp_path / "shiller.csv"
    gold = tmp_path / "gold.csv"
    shiller_lines = ["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate"]
    gold_lines = ["Date,Price"]
    year, month = 1971, 1
    price = 100.0
    gold_price = 35.0
    for index in range(56 * 12):
        price *= 1.005 if index % 36 < 28 else 0.99
        gold_price *= 1.003 if index % 48 < 20 else 0.999
        ym = f"{year:04d}-{month:02d}"
        shiller_lines.append(f"{ym}-01,{price},2,5,100,4")
        gold_lines.append(f"{ym},{gold_price}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    shiller.write_text("\n".join(shiller_lines) + "\n", encoding="utf-8")
    gold.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")
    return shiller, gold


def test_probe_writes_complete_json_and_summary(tmp_path: Path) -> None:
    shiller, gold = _write_inputs(tmp_path)
    json_out = tmp_path / "factory.json"
    summary_out = tmp_path / "LAST_RUN.md"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/strategy_factory_probe.py",
            "--shiller-file",
            str(shiller),
            "--gold-file",
            str(gold),
            "--code-commit",
            "abc123",
            "--timestamp-utc",
            "2026-08-23T00:00:00Z",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 64
    assert payload["complete_trial_count"] == 64
    assert "자동 전략 공장" in summary_out.read_text(encoding="utf-8")
