from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.analytics.opportunity_monitor import append_opportunity_record
from auto_invest.cli import app

runner = CliRunner()


def _report(total: str) -> dict:
    return {
        "schema_version": 1,
        "as_of_utc": "2026-06-26T00:00:00Z",
        "rejected_count": 1,
        "valued_count": 1,
        "total_opportunity_pnl_usd": total,
        "buy_opportunity_pnl_usd": total,
        "sell_opportunity_pnl_usd": "+0.00",
        "rows": [],
    }


def test_opportunity_monitor_cli_updates_history_and_summary(tmp_path: Path) -> None:
    prior = append_opportunity_record(
        {},
        _report("-3.00"),
        run_id="100",
        timestamp_utc="2026-06-26T00:00:00Z",
    )
    history_json = tmp_path / "history.json"
    opportunity_json = tmp_path / "opportunity.json"
    history_out = tmp_path / "opportunity_history.json"
    monitor_out = tmp_path / "opportunity_monitor.json"
    history_json.write_text(json.dumps(prior), encoding="utf-8")
    opportunity_json.write_text(json.dumps(_report("-2.50")), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "opportunity-monitor",
            "--history-json",
            str(history_json),
            "--opportunity-json",
            str(opportunity_json),
            "--history-out",
            str(history_out),
            "--monitor-out",
            str(monitor_out),
            "--run-id",
            "101",
            "--run-url",
            "https://example.test/run/101",
            "--event",
            "schedule",
            "--live-outcome",
            "success",
            "--armed",
            "true",
            "--capital-usd",
            "1000",
            "--timestamp-utc",
            "2026-06-26T00:01:00Z",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["verdict"] == "STRATEGY_REVIEW"
    assert summary["latest"]["run_id"] == "101"
    assert json.loads(monitor_out.read_text(encoding="utf-8")) == summary
    history = json.loads(history_out.read_text(encoding="utf-8"))
    assert [record["run_id"] for record in history["records"]] == ["100", "101"]


def test_opportunity_monitor_cli_text_mode_without_history() -> None:
    result = runner.invoke(app, ["opportunity-monitor", "--format", "text"])

    assert result.exit_code == 0, result.output
    assert "거부 주문 누적 평가" in result.stdout
    assert "NO_VALUED_REJECTIONS" in result.stdout


def test_opportunity_monitor_cli_without_opportunity_json_preserves_history(
    tmp_path: Path,
) -> None:
    prior = append_opportunity_record(
        {},
        _report("-1.14"),
        run_id="28253047287",
        timestamp_utc="2026-06-26T17:03:12Z",
    )
    history_json = tmp_path / "history.json"
    history_out = tmp_path / "opportunity_history.json"
    monitor_out = tmp_path / "opportunity_monitor.json"
    history_json.write_text(json.dumps(prior), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "opportunity-monitor",
            "--history-json",
            str(history_json),
            "--history-out",
            str(history_out),
            "--monitor-out",
            str(monitor_out),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    history = json.loads(history_out.read_text(encoding="utf-8"))
    summary = json.loads(monitor_out.read_text(encoding="utf-8"))
    assert [record["run_id"] for record in history["records"]] == ["28253047287"]
    assert summary["latest_signal"] == "INTENT_LOSS"
    assert summary["latest"]["run_id"] == "28253047287"
