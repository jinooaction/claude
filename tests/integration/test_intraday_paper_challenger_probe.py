from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, timedelta
from pathlib import Path

import exchange_calendars as xcals

ROOT = Path(__file__).parents[2]
PREREGISTRATION = (
    ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
)
SYMBOLS = ("SPY", "QQQ", "IWM", "TLT", "GLD")


def _dataset(root: Path) -> Path:
    calendar = xcals.get_calendar("XNYS")
    files: dict[str, object] = {}
    for symbol_index, symbol in enumerate(SYMBOLS):
        path = root / f"{symbol}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp_utc", "symbol", "open", "high", "low", "close", "volume"])
            rows = 0
            for session_index, label in enumerate(("2024-01-02", "2024-01-03")):
                cursor = calendar.session_open(label).to_pydatetime()
                close = calendar.session_close(label).to_pydatetime()
                bar_index = 0
                while cursor < close:
                    price = 100 + symbol_index * 5 + session_index + bar_index * 0.02
                    writer.writerow(
                        [
                            cursor.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            symbol,
                            price,
                            price + 0.05,
                            price - 0.03,
                            price + 0.02,
                            1_000_000,
                        ]
                    )
                    cursor += timedelta(minutes=5)
                    bar_index += 1
                    rows += 1
        files[symbol] = {
            "path": path.name,
            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": rows,
        }
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "dataset_id": "integration-short-synthetic-v1",
                "provider": "pytest",
                "retrieved_at_utc": "2026-01-01T00:00:00Z",
                "adjustment_policy": "split-adjusted fixture",
                "base_timeframe_minutes": 5,
                "synthetic": True,
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_probe_is_deterministic_and_independent_gate_accepts_insufficient_evidence(
    tmp_path: Path,
) -> None:
    manifest = _dataset(tmp_path)
    result = tmp_path / "result.json"
    ledger = tmp_path / "ledger.jsonl"
    summary = tmp_path / "summary.md"
    command = [
        sys.executable,
        str(ROOT / "scripts/intraday_paper_challenger_probe.py"),
        "--bars-dir",
        str(tmp_path),
        "--manifest",
        str(manifest),
        "--preregistration",
        str(PREREGISTRATION),
        "--code-commit",
        "integration-test",
        "--timestamp-utc",
        "2026-09-02T00:00:00Z",
        "--json-out",
        str(result),
        "--ledger-out",
        str(ledger),
        "--summary-out",
        str(summary),
    ]

    first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    first_result = result.read_bytes()
    first_ledger = ledger.read_bytes()
    payload = json.loads(first_result)
    assert payload["decision"]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert payload["safety"]["orders_submitted"] == 0

    second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert second.returncode == 0, second.stderr
    assert result.read_bytes() == first_result
    assert ledger.read_bytes() == first_ledger

    gate = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/intraday_paper_evidence_gate.py"),
            "--evidence",
            str(result),
            "--ledger",
            str(ledger),
            "--preregistration",
            str(PREREGISTRATION),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert gate.returncode == 0, gate.stderr
    assert json.loads(gate.stdout)["valid"] is True
