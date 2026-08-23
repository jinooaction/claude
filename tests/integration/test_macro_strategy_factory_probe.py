from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path


def _write_market_inputs(tmp_path: Path) -> tuple[Path, Path, list[str]]:
    shiller = tmp_path / "shiller.csv"
    gold = tmp_path / "gold.csv"
    shiller_lines = ["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate"]
    gold_lines = ["Date,Price"]
    dates: list[str] = []
    year, month = 1990, 1
    price, gold_price = 100.0, 400.0
    for index in range(37 * 12):
        price *= 1.006 if index % 48 < 36 else 0.985
        gold_price *= 1.004 if index % 60 < 30 else 0.998
        current = f"{year:04d}-{month:02d}-01"
        dates.append(current)
        shiller_lines.append(f"{current},{price},2,5,100,4")
        gold_lines.append(f"{year:04d}-{month:02d},{gold_price}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    shiller.write_text("\n".join(shiller_lines) + "\n", encoding="utf-8")
    gold.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")
    return shiller, gold, dates


def _write_series(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("date,value\n" + "\n".join(f"{day},{value}" for day, value in rows) + "\n")


def _write_macro_inputs(tmp_path: Path) -> Path:
    root = tmp_path / "public-data"
    start = date(1989, 1, 1)
    end = date(2026, 8, 23)
    days = (end - start).days + 1
    daily_dates = [(start + timedelta(days=index)).isoformat() for index in range(days)]
    _write_series(root / "fred" / "DGS2.csv", [(day, "2.0") for day in daily_dates])
    _write_series(root / "fred" / "DGS10.csv", [(day, "2.5") for day in daily_dates])
    _write_series(root / "cboe" / "VIX.csv", [(day, "20") for day in daily_dates])

    monthly: list[tuple[str, str]] = []
    sahm: list[tuple[str, str]] = []
    year, month, index = 1988, 1, 0
    while date(year, month, 1) <= end:
        monthly.append((f"{year:04d}-{month:02d}-01", str(100 + index / 10)))
        sahm.append((f"{year:04d}-{month:02d}-01", str((index % 12) / 20)))
        index += 1
        month += 1
        if month == 13:
            year, month = year + 1, 1
    _write_series(root / "fred" / "CPIAUCNS.csv", monthly)
    _write_series(root / "fred" / "SAHMREALTIME.csv", sahm)
    (root / "summary.json").write_text(
        json.dumps(
            {
                "source_commit": "abc123",
                "generated_at_utc": "2026-08-23T00:00:00Z",
                "cross_checks": [{"status": "PASS"}],
                "items": [
                    {
                        "kind": "cboe",
                        "id": "VIX",
                        "close_sanity": {"status": "PASS"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


def _write_prior_ledger(path: Path) -> None:
    rows = [
        {
            "candidate_id": f"factory-prior-{index:03d}",
            "status": "complete",
            "sharpe_25bps": 0.1,
            "segment_sharpes": [0.1] * 10,
        }
        for index in range(256)
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_probe_writes_512_trial_evidence_within_upper_bound(tmp_path: Path) -> None:
    shiller, gold, _ = _write_market_inputs(tmp_path)
    macro = _write_macro_inputs(tmp_path)
    ledger = tmp_path / "prior.jsonl"
    _write_prior_ledger(ledger)
    json_out = tmp_path / "factory.json"
    summary_out = tmp_path / "LAST_RUN.md"
    started = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            "scripts/macro_strategy_factory_probe.py",
            "--shiller-file",
            str(shiller),
            "--gold-file",
            str(gold),
            "--macro-data-dir",
            str(macro),
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
    assert payload["exploratory_trial_count"] == 192
    assert payload["multiplicity_trial_count"] == 512
    assert payload["decision"]["selected_candidate_id"] is None
    assert elapsed < 900
    assert "독립 거시 전략 공장" in summary_out.read_text(encoding="utf-8")
