"""Spec 143 live-profit probe file integration."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_PROBE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "live_profit_evidence_probe.py"
)
_spec = importlib.util.spec_from_file_location("live_profit_evidence_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_writes_sticky_json_and_markdown(tmp_path: Path) -> None:
    performance = tmp_path / "performance.json"
    prior = tmp_path / "prior.json"
    output = tmp_path / "profit_evidence.json"
    summary = tmp_path / "LAST_RUN.md"
    performance.write_text(
        json.dumps(
            {
                "mode": "live",
                "fills_count": 2,
                "gross_invested_usd": "178.32",
                "realized_pnl_usd": "0",
                "unrealized_pnl_usd": "0.42",
                "total_pnl_usd": "0.42",
                "return_pct": "0.2355",
                "unmarked_symbols": [],
                "data_quality_warnings": [],
            }
        ),
        encoding="utf-8",
    )
    prior.write_text("{}", encoding="utf-8")

    rc = probe_main(
        [
            "--performance-json",
            str(performance),
            "--prior-json",
            str(prior),
            "--json-out",
            str(output),
            "--summary-out",
            str(summary),
            "--now",
            "2026-08-18T00:05:00Z",
            "--run-id",
            "31900000002",
        ]
    )

    assert rc == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["status"] == "FIRST_PROFIT_OBSERVED"
    assert data["first_profit_total_pnl_usd"] == "0.42"
    assert "최초 양의 손익" in summary.read_text(encoding="utf-8")
