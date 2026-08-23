from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path


def _write_market_inputs(tmp_path: Path) -> tuple[Path, Path]:
    shiller = tmp_path / "shiller.csv"
    gold = tmp_path / "gold.csv"
    shiller_lines = ["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate"]
    gold_lines = ["Date,Price"]
    year, month = 1990, 1
    price, gold_price = 100.0, 400.0
    for index in range(37 * 12):
        price *= 1.006 if index % 48 < 36 else 0.985
        gold_price *= 1.004 if index % 60 < 30 else 0.998
        current = f"{year:04d}-{month:02d}-01"
        shiller_lines.append(f"{current},{price},2,5,100,{3.0 + (index % 24) / 20}")
        gold_lines.append(f"{year:04d}-{month:02d},{gold_price}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    shiller.write_text("\n".join(shiller_lines) + "\n", encoding="utf-8")
    gold.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")
    return shiller, gold


def _write_treasury_inputs(tmp_path: Path) -> Path:
    root = tmp_path / "public-data"
    fred = root / "fred"
    fred.mkdir(parents=True)
    start = date(1989, 1, 1)
    end = date(2026, 8, 23)
    points: list[date] = []
    current = start
    while current <= end:
        points.append(current)
        current += timedelta(days=5)
    for offset, series_id in enumerate(("DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30")):
        lines = ["observation_date,value"]
        lines.extend(
            f"{day.isoformat()},{2.0 + offset * 0.3 + (index % 30) / 100}"
            for index, day in enumerate(points)
        )
        (fred / f"{series_id}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _write_prior_inputs(tmp_path: Path) -> tuple[Path, Path]:
    ledger = tmp_path / "prior.jsonl"
    ledger_rows = [
        {
            "candidate_id": f"factory-prior-{index:03d}",
            "strategy_fingerprint": f"sha256:price-{index:03d}",
            "status": "complete",
            "sharpe_25bps": 0.1,
            "segment_sharpes": [0.1] * 10,
        }
        for index in range(256)
    ]
    ledger.write_text("".join(json.dumps(row) + "\n" for row in ledger_rows), encoding="utf-8")
    prior = tmp_path / "macro.json"
    prior.write_text(
        json.dumps(
            {
                "exploratory_replay": [
                    {
                        "candidate_id": f"explore-{index:03d}",
                        "strategy_fingerprint": f"sha256:explore-{index:03d}",
                        "status": "EXPLORATORY_REJECTED",
                        "sharpe_25bps": 0.2,
                        "segment_sharpes": [0.2] * 10,
                    }
                    for index in range(192)
                ],
                "trial_records": [
                    {
                        "candidate_id": f"macro-{index:03d}",
                        "strategy_fingerprint": f"sha256:macro-{index:03d}",
                        "status": "complete",
                        "sharpe_25bps": 0.3,
                        "segment_sharpes": [0.3] * 10,
                    }
                    for index in range(64)
                ],
            }
        ),
        encoding="utf-8",
    )
    return ledger, prior


def test_probe_writes_576_trial_no_order_evidence_within_upper_bound(tmp_path: Path) -> None:
    shiller, gold = _write_market_inputs(tmp_path)
    treasury = _write_treasury_inputs(tmp_path)
    ledger, prior = _write_prior_inputs(tmp_path)
    json_out = tmp_path / "factory.json"
    summary_out = tmp_path / "LAST_RUN.md"
    started = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            "scripts/treasury_carry_factory_probe.py",
            "--shiller-file",
            str(shiller),
            "--gold-file",
            str(gold),
            "--macro-data-dir",
            str(treasury),
            "--prior-factory-json",
            str(prior),
            "--prior-ledger",
            str(ledger),
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
        timeout=900,
    )
    elapsed = time.monotonic() - started
    assert result.returncode == 0, result.stderr
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 64
    assert payload["prior_trial_count"] == 512
    assert payload["multiplicity_trial_count"] == 576
    assert payload["decision"]["selected_candidate_id"] is None
    assert elapsed < 900
    assert "독립 국채 캐리 전략 공장" in summary_out.read_text(encoding="utf-8")
