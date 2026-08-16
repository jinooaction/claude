"""Spec 146 probe, workflow, gateway, and autonomous-loop boundaries."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from auto_invest.analytics.autonomous_work_execution import build_autonomous_work_execution
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db

ROOT = Path(__file__).resolve().parents[2]


def _candidate_report(*, eligible: bool) -> str:
    return json.dumps(
        {
            "verdict": "DAILY_ML_EDGE_CANDIDATE_READY" if eligible else "NO_EDGE",
            "candidate_package": {
                "eligible": eligible,
                "candidate_id": "candidate-daily-cross-asset-ml-v1",
                "title_ko": "일봉 교차자산 AI 상대수익 후보 재현 검증",
                "domain_key": "investment_edge",
                "status": "new" if eligible else "rejected",
                "risk_grade": 2,
                "priority_score": 760,
            },
        }
    )


def test_probe_emits_blocked_json_instead_of_reusing_stale_success(tmp_path: Path):
    path = tmp_path / "bars.db"
    conn = db.get_connection(path)
    db.migrate(conn)
    insert_bar(
        conn,
        PriceBar(
            "SPY",
            "1d",
            "2026-08-14T00:00:00.000Z",
            Decimal("100"),
            Decimal("101"),
            Decimal("99"),
            Decimal("100"),
            1_000_000,
        ),
    )
    conn.close()

    completed = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/daily_cross_asset_ml_probe.py",
            "--db",
            str(path),
            "--json",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["verdict"] == "BLOCKED"
    assert payload["candidate_package"]["eligible"] is False
    assert payload["safety"]["orders_submitted"] == 0


def test_only_eligible_daily_ml_report_becomes_autonomous_work():
    now = datetime(2026, 8, 16, tzinfo=UTC)
    rejected = build_autonomous_work_execution(
        {"daily-cross-asset-ml": _candidate_report(eligible=False)}, now=now
    )
    ready = build_autonomous_work_execution(
        {"daily-cross-asset-ml": _candidate_report(eligible=True)}, now=now
    )
    assert all(
        row.candidate_id != "candidate-daily-cross-asset-ml-v1"
        for row in rejected.ranked_work
    )
    assert any(
        row.candidate_id == "candidate-daily-cross-asset-ml-v1"
        for row in ready.ranked_work
    )


def test_workflow_and_forced_command_are_read_only_and_exact():
    workflow = (ROOT / ".github/workflows/daily-cross-asset-ml.yml").read_text()
    helper = (ROOT / "deploy/observe-on-instance.sh").read_text()
    gateway = (ROOT / "deploy/repair-ssh-boundary.sh").read_text()
    module = (ROOT / "src/auto_invest/analytics/daily_cross_asset_ml.py").read_text()
    probe = (ROOT / "scripts/daily_cross_asset_ml_probe.py").read_text()

    assert '"observe daily-ml-edge"' in workflow
    assert "DAILY_ML_EDGE_JSON_BEGIN" in helper
    assert "--min-bars 1250" in helper
    assert "observe\\ daily-ml-edge)" in gateway
    assert "observe\\ daily-ml-edge\\ *)" not in gateway
    assert "automation/daily-cross-asset-ml-last-run" in workflow
    combined = (workflow + module + probe).lower()
    for forbidden in ("submit_order", "cancel_order", "rebalance-once", "--mode live"):
        assert forbidden not in combined


def test_autonomous_manifest_fetches_daily_ml_sidecar():
    probe = (ROOT / "scripts/autonomous_work_execution_probe.py").read_text()
    core = (ROOT / "src/auto_invest/analytics/autonomous_work_execution.py").read_text()
    assert "automation/daily-cross-asset-ml-last-run" in probe
    assert '"daily-cross-asset-ml"' in core
