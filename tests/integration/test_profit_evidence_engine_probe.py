"""스펙 138 - 수익 증거 probe와 workflow 계약 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scripts" / "profit_evidence_engine_probe.py"
WORKFLOW = ROOT / ".github" / "workflows" / "profit-evidence-engine.yml"

_spec = importlib.util.spec_from_file_location("profit_evidence_engine_probe", PROBE)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)


def _public_csvs(tmp_path: Path) -> tuple[Path, Path]:
    shiller = tmp_path / "shiller.csv"
    gold = tmp_path / "gold.csv"
    shiller_lines = ["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate"]
    gold_lines = ["Date,Price"]
    equity = gold_price = 100.0
    year, month = 1971, 1
    for index in range(660):
        equity *= 1.009 if index % 2 == 0 else 0.997
        gold_price *= 1.006 if index % 3 else 0.998
        shiller_lines.append(
            f"{year:04d}-{month:02d}-01,{equity:.8f},2,5,100,4"
        )
        gold_lines.append(f"{year:04d}-{month:02d},{gold_price:.8f}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    shiller.write_text("\n".join(shiller_lines) + "\n", encoding="utf-8")
    gold.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")
    return shiller, gold


def test_probe_writes_machine_readable_no_live_report(tmp_path: Path, capsys) -> None:
    shiller, gold = _public_csvs(tmp_path)
    leaderboard = tmp_path / "leaderboard.json"
    leaderboard.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "key": "globalfixed",
                        "n_obs": 41,
                        "psr_vs_benchmark": "0.827270",
                        "verdict": "NO_EDGE",
                        "beats_benchmark_calmar": True,
                        "significance_method": "paired_active_return_psr_v1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    json_out = tmp_path / "profit_evidence.json"
    summary_out = tmp_path / "LAST_RUN.md"

    assert (
        _probe.main(
            [
                "--shiller-file",
                str(shiller),
                "--gold-file",
                str(gold),
                "--leaderboard",
                str(leaderboard),
                "--json-out",
                str(json_out),
                "--summary-out",
                str(summary_out),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["trial_count"] == 12
    assert payload["split"]["overlap_months"] == 0
    assert len(payload["safety_invariants"]) >= 8
    assert payload["deployment_match"]["candidate_id"] == (
        "globalfixed-ensemble-3-6-9-12"
    )
    assert isinstance(payload["deployment_match"]["historical_passed"], bool)
    assert "실주문" in summary_out.read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["schema_version"] == "1.1"


def test_workflow_is_read_only_and_publishes_profit_evidence_sidecar() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text and "workflow_dispatch:" in text
    assert "profit_evidence_engine_probe.py" in text
    assert "automation/profit-evidence-engine-last-run" in text
    assert "| timestamp_utc | $(date -u +%Y-%m-%dT%H:%M:%SZ) |" in text
    assert "rebalance-paper-forward-last-run:leaderboard.json" in text
    assert "--mode live" not in text
    assert "--confirm-live" not in text
    assert "rebalance-once" not in text
    assert "KIS_" not in text
    assert "VULTR_" not in text
