"""스펙 140 - 탐색 캐너리 입력을 자본 사다리에 잇는 CLI 회귀 테스트."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest

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
    assert payload["target_rung"] == 2
    assert payload["target_capital_usd"] == 2400
    assert payload["exploration_verdict"]["hardened_canary_pass"] is True


def test_hardened_failure_keeps_real_money_disarmed(tmp_path: Path) -> None:
    result = _invoke(tmp_path, canary_verdict="FAIL")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "WAIT_EDGE"
    assert payload["target_rung"] == 0
    assert payload["exploration_verdict"]["hardened_canary_pass"] is False


def _invoke_factory(tmp_path: Path, *, winner: bool):
    live = ROOT / "deploy" / "canary-live-portfolio.toml"
    config_text = live.read_text(encoding="utf-8")
    config = PortfolioRebalanceConfig.model_validate(tomllib.loads(config_text)["portfolio"])
    fingerprint = strategy_fingerprint_digest(config)
    factory = _json(
        tmp_path,
        "factory.json",
        {
            "gate_version": "2.0",
            "candidate_count": 16,
            "complete_trial_count": 16,
            "global_audit_trial_count": 704,
            "unique_trial_fingerprint_count": 704,
            "decision": {
                "verdict": "FACTORY_EDGE" if winner else "NO_FACTORY_EDGE",
                "research_canary_eligible": winner,
                "selected_candidate_id": "factory-exact" if winner else None,
                "selected_strategy_fingerprint": fingerprint if winner else None,
                "selected_deploy_config": config_text if winner else None,
                "gates": [
                    {
                        "gate_id": "complete_family_trials",
                        "passed": True,
                        "actual": "16",
                        "required": "16",
                    },
                    {
                        "gate_id": "prior_audit_complete",
                        "passed": True,
                        "actual": "688",
                        "required": "688",
                    },
                    {
                        "gate_id": "global_audit_trials",
                        "passed": True,
                        "actual": "704",
                        "required": "704",
                    },
                    {
                        "gate_id": "unique_audit_fingerprints",
                        "passed": True,
                        "actual": "704",
                        "required": "704",
                    },
                    {"gate_id": "holdout_excess_psr", "passed": winner},
                ],
            },
        },
    )
    forward = _json(tmp_path, "forward.json", {"verdict": "NO_EDGE", "n_obs": 0})
    canary = _json(tmp_path, "canary.json", {"verdict": "PASS"})
    nav = _json(tmp_path, "nav.json", {"total_value_usd": "12000"})
    sentinel = tmp_path / "sentinel.request"
    sentinel.write_text("armed: false\ncapital_usd: 0\nrun_seq: 1\n", encoding="utf-8")
    return RUNNER.invoke(
        app,
        [
            "ladder-decide",
            "--verdict-json",
            str(forward),
            "--factory-evidence-json",
            str(factory),
            "--factory-evidence-age-hours",
            "2",
            "--hardened-canary-json",
            str(canary),
            "--account-nav-json",
            str(nav),
            "--live-portfolio",
            str(live),
            "--validated-portfolio",
            str(ROOT / "deploy/global-trend-fixed-portfolio.toml"),
            "--sentinel",
            str(sentinel),
            "--format",
            "json",
        ],
    )


def test_complete_exact_factory_winner_enters_only_10pct(tmp_path: Path) -> None:
    result = _invoke_factory(tmp_path, winner=True)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "PROMOTE"
    assert payload["target_rung"] == 1
    assert payload["target_capital_usd"] == 1200
    assert payload["factory_verdict"]["contract_version"] == "family-complete-v2"
    assert payload["factory_verdict"]["contract_complete"] is True
    assert payload["factory_verdict"]["exact_strategy_match"] is True


def test_current_no_factory_edge_stays_disarmed(tmp_path: Path) -> None:
    result = _invoke_factory(tmp_path, winner=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "WAIT_EDGE"
    assert payload["target_rung"] == 0
    assert payload["target_capital_usd"] is None
    assert payload["factory_verdict"]["contract_complete"] is False
    assert "factory_edge" in payload["factory_verdict"]["contract_reasons"]


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
