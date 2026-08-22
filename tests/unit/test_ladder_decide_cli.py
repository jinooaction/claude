"""스펙 140 - 탐색 캐너리 입력을 자본 사다리에 잇는 CLI 회귀 테스트."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app

ROOT = Path(__file__).resolve().parents[2]
RUNNER = CliRunner()


def _json(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _invoke(tmp_path: Path, *, canary_verdict: str):
    forward = _json(
        tmp_path,
        "forward.json",
        {"verdict": "NO_EDGE", "n_obs": 41, "psr_vs_benchmark": "0.82727"},
    )
    profit = _json(
        tmp_path,
        "profit.json",
        {
            "deployment_match": {
                "candidate_id": "globalfixed-ensemble-3-6-9-12",
                "exploration_canary_ready": True,
            }
        },
    )
    canary = _json(tmp_path, "canary.json", {"verdict": canary_verdict})
    nav = _json(tmp_path, "nav.json", {"total_value_usd": "12000"})
    sentinel = tmp_path / "sentinel.request"
    sentinel.write_text("armed: false\ncapital_usd: 0\nrun_seq: 1\n", encoding="utf-8")
    return RUNNER.invoke(
        app,
        [
            "ladder-decide",
            "--verdict-json",
            str(forward),
            "--profit-evidence-json",
            str(profit),
            "--hardened-canary-json",
            str(canary),
            "--account-nav-json",
            str(nav),
            "--live-portfolio",
            str(ROOT / "deploy/canary-live-portfolio.toml"),
            "--validated-portfolio",
            str(ROOT / "deploy/global-trend-fixed-portfolio.toml"),
            "--sentinel",
            str(sentinel),
            "--format",
            "json",
        ],
    )


def test_exact_evidence_and_hardened_pass_enter_20pct_canary(tmp_path: Path) -> None:
    result = _invoke(tmp_path, canary_verdict="PASS")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "PROMOTE"
    assert payload["target_rung"] == 1
    assert payload["target_capital_usd"] == 2400
    assert payload["exploration_verdict"]["hardened_canary_pass"] is True


def test_hardened_failure_keeps_real_money_disarmed(tmp_path: Path) -> None:
    result = _invoke(tmp_path, canary_verdict="FAIL")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "WAIT_EDGE"
    assert payload["target_rung"] == 0
    assert payload["exploration_verdict"]["hardened_canary_pass"] is False


def test_separate_live_performance_demotes_unfilled_stale_entry(tmp_path: Path) -> None:
    forward = _json(tmp_path, "forward.json", {"verdict": "NO_EDGE", "n_obs": 47})
    profit = _json(
        tmp_path,
        "profit.json",
        {
            "deployment_match": {
                "candidate_id": "globalfixed-ensemble-3-6-9-12",
                "exploration_canary_ready": False,
            }
        },
    )
    canary = _json(tmp_path, "canary.json", {"verdict": "PASS"})
    growth = _json(
        tmp_path,
        "growth.json",
        {"snapshot_count": 1, "max_drawdown_pct": None, "period_days": None},
    )
    performance = _json(tmp_path, "performance.json", {"fills_count": 0})
    nav = _json(tmp_path, "nav.json", {"total_value_usd": "1457.59"})
    sentinel = tmp_path / "sentinel.request"
    sentinel.write_text(
        "armed: true\ncapital_usd: 293\nladder_rung: 1\nrung_entered: 2026-08-22\n",
        encoding="utf-8",
    )

    result = RUNNER.invoke(
        app,
        [
            "ladder-decide",
            "--verdict-json",
            str(forward),
            "--profit-evidence-json",
            str(profit),
            "--hardened-canary-json",
            str(canary),
            "--live-growth-json",
            str(growth),
            "--live-performance-json",
            str(performance),
            "--account-nav-json",
            str(nav),
            "--live-portfolio",
            str(ROOT / "deploy/canary-live-portfolio.toml"),
            "--validated-portfolio",
            str(ROOT / "deploy/global-trend-fixed-portfolio.toml"),
            "--sentinel",
            str(sentinel),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "DEMOTE"
    assert payload["target_rung"] == 0
