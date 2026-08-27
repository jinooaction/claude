"""End-to-end no-order probe contract for spec 171."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scripts" / "regime_adaptive_challenger_probe.py"
CONTRACT = (
    ROOT
    / "specs"
    / "171-parallel-regime-edge-challenger"
    / "contracts"
    / "preregistered-challenger.json"
)


def _load_probe():
    spec = importlib.util.spec_from_file_location("regime_adaptive_challenger_probe", PROBE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public_csvs(tmp_path: Path) -> tuple[Path, Path]:
    shiller = tmp_path / "shiller.csv"
    gold = tmp_path / "gold.csv"
    shiller_lines = ["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate"]
    gold_lines = ["Date,Price"]
    equity = gold_price = 100.0
    year, month = 1971, 1
    for index in range(624):
        crisis = index % 84 in range(55, 62)
        equity *= 0.965 if crisis else 1.008
        gold_price *= 1.02 if crisis else 1.002
        rate = 4.0 + (index % 24) * 0.1 if crisis else 5.0 - (index % 24) * 0.05
        shiller_lines.append(f"{year:04d}-{month:02d}-01,{equity:.8f},2,5,100,{max(rate, 0.5):.4f}")
        gold_lines.append(f"{year:04d}-{month:02d},{gold_price:.8f}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    shiller.write_text("\n".join(shiller_lines) + "\n", encoding="utf-8")
    gold.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")
    return shiller, gold


def test_probe_writes_valid_no_order_json_and_markdown(tmp_path: Path, capsys) -> None:
    probe = _load_probe()
    shiller, gold = _public_csvs(tmp_path)
    output = tmp_path / "result.json"
    markdown = tmp_path / "result.md"

    assert (
        probe.main(
            [
                "--contract",
                str(CONTRACT),
                "--shiller-file",
                str(shiller),
                "--gold-file",
                str(gold),
                "--output",
                str(output),
                "--markdown-output",
                str(markdown),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 16
    assert payload["verdict"] in {"RESEARCH_EDGE", "NO_RESEARCH_EDGE"}
    assert payload["safety"]["promotion_allowed"] is False
    assert payload["safety"]["orders_submitted"] == 0
    assert "실제 주문: 0건" in markdown.read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["schema_version"] == "regime-edge-result-v1"
